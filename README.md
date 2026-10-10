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
  [Next step] AI worker → zone occupancy snapshots → dashboard
```

The web frontend and Python API are separate services. Vercel may host the frontend; the FastAPI service must be deployed separately. Video storage is private and temporary. RTSP addresses are encrypted at rest by the API.

## Code in this branch

- `web/`: Next.js, TypeScript, Tailwind, dashboard, mobile Capture PWA, MP4/WebM upload client and installable manifest.
- `backend/`: FastAPI source registry, upload endpoint, pairing-code check, job status API and best-effort temporary-file cleanup.
- `supabase/migrations/`: initial metadata schema and Capture source registry schema.
- `docs/`: product vision, privacy, system architecture, detection approach, database and MVP requirements.
- `IMPLEMENTATION_PLAN.md`: step-by-step implementation plan.

## What is not working yet

This branch is **not a deployed, verified end-to-end product yet**:
- Live Supabase migrations and project credentials have not been configured in this conversation.
- AI inference (YOLO/OpenCV worker), person tracking, zone occupancy/seat estimation, and continuous live streaming are not implemented.
- Registering an RTSP camera records its metadata and encrypted URL but does not connect to or analyse its stream yet.
- Upload receipt/job creation is coded but still needs testing against a real Supabase project and deployed API.
- Dashboard figures are illustrative sample values, not real occupancy.

A video being uploaded is **not** the same as the video being analysed.

## Setup docs

- Frontend and phone installation: [`web/README.md`](web/README.md)
- FastAPI and Supabase setup: [`backend/README.md`](backend/README.md)
- Product and technical documents: [`docs/`](docs/)
- Implementation steps: [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md)

Use only camera footage you are authorized to capture. WIMS does not need face recognition; keep raw footage temporary and persist the minimum useful occupancy metadata.
