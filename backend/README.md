# WIMS Capture API

FastAPI service for the **WIMS Capture mobile app**. It accepts uploaded/captured clips, saves source/job metadata in Supabase, and puts videos in a private temporary storage bucket. Deploy it separately from the Next.js frontend so anyone with the configured beta pairing code can use WIMS from their phone or computer without installing Python.

## Current API stage

- `GET /health`: reports whether Supabase, capture pairing, and RTSP encryption are configured.
- `GET /v1/sources`: lists source metadata without returning any RTSP address.
- `POST /v1/sources`: registers a phone camera, screen recording, video upload, or external RTSP camera.
- `POST /v1/jobs/upload`: accepts MP4/WebM clips, validates the container signature and size, puts the clip in private temporary storage, and records a job.
- `GET /v1/jobs/{job_id}`: returns safe status fields for a job.
- API source/upload/status requests require the shared `X-WIMS-Capture-Key` beta pairing code.
- Expired videos which have not entered processing are removed by a best-effort cleanup loop while the API runs.
- **AI inference and continuous live streaming are not implemented yet.** A successful upload means only that the video and metadata were received, not that occupancy was calculated.

## Run locally

Use Python 3.11+ (3.12 recommended).

```bash
cd backend
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
```

Set these values in `.env`:

1. `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` from the Supabase project's server-side API settings.
2. `WIMS_CAPTURE_ACCESS_CODE`: generate with `python -c "import secrets; print(secrets.token_urlsafe(24))"`. Share this separately with the people allowed to upload.
3. `WIMS_SOURCE_ENCRYPTION_KEY`: generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Keep the same key safe; rotating it requires re-encrypting registered RTSP URLs.
4. `CORS_ORIGINS`: exact frontend origin(s), for local development usually `http://localhost:3000`.

Run the service:

```bash
uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000/docs` for the API schema and `http://localhost:8000/health` for configuration status. Do not expose the service-role key or source-encryption key to the browser, screenshots, or GitHub.

## Supabase setup

Apply both migrations in order using the Supabase SQL editor or Supabase CLI:

1. `../supabase/migrations/20261010150000_initial_wims_schema.sql`
2. `../supabase/migrations/20261010160000_wims_capture_sources.sql`

They create locations, zones, processing jobs, occupancy metadata, the source registry, access policies, and a private `wims-temporary-videos` bucket with a 100 MiB cap. The API writes with the server-only service role. Browser roles cannot read the source registry or job table.

## Phone usage

1. Deploy the Next.js web app and this API to HTTPS origins.
2. Set `NEXT_PUBLIC_WIMS_API_URL` in the web app environment to the API's HTTPS origin.
3. Set `CORS_ORIGINS` in the API environment to the web app's exact HTTPS origin.
4. Open `/capture` on the phone. Enter the shared beta pairing code.
5. Choose Phone Camera, Screen Share (only if the browser supports it), Video File, or CCTV/IP Camera.
6. For the phone camera, allow permission, record a short clip, review it, then upload. For screen capture, use the browser picker where supported; otherwise use the phone's built-in screen recorder and upload the saved file.
7. A successful upload creates source metadata and a processing-job record. **No occupancy result will appear until the AI worker is added.**

The Capture route includes a web app manifest and can be added to the phone's Home Screen from the browser. Camera APIs require HTTPS (localhost is an exception). Mobile screen-sharing support varies by device/browser; it must not be promised on every phone.

## External camera safety

Use only camera URLs you are authorized to access. RTSP/RTSPS addresses are encrypted by the backend using `WIMS_SOURCE_ENCRYPTION_KEY`, and the API does not return that URL from source-list responses. Registration currently saves source metadata and an encrypted address; it does **not** connect to or process the RTSP stream yet.

## Deployment notes

- Host the API as a Docker web service or on a managed container/VPS host; see `Dockerfile`.
- Set `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_VIDEO_BUCKET`, `CORS_ORIGINS`, `MAX_UPLOAD_MIB`, `UPLOAD_TTL_MINUTES`, `WIMS_CAPTURE_ACCESS_CODE`, and `WIMS_SOURCE_ENCRYPTION_KEY` as server environment variables.
- Enforce request-body limits and rate limiting at the hosting proxy too; the app-level file-size check runs during upload.
- The cleanup loop is best effort and needs the API service to remain running. For a public launch, add durable queue/worker handling, external rate limiting, audit logs, and a scheduled storage cleanup independent of the API process.
- A received video is not proof that AI analysed it. Don't label a job completed until a worker has actually processed the clip and persisted valid results.
