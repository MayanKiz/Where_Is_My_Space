# WIMS Implementation Plan

This repository is being developed as working software, in focused commits. The UI must never present sample data as live measurements.

## Product goal

Where Is My Space? helps people find suitable available campus spaces. The end-to-end target is:

`Phone/camera source → secure capture/API → AI inference → configured occupancy zones → Supabase metadata → WIMS dashboard`

## Agreed constraints

- Developer setup: laptop/PC.
- A single **WIMS Capture** app route should accept camera recordings, browser screen capture where supported, MP4/WebM files, and additional authorized IP camera sources.
- The Capture PWA should open from a link and be addable to a phone's Home Screen; a native APK is not required for the first prototype.
- Other users must not need to install Python, OpenCV, or YOLO on their devices.
- Supabase is the metadata store. Raw video should be kept in private temporary storage and deleted after processing/expiry.
- No face recognition. Keep only the minimum occupancy metadata.
- Frontend and Python inference/API are separate deployable services.
- Keep each meaningful change in its own Git commit.
- Never claim a stage, external integration, test, or deployment is complete without verification.

## Implementation state in this PR branch

### Code added and locally verified
1. A Next.js / TypeScript / Tailwind web app in `web/` with a light, small-text theme; TypeScript, ESLint and the production build all pass.
2. A dashboard wired to the live API (`GET /v1/occupancy`, `GET /health`); it shows live zone occupancy and falls back to clearly labelled sample values when the API is unreachable.
3. A mobile-first installable `/capture` PWA route with four source modes:
   - phone camera recording with browser permission;
   - screen capture only when supported by the mobile browser;
   - MP4/WebM file upload;
   - registration of an authorized RTSP/RTSPS IP camera (optionally linked to a zone).
   Plus an occupancy-zone picker, job-status polling with AI results, and the annotated bounding-box preview.
4. A FastAPI service for source metadata, private temporary video upload, job creation/status, zones (with polygons), a public live-occupancy feed, an AI preview endpoint, a shared pairing code, encryption of RTSP URLs, and per-client rate limiting.
5. Supabase migrations for locations, zones, jobs, occupancy snapshots, source registry, RLS, a private temporary video bucket, worker job-claiming columns, and a private preview bucket.
6. An OpenCV + YOLO inference worker (`backend/app/worker.py`): durable job queue backed by `processing_jobs` with atomic claims and stale-claim recovery, pinned SHA-256 model download, person detection on sampled frames, zone-polygon occupancy estimates, annotated previews, immediate raw-video deletion after processing, and continuous RTSP streaming ingestion for zoned cameras.
7. CI: web (TypeScript, ESLint, production build) and backend (syntax, 18 unit tests, route + worker smoke tests).
8. Real-model verification: the pinned `yolov5s.onnx` detects 4 people in a COCO test image (~0.65 s/frame on CPU); a full clip run produces correct full-frame and zone-restricted counts and a visually inspected bounding-box preview.

### Still required (external steps)
1. Configure a real Supabase project and apply the three migrations in order.
2. Test source creation/list, MP4/WebM upload, job processing, preview, expiry cleanup and live occupancy with real credentials (API + worker + web app running together).
3. Deploy frontend and API+worker separately and verify both HTTPS endpoints; configure CORS and environment secrets.
4. Exercise continuous live streaming with a real RTSP camera (the ingestion code exists but has no camera to test against here).
5. Strengthen beta access with production-grade identity/access control, external rate limiting and abuse protection.
6. Refine the occupancy definition (e.g. tracking across frames, seat-level estimates) once real campus footage is available.

## Security requirements

- `SUPABASE_SERVICE_ROLE_KEY`, `WIMS_CAPTURE_ACCESS_CODE`, and `WIMS_SOURCE_ENCRYPTION_KEY` are backend-only secrets.
- The frontend may contain only the public API origin and optional public Supabase credentials.
- Never return a saved RTSP URL to the browser; encrypt it at rest.
- The temporary video bucket must remain private. Expired raw uploads should be deleted while useful job/source metadata is retained.
- A successfully received file is not an AI result. Do not mark a job complete without verified processing results.

## Demo acceptance criteria

The first credible demo should let a second device open the deployed Capture URL, pair using the beta code, record/upload a short clip, and see a persisted source record, an upload-job record, and — once the worker processes it — an AI result (peak persons in the configured zone), an annotated bounding-box preview, and a matching dashboard update from `occupancy_snapshots`. The dashboard must show an explicit **sample data** state whenever live results are not available, and a received upload must never be presented as an AI result.
