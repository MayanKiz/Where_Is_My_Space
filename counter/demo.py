"""Library Counter — Demo v1.0 (browser webcam).

A mock-test version of the counter for demonstrations. After signing in, the
browser asks permission to use this computer's camera. The video is shown only
on this screen. Every couple of seconds one still frame is sent to this same
computer (127.0.0.1), where YOLO counts the people and the frame is discarded.
ONLY the number is sent to the cloud dashboard — no image, face or video ever
leaves this machine.

Run:  python demo.py      then open http://127.0.0.1:8901
"""

import re
import threading
from contextlib import asynccontextmanager

import cv2
import httpx
import numpy as np
import uvicorn
from fastapi import FastAPI, Form, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.middleware.sessions import SessionMiddleware

import app as portal  # reuse the tested login, throttle and page styling
import counter_engine
from config import get_settings
from counter_engine import count_reserved_seats, detect, get_outbound, load_model, send_count

settings = get_settings()

def _load_model_in_background():
    def _load():
        try:
            load_model()
        except Exception as exc:  # shown to the user on the first count instead
            print(f"[demo] model load failed: {exc}")

    threading.Thread(target=_load, daemon=True).start()


@asynccontextmanager
async def _lifespan(_app):
    # Load YOLO in the background so the first count isn't slow.
    _load_model_in_background()
    yield


demo = FastAPI(title="Library Counter — Demo v1.0", lifespan=_lifespan)
demo.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET,
    same_site="strict",
    max_age=settings.SESSION_MAX_AGE,
)

_client = httpx.Client()
_MAX_FRAME_BYTES = 3_000_000
_CAMERA_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _unauthorized() -> JSONResponse:
    return JSONResponse({"detail": "login required"}, status_code=401)


# ── login (same credentials and lockout as the main portal) ──────────────────
@demo.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if portal._logged_in(request):
        return RedirectResponse("/", status_code=303)
    return HTMLResponse(portal._login_page())


@demo.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    ip = portal._client_ip(request)
    remaining = portal._lockout_remaining(ip)
    if remaining:
        mins = (remaining + 59) // 60
        return HTMLResponse(
            portal._login_page(f"Too many attempts. Try again in about {mins} minute(s)."),
            status_code=429,
        )
    if portal._check_credentials(email, password):
        portal._clear_fails(ip)
        request.session["user"] = email.strip().lower()
        return RedirectResponse("/", status_code=303)
    portal._record_fail(ip)
    return HTMLResponse(portal._login_page("Incorrect email or password."), status_code=401)


@demo.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@demo.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


# The same "What leaves this machine" page as the main portal.
demo.add_api_route("/outbound", portal.outbound_page, methods=["GET"], response_class=HTMLResponse)


# ── API used by the demo page ────────────────────────────────────────────────
@demo.get("/api/regions")
async def api_regions(request: Request):
    """Zones configured on the dashboard, so the demo counts for a real one."""
    if not portal._logged_in(request):
        return _unauthorized()

    def fetch():
        try:
            r = _client.get(f"{settings.BACKEND_URL.rstrip('/')}/regions", timeout=60.0)
            r.raise_for_status()
            return [
                {"camera_id": z["camera_id"], "name": z["name"], "section": z.get("section", "library")}
                for z in r.json()
            ]
        except Exception:
            return []

    return {"regions": await run_in_threadpool(fetch), "default": settings.DEMO_CAMERA_ID}


@demo.get("/api/outbound")
def api_outbound(request: Request):
    if not portal._logged_in(request):
        return _unauthorized()
    return get_outbound(20)


@demo.get("/api/health")
def api_health(request: Request):
    if not portal._logged_in(request):
        return _unauthorized()
    return {"model_ready": counter_engine._model is not None}


