# WIMS Web + Capture

Next.js frontend for **Where Is My Space?** The `/capture` route is a mobile-first, installable PWA for adding camera sources and uploading video from a phone or computer.

## Requirements

- Node.js 20.9 or newer
- npm

## Run locally

```bash
npm install
cp .env.example .env.local
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The dashboard is at `/`; the mobile source studio is at `/capture`.

Set `NEXT_PUBLIC_WIMS_API_URL` in `.env.local` to the FastAPI service origin. For local testing this is commonly `http://localhost:8000`, with the API's `CORS_ORIGINS` set to `http://localhost:3000`.

## Phone install

Deploy the web app to an HTTPS domain and open `/capture` on the phone. Use the browser's **Add to Home Screen / Install app** option. The app manifest is served from `/manifest.webmanifest`.

- **Phone camera:** requests camera permission, records a short clip, lets the user review it, then uploads the recording.
- **Screen share:** uses the browser's Screen Capture API when supported. Mobile support varies; the fallback is the phone's built-in screen recorder followed by Video File upload.
- **Video file:** accepts MP4/WebM files up to 100 MiB per file (server configuration can set the limit).
- **CCTV / IP camera:** registers an RTSP/RTSPS source with an optional occupancy zone. The server encrypts the URL; the stream worker analyses zoned cameras continuously.
- **Occupancy zone:** when zones exist on the API, a zone picker appears so uploads and cameras are attributed to the right space.
- **Job tracking:** after an upload, the app polls the job status and shows the AI result plus the annotated bounding-box preview when the worker finishes.
- **Registered sources:** lists saved source metadata without exposing camera URLs.

The Capture app prompts for a shared beta pairing code configured only on the backend as `WIMS_CAPTURE_ACCESS_CODE`. The code is retained in the current tab's session storage. It is not a full user-account system, so public production use will need stronger access control and rate limits.

## Available scripts

- `npm run dev` — local dev server
- `npm run build` — production build
- `npm run start` — serve a production build
- `npm run lint` — ESLint
- `npm run typecheck` — TypeScript checks

## Current implementation status

Implemented and locally verified (typecheck, ESLint, production build all pass): light-themed dashboard that fetches live occupancy from `GET /v1/occupancy` (and labels its data as samples whenever the API is unreachable), capture PWA route/manifest, browser camera recording, feature-detected screen recording, MP4/WebM upload client with progress, source registration/list UI, zone picker, job polling with AI result + preview display, pairing-code checks, and RTSP URL encryption at rest.

The backend implements the inference worker (YOLO/OpenCV), zone occupancy estimation, occupancy snapshots, and continuous RTSP ingestion — verified with unit tests and a real `yolov5s.onnx` model locally.

**Still required for a live product:** applying the SQL migrations to a real Supabase project, configuring production secrets, deploying the frontend/API/worker, and verifying the whole flow end to end on those deployments. Until then the dashboard labels its numbers as sample data. Upload success is not the same as AI processing success — the Capture app shows the AI result only after the worker marks the job completed.

Never put `SUPABASE_SERVICE_ROLE_KEY`, `WIMS_CAPTURE_ACCESS_CODE` or `WIMS_SOURCE_ENCRYPTION_KEY` in frontend environment variables.
