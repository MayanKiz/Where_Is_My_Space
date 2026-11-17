"""
Real YOLO-based people counter for Campus Library Occupancy Dashboard.

Usage — one camera:
    python cv_camera.py --camera-id cam_01 --source 0

Usage — all configured campus cameras (use --multi):
    python cv_camera.py --multi

Camera source can be:
    0, 1, 2 ...     → USB/built-in webcam index
    rtsp://...      → IP camera RTSP stream
    http://...      → MJPEG stream
    /dev/video0     → Linux device
    test            → uses ml_stub simulation (no real camera needed)

━━━ HOW THIS CONNECTS TO BACKEND ━━━
After each inference it POSTs:
    POST http://localhost:8000/count/update  (or set OCCUPANCY_API_BASE_URL)
    { "camera_id": "cam_01", "count": 14 }

camera_id must match what's configured in Admin Panel.
"""

import argparse
import asyncio
import sys
import time
import random
import os
from datetime import datetime, timezone

import httpx
BACKEND_URL = os.environ.get("OCCUPANCY_API_BASE_URL", "http://localhost:8000").rstrip("/")
DEVICE_API_KEY = os.environ.get("DEVICE_API_KEY", "")

# ─── Configure your cameras here ───────────────────────────────────────────
# source: webcam index (0,1,2), RTSP URL, or "test" for simulation
CAMERAS = {
    "cam_01":     {"source": 0,      "name": "Entrance / Lobby",            "detect_reserved": True},
    "cam_02":     {"source": 1,      "name": "Main Reading Hall",           "detect_reserved": True},
    "cam_03":     {"source": 2,      "name": "Upper Floor / Quiet Zone",    "detect_reserved": True},
    "cam_04":     {"source": 3,      "name": "Collaborative / Group Study", "detect_reserved": True},
    "cam_lt_01":       {"source": 4, "name": "Main Lecture Theatre (LT)", "detect_reserved": False},
    "cam_canteen_01":  {"source": 5, "name": "CS-IT Canteen",              "detect_reserved": False},
}

INFERENCE_INTERVAL = 3   # seconds between each count POST
SHOW_PREVIEW = False     # set True to open a CV window (requires display)
MODEL_NAME = "yolov8s.pt"  # small model — better overlap detection than nano, ~22MB

# Set True if cameras are ceiling-mounted (top-down view).
# False = side-angle view (webcam on desk/wall).
# Ceiling: laptop can be in ANY direction → uniform expansion used.
# Side: laptop is typically to the side/below person → directional expansion used.
CEILING_CAM = False
# ───────────────────────────────────────────────────────────────────────────


def load_yolo():
    """Import and load YOLO model. Fails clearly if ultralytics not installed."""
    try:
        from ultralytics import YOLO
        print(f"[CV] Loading model {MODEL_NAME} ...")
        model = YOLO(MODEL_NAME)
        print(f"[CV] Model ready.")
        return model
    except ImportError:
        print(
            "\n[ERROR] ultralytics not installed.\n"
            "Run:  pip install -r requirements_cv.txt\n"
        )
        sys.exit(1)


def _edge_distance(laptop_box: list, person_box: list) -> float:
    """Distance from laptop center to nearest edge of person bbox. 0 if overlapping."""
    ox = (laptop_box[0] + laptop_box[2]) / 2
    oy = (laptop_box[1] + laptop_box[3]) / 2
    dx = max(person_box[0] - ox, 0, ox - person_box[2])
    dy = max(person_box[1] - oy, 0, oy - person_box[3])
    return (dx ** 2 + dy ** 2) ** 0.5


def _within_threshold(laptop_box: list, person_box: list) -> bool:
    """True if laptop is within the person's desk zone threshold."""
    ox = (laptop_box[0] + laptop_box[2]) / 2
    oy = (laptop_box[1] + laptop_box[3]) / 2
    pw = person_box[2] - person_box[0]
    ph = person_box[3] - person_box[1]
    dist = _edge_distance(laptop_box, person_box)
    if CEILING_CAM:
        return dist < pw * 0.7
    else:
        # Side view: ignore laptops above person (not at desk level)
        if oy < person_box[1] - ph * 0.2:
            return False
        return dist < pw * 0.5


def count_people_and_reserved(model, frame, detect_reserved: bool = True) -> tuple[int, int]:
    """Detect people and reserved seats using one-to-one laptop assignment.

    detect_reserved=False for LT and canteen cameras — only people counted, no laptop detection.

    Each person is assigned their CLOSEST laptop (if within threshold).
    Unassigned laptops = reserved seats. This prevents a sitting person from
    accidentally "claiming" a nearby laptop left by someone else at an adjacent seat.

    COCO classes used:
        0  = person
        63 = laptop  (books excluded — too many false positives from shelves)
    """
    detect_classes = [0, 63] if detect_reserved else [0]
    results = model(frame, verbose=False, classes=detect_classes)
    boxes = results[0].boxes

    person_boxes = []
    object_boxes = []

    for box in boxes:
        cls = int(box.cls[0])
        coords = box.xyxy[0].tolist()
        if cls == 0:
            person_boxes.append(coords)
        else:
            object_boxes.append(coords)

    # One-to-one matching: each person claims their CLOSEST laptop only.
    # This prevents Person A from accidentally "absorbing" Person B's reserved laptop.
    assigned = set()
    for pb in person_boxes:
        best_idx, best_dist = None, float("inf")
        for i, lb in enumerate(object_boxes):
            if i in assigned:
                continue
            if _within_threshold(lb, pb):
                d = _edge_distance(lb, pb)
                if d < best_dist:
                    best_dist, best_idx = d, i
        if best_idx is not None:
            assigned.add(best_idx)

    reserved = len(object_boxes) - len(assigned)
    return len(person_boxes), reserved