@demo.post("/api/infer")
async def api_infer(request: Request, camera_id: str, reserved: int = 1):
    """Count people in one frame from this computer's browser, send only the number."""
    if not portal._logged_in(request):
        return _unauthorized()
    if not _CAMERA_ID_RE.match(camera_id):
        return JSONResponse({"detail": "Invalid zone ID"}, status_code=400)

    data = await request.body()
    if not data:
        return JSONResponse({"detail": "Empty frame"}, status_code=400)
    if len(data) > _MAX_FRAME_BYTES:
        return JSONResponse({"detail": "Frame too large"}, status_code=413)

    frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    del data
    if frame is None:
        return JSONResponse({"detail": "Not a valid image"}, status_code=400)
    height, width = frame.shape[:2]

    try:
        persons, laptops = await run_in_threadpool(detect, frame, bool(reserved))
    except Exception as exc:
        return JSONResponse({"detail": f"Detection failed: {exc}"}, status_code=500)
    finally:
        frame = None  # the frame is discarded here — it is never stored or sent

    people = len(persons)
    reserved_seats = count_reserved_seats(persons, laptops) if reserved else 0
    ok, detail, body = await run_in_threadpool(send_count, _client, camera_id, people, reserved_seats)
    return {
        "people": people,
        "reserved": reserved_seats,
        "width": width,
        "height": height,
        "boxes": {"person": persons, "laptop": laptops},
        "sent": body,
        "ok": ok,
        "detail": detail,
    }


# ── the demo page ────────────────────────────────────────────────────────────
DEMO_STYLE = """
<style>
  .demo-grid { display:grid; grid-template-columns: 1.6fr 1fr; gap:16px; }
  @media (max-width:760px) { .demo-grid { grid-template-columns:1fr; } }
  .stage { position:relative; background:#0f1a19; border-radius:10px; overflow:hidden; min-height:260px; }
  .stage video { display:block; width:100%; height:auto; transition:opacity .2s; }
  .stage canvas { position:absolute; inset:0; width:100%; height:100%; pointer-events:none; }
  .stage-empty { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; color:#9fb3b0; font-size:.95rem; }
  .tag { font-size:.7rem; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); font-weight:700; }
  .big { font-size:3.4rem; font-weight:800; line-height:1; color:var(--teal); margin-top:6px; }
  pre.sent { background:var(--paper); border:1px solid var(--line); border-radius:8px; padding:10px 12px; font-size:.82rem; overflow-x:auto; margin:6px 0; }
  .banner { margin-bottom:16px; }
</style>
"""

