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

### Code added (not yet verified end-to-end)
1. A Next.js / TypeScript / Tailwind web app in `web/`.
2. A responsive WIMS dashboard with sample data labelled as illustrative.
3. A mobile-first installable `/capture` PWA route with four source modes:
   - phone camera recording with browser permission;
   - screen capture only when supported by the mobile browser;
   - MP4/WebM file upload;
   - registration of an authorized RTSP/RTSPS IP camera.
4. A FastAPI service for source metadata, private temporary video upload, job creation/status, a shared pairing code, and encryption of RTSP URLs.
5. Supabase migrations for locations, zones, jobs, occupancy snapshots, source registry, RLS, and a private temporary video bucket.
6. Basic CI to run TypeScript, ESLint, and production build checks.

### Still required
1. **Fix any CI errors** and verify frontend production build.
2. Configure a real Supabase project and apply migrations in order.
3. Test source creation/list, MP4/WebM upload, job reads and video expiry cleanup with real credentials.
4. Build the OpenCV + YOLO inference worker and a durable job queue.
5. Add person detection and visual preview; do not confuse people count with exact chair occupancy.
6. Configure per-camera zones/polygons and implement a clearly defined occupancy estimate.
7. Persist inference output to `occupancy_snapshots` and wire the dashboard to live Supabase/API results.
8. Add continuous live streaming/RTSP ingestion; current phone modes record a short clip and upload it rather than sending a continuous stream.
9. Strengthen beta access with production-grade identity/access control, rate limiting and abuse protection.
10. Deploy frontend and API separately and verify both HTTPS endpoints; configure CORS and environment secrets.

## Security requirements

- `SUPABASE_SERVICE_ROLE_KEY`, `WIMS_CAPTURE_ACCESS_CODE`, and `WIMS_SOURCE_ENCRYPTION_KEY` are backend-only secrets.
- The frontend may contain only the public API origin and optional public Supabase credentials.
- Never return a saved RTSP URL to the browser; encrypt it at rest.
- The temporary video bucket must remain private. Expired raw uploads should be deleted while useful job/source metadata is retained.
- A successfully received file is not an AI result. Do not mark a job complete without verified processing results.

## Demo acceptance criteria

The first credible demo should let a second device open the deployed Capture URL, pair using the beta code, record/upload a short clip, and see a persisted source record and upload-job metadata. It must display an explicit **AI processing not enabled** state until the inference worker is implemented. Later acceptance adds bounding boxes, zone counts, timestamps, and dashboard updates based on the actual processed clip.