async def post_count(client: httpx.AsyncClient, camera_id: str, count: int, reserved: int = 0) -> bool:
    """POST count to backend. Returns True on success."""
    try:
        r = await client.post(
            f"{BACKEND_URL}/count/update",
            json={
                "camera_id": camera_id,
                "count": count,
                "reserved": reserved,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            headers={"X-API-Key": DEVICE_API_KEY} if DEVICE_API_KEY else {},
            timeout=5.0,
        )
        return r.status_code == 200
    except Exception as e:
        print(f"[{camera_id}] POST failed: {e}")
        return False


async def run_camera(model, camera_id: str, source, client: httpx.AsyncClient):
    """Main loop for a single camera — capture → infer → POST."""
    import cv2

    cam_name = CAMERAS.get(camera_id, {}).get("name", camera_id)
    print(f"[{camera_id}] Starting — source={source!r}  region='{cam_name}'")

    while True:
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            print(f"[{camera_id}] Cannot open source {source!r}, retrying in 5s ...")
            await asyncio.sleep(5)
            continue

        print(f"[{camera_id}] Camera opened.")

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    print(f"[{camera_id}] Frame read failed — camera disconnected, reconnecting ...")
                    break

                do_reserved = CAMERAS.get(camera_id, {}).get("detect_reserved", True)
                count, reserved = count_people_and_reserved(model, frame, detect_reserved=do_reserved)
                ok = await post_count(client, camera_id, count, reserved)
                status = "✓" if ok else "✗"
                ts = datetime.now().strftime("%H:%M:%S")
                res_str = f"reserved={reserved:>2}" if do_reserved else "no-reserved"
                print(f"[{camera_id}] {ts}  people={count:>3}  {res_str}  {status}")

                if SHOW_PREVIEW:
                    label = f"{camera_id}: {count} people" + (f"  {reserved} reserved" if do_reserved else "")
                    cv2.putText(frame, label, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                    cv2.imshow(f"Library CV — {camera_id}", frame)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        return

                await asyncio.sleep(INFERENCE_INTERVAL)

        finally:
            cap.release()

        await asyncio.sleep(3)  # wait before reconnect attempt


async def run_simulation(camera_id: str, client: httpx.AsyncClient):
    """Simulation mode — no real camera, generates realistic counts like ml_stub."""
    ranges = {"cam_01": (0,40,2), "cam_02": (10,80,5), "cam_03": (5,30,3), "cam_04": (0,25,2), "cam_lt_01": (0,120,6), "cam_canteen_01": (0,60,4)}
    lo, hi, drift = ranges.get(camera_id, (0, 50, 3))
    count = random.randint(lo, hi)
    cam_name = CAMERAS.get(camera_id, {}).get("name", camera_id)

    print(f"[{camera_id}] Simulation mode — region='{cam_name}'")

    while True:
        count = max(lo, min(hi, count + random.randint(-drift, drift)))
        ok = await post_count(client, camera_id, count)
        status = "✓" if ok else "✗"
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{camera_id}] {ts}  count={count:>3}  {status} [SIM]")
        await asyncio.sleep(INFERENCE_INTERVAL)


async def main():
    global BACKEND_URL
    parser = argparse.ArgumentParser(description="AKGEC campus YOLO people counter")
    parser.add_argument("--camera-id", default=None, help="e.g. cam_01")
    parser.add_argument("--source", default=None, help="Webcam index, RTSP URL, or 'test'")
    parser.add_argument("--multi", action="store_true", help="Run all cameras from CAMERAS dict")
    parser.add_argument("--backend", default=BACKEND_URL, help="Backend base URL")
    args = parser.parse_args()

    backend = args.backend.rstrip("/")
    BACKEND_URL = backend

    if not args.multi and args.camera_id is None:
        parser.print_help()
        print("\nExample: python cv_camera.py --camera-id cam_01 --source 0")
        print("Example: python cv_camera.py --multi")
        sys.exit(1)

    # Build list of tasks
    tasks_spec: list[tuple[str, object]] = []

    if args.multi:
        for cam_id, cfg in CAMERAS.items():
            tasks_spec.append((cam_id, cfg["source"]))
    else:
        source_raw = args.source
        # Try to cast to int for webcam index
        try:
            source = int(source_raw)
        except (TypeError, ValueError):
            source = source_raw  # RTSP string or "test"
        tasks_spec.append((args.camera_id, source))

    # Decide whether to load real YOLO
    all_test = all(str(src) == "test" for _, src in tasks_spec)
    model = None if all_test else load_yolo()

    async with httpx.AsyncClient() as client:
        coroutines = []
        for cam_id, source in tasks_spec:
            if str(source) == "test":
                coroutines.append(run_simulation(cam_id, client))
            else:
                coroutines.append(run_camera(model, cam_id, source, client))

        print(f"\n[CV] Starting {len(coroutines)} camera(s) → backend: {backend}\n")
        await asyncio.gather(*coroutines)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[CV] Stopped.")