DEMO_BODY = """
<header class="bar">
  <h1>Library Counter <span class="muted" style="font-size:.9rem">· Demo v1.0</span></h1>
  <div style="display:flex;gap:8px">
    <a class="btn ghost sm" href="/outbound">What leaves this machine</a>
    <a class="btn ghost sm" href="/logout">Sign out</a>
  </div>
</header>

<div class="card">
  <p style="margin-top:0"><b>How this demo works:</b> the browser asks to use this computer's camera.
  The video stays on this screen. Every 2 seconds one still frame goes to this same computer,
  where the people are counted and the frame is thrown away. <b>Only the number</b> is sent to the dashboard.</p>
  <div class="grid2">
    <div><label for="zone">Zone to count for</label><select id="zone"><option>Loading zones…</option></select></div>
    <div style="display:flex;align-items:flex-end;gap:8px;margin-top:10px">
      <button class="btn" id="startBtn" type="button">Start camera</button>
      <button class="btn gray" id="stopBtn" type="button" disabled>Stop</button>
    </div>
  </div>
  <label style="display:flex;align-items:center;gap:8px;margin-top:14px;font-weight:600">
    <input type="checkbox" id="hideVideo" style="width:auto"> Privacy view — hide the video, show only what the system detects
  </label>
  <p id="msg" class="muted" style="margin:10px 0 0;font-size:.9rem"></p>
</div>

<div class="demo-grid">
  <div class="card">
    <div class="stage">
      <video id="video" autoplay muted playsinline></video>
      <canvas id="overlay"></canvas>
      <div class="stage-empty" id="stageEmpty">Camera is off</div>
    </div>
  </div>
  <div class="card">
    <div class="tag">Counted right now</div>
    <div class="big" id="people">–</div>
    <div class="muted">people</div>
    <div style="margin-top:12px"><b id="reservedN">–</b> <span class="muted">reserved seats (laptop, nobody there)</span></div>
    <div class="tag" style="margin-top:18px">Last message sent to the cloud</div>
    <pre class="sent" id="lastSent">nothing yet</pre>
    <div id="sendState" style="font-size:.85rem"></div>
  </div>
</div>

<div class="card">
  <h2 style="margin-top:0">Live: what's leaving this computer</h2>
  <p class="muted" style="font-size:.9rem;margin-top:0">Every message this computer sends. Each one is only a number — no image, no face, no video.</p>
  <table>
    <thead><tr><th>Time</th><th>Status</th><th>Exact message sent</th></tr></thead>
    <tbody id="log"><tr><td colspan="3" class="muted">Nothing sent yet.</td></tr></tbody>
  </table>
</div>

<script>
const $ = id => document.getElementById(id);
const video = $('video'), overlay = $('overlay'), zone = $('zone'), msg = $('msg');
let stream = null, timer = null, busy = false;
const sections = {};

function option(value, text, selected) {
  const o = document.createElement('option');
  o.value = value; o.textContent = text; o.selected = !!selected;
  return o;
}

async function loadZones() {
  try {
    const r = await fetch('/api/regions');
    if (r.status === 401) { location.href = '/login'; return; }
    const d = await r.json();
    zone.innerHTML = '';
    if (!d.regions.length) {
      zone.appendChild(option(d.default, d.default + ' (default)', true));
      msg.textContent = "Couldn't load zones from the dashboard — it may be waking up. Counts will go to " + d.default + '.';
      return;
    }
    for (const z of d.regions) {
      sections[z.camera_id] = z.section;
      zone.appendChild(option(z.camera_id, z.name + ' (' + z.camera_id + ')', z.camera_id === d.default));
    }
  } catch (e) { msg.textContent = "Couldn't load zones: " + e; }
}

$('startBtn').onclick = async () => {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    msg.textContent = 'This browser cannot open the camera here. Open the page at http://127.0.0.1:8901 in Chrome or Edge.';
    return;
  }
  msg.textContent = 'Asking for camera permission…';
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 640 }, height: { ideal: 480 } }, audio: false });
  } catch (e) {
    msg.textContent = e.name === 'NotAllowedError'
      ? 'Camera permission was denied. Allow camera access for this page and try again.'
      : 'No camera available: ' + e.message;
    return;
  }
  video.srcObject = stream;
  await video.play();
  $('stageEmpty').style.display = 'none';
  $('startBtn').disabled = true; $('stopBtn').disabled = false; zone.disabled = true;
  msg.textContent = 'Camera on — counting every 2 seconds. The first count can take a few seconds while the model loads.';
  tick();
  timer = setInterval(tick, 2000);
};

function stop() {
  clearInterval(timer); timer = null;
  if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }
  video.srcObject = null;
  overlay.getContext('2d').clearRect(0, 0, overlay.width, overlay.height);
  $('stageEmpty').style.display = 'flex';
  $('startBtn').disabled = false; $('stopBtn').disabled = true; zone.disabled = false;
  msg.textContent = 'Camera off.';
}
$('stopBtn').onclick = stop;
$('hideVideo').onchange = e => { video.style.opacity = e.target.checked ? '0' : '1'; };

function explain(detail) {
  if (detail.includes('404')) return "Not on the dashboard: this zone ID doesn't exist there (HTTP 404).";
  if (detail.includes('401')) return "Rejected: DEVICE_API_KEY doesn't match the server (HTTP 401).";
  return 'Not delivered: ' + detail + ' — the server may be waking up; it keeps retrying.';
}

function draw(d) {
  const w = video.clientWidth, h = video.clientHeight;
  overlay.width = w; overlay.height = h;
  const g = overlay.getContext('2d');
  g.clearRect(0, 0, w, h);
  const sx = w / d.width, sy = h / d.height;
  g.lineWidth = 3; g.font = 'bold 14px system-ui, sans-serif';
  const box = (b, color, label) => {
    g.strokeStyle = color; g.fillStyle = color;
    g.strokeRect(b[0] * sx, b[1] * sy, (b[2] - b[0]) * sx, (b[3] - b[1]) * sy);
    g.fillText(label, b[0] * sx + 4, b[1] * sy + 16);
  };
  d.boxes.person.forEach(b => box(b, '#02c39a', 'person'));
  d.boxes.laptop.forEach(b => box(b, '#e0ad4e', 'laptop'));
}

async function refreshLog() {
  const r = await fetch('/api/outbound');
  if (!r.ok) return;
  const rows = await r.json();
  const tb = $('log');
  tb.innerHTML = '';
  for (const e of rows.slice(0, 8)) {
    const tr = document.createElement('tr');
    const t1 = document.createElement('td'); t1.className = 'muted'; t1.textContent = e.at;
    const t2 = document.createElement('td');
    t2.innerHTML = e.ok ? '<span class="pill on">sent</span>' : '<span class="pill err">failed</span>';
    const t3 = document.createElement('td'); const c = document.createElement('code');
    c.textContent = JSON.stringify(e.body); t3.appendChild(c);
    tr.append(t1, t2, t3); tb.appendChild(tr);
  }
}

async function tick() {
  if (busy || !stream || !video.videoWidth) return;
  busy = true;
  try {
    const c = document.createElement('canvas');
    c.width = video.videoWidth; c.height = video.videoHeight;
    c.getContext('2d').drawImage(video, 0, 0);
    const blob = await new Promise(res => c.toBlob(res, 'image/jpeg', 0.8));
    const reserved = (sections[zone.value] || 'library') === 'library' ? 1 : 0;
    const r = await fetch('/api/infer?camera_id=' + encodeURIComponent(zone.value) + '&reserved=' + reserved,
      { method: 'POST', headers: { 'Content-Type': 'image/jpeg' }, body: blob });
    if (r.status === 401) { location.href = '/login'; return; }
    const d = await r.json();
    if (!r.ok) { msg.textContent = d.detail || ('Error ' + r.status); return; }
    draw(d);
    $('people').textContent = d.people;
    $('reservedN').textContent = d.reserved;
    $('lastSent').textContent = JSON.stringify(d.sent, null, 2);
    const st = $('sendState');
    st.textContent = d.ok ? 'Delivered to the dashboard ✓' : explain(d.detail);
    st.style.color = d.ok ? 'var(--green)' : 'var(--red)';
    refreshLog();
  } catch (e) {
    msg.textContent = 'Error: ' + e;
  } finally {
    busy = false;
  }
}

loadZones();
</script>
"""


@demo.get("/", response_class=HTMLResponse)
def home(request: Request):
    if not portal._logged_in(request):
        return RedirectResponse("/login", status_code=303)
    warn = "" if settings.DEVICE_API_KEY else (
        '<div class="banner">⚠️ No <code>DEVICE_API_KEY</code> set in .env — the dashboard will reject counts.</div>'
    )
    return HTMLResponse(portal._page("Counter — Demo v1.0", DEMO_STYLE + warn + DEMO_BODY))


if __name__ == "__main__":
    # Always localhost: browsers only allow camera access on a secure origin,
    # and http://127.0.0.1 counts as one.
    # ASCII only: Windows consoles/redirected output may not encode arrows etc.
    print(f"\n  Library Counter - Demo v1.0  ->  http://127.0.0.1:{settings.DEMO_PORT}")
    print(f"  Sending counts to            ->  {settings.BACKEND_URL}\n")
    for p in portal.setup_problems():
        print(f"  !! SETUP NEEDED: {p}")
    uvicorn.run(demo, host="127.0.0.1", port=settings.DEMO_PORT, log_level="warning")
