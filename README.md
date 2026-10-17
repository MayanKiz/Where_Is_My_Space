# Where Is My Space? (WIMS)

> **Find your space before you reach there.**  
> Intelligence for physical spaces.

WIMS is a campus spatial-intelligence project intended to estimate how spaces are being used and help people find a suitable study area before walking there.

## The single-app experience

The web app includes a mobile-first **WIMS Capture** route at `/capture`. Open the deployed link on a phone; users do not install Python, OpenCV, or YOLO on their own device.

Capture modes:
- **Phone camera:** request camera permission, record a short clip, review, and upload it.
- **Screen share:** use the browser's display-capture API when available. Mobile support varies, so the phone's built-in screen recorder followed by file upload is the fallback.
- **Video file:** upload a recorded MP4 or WebM.
- **CCTV / IP camera:** register an authorized RTSP/RTSPS source. The URL is encrypted by the backend and is not returned in source-list responses.

The PWA can be added to a phone's Home Screen. Capture access uses a shared beta pairing code configured on the backend; it is not a full user-account system.

## Current architecture

```text
Phone / laptop browser
    ├── Camera recording
    ├── Screen recording (browser dependent)
    ├── MP4 / WebM upload
    └── Authorized RTSP source registration
                |
                v
       WIMS Capture (Next.js PWA)
                |
                v
        FastAPI upload API
          |             |
          v             v
   Supabase metadata   Private temporary video bucket
          |
          v
  AI worker (OpenCV + YOLO person detection)
          |
          v
  Zone occupancy snapshots → live dashboard
```

The inference worker (`python -m app.worker`) runs separately from the API. It claims upload jobs from the database, analyses sampled frames with a pinned YOLO ONNX model, stores an annotated preview, writes occupancy snapshots, and deletes the raw clip right after verified processing. In `--mode stream` it also connects continuously to registered RTSP cameras and publishes snapshots at a configured interval.

The web frontend and Python API are separate services. Vercel may host the frontend; the FastAPI service must be deployed separately. Video storage is private and temporary. RTSP addresses are encrypted at rest by the API.

## Code in this branch

- `web/`: Next.js, TypeScript, Tailwind, dashboard, mobile Capture PWA, MP4/WebM upload client and installable manifest.
- `backend/`: FastAPI source registry, upload endpoint, pairing-code check, zones/occupancy API, job status + AI preview APIs, per-endpoint rate limiting, and best-effort temporary-file cleanup — plus `app/worker.py`, the OpenCV + YOLO inference worker (durable job queue and RTSP streaming modes).
- `supabase/migrations/`: initial metadata schema, Capture source registry schema, and AI-worker schema (source→zone link, job claiming columns, private preview bucket).
- `docs/`: product vision, privacy, system architecture, detection approach, database and MVP requirements.
- `IMPLEMENTATION_PLAN.md`: step-by-step implementation plan.

## What is verified in this branch

Verified locally in this workspace:
- Frontend: TypeScript, ESLint, and `next build` all pass with the light theme.
- Backend: `compileall`, 18 unit tests (occupancy maths, rate limiting, YOLO decoding, video analysis), route smoke tests, and worker CLI smoke tests all pass.
- Real inference: the pinned `yolov5s.onnx` model detects 4 people in a COCO test image (~0.65 s/frame) and a full 30-frame clip run produces a correct peak-person count, a zone-restricted count, and an annotated JPEG preview. The preview was inspected visually.

Still required for a real deployment:
- A real Supabase project with all three migrations applied, plus backend/web secrets (not possible from this repository alone).
- Running the API + worker + web app against those credentials end to end (upload → AI job → snapshot → dashboard).
- Deploying the frontend and API separately and verifying both HTTPS endpoints.
- A live RTSP camera to exercise continuous streaming ingestion.
- Production-grade identity/access control beyond the shared beta code.

Until those steps happen, the dashboard clearly labels its data as sample values whenever the API/live feed is unavailable. A video being uploaded is **not** the same as the video being analysed, and a job is only marked `completed` by the worker after verified results are persisted.

## Setup docs

- Frontend and phone installation: [`web/README.md`](web/README.md)
- FastAPI and Supabase setup: [`backend/README.md`](backend/README.md)
- Product and technical documents: [`docs/`](docs/)
- Implementation steps: [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md)

Use only camera footage you are authorized to capture. WIMS does not need face recognition; keep raw footage temporary and persist the minimum useful occupancy metadata.
