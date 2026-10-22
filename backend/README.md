# WIMS Capture API + AI Inference Worker

FastAPI service for the **WIMS Capture mobile app** plus the OpenCV + YOLO inference worker. The API accepts uploaded/captured clips, saves source/job metadata in Supabase, and puts videos in a private temporary storage bucket. The worker claims those jobs, runs person detection, estimates zone occupancy, publishes snapshots, and serves them to the dashboard. Deploy both separately from the Next.js frontend so anyone with the configured beta pairing code can use WIMS from their phone without installing Python.

## API endpoints

- `GET /health`: reports whether Supabase, capture pairing, and RTSP encryption are configured.
- `GET /v1/sources`: lists source metadata without returning any RTSP address.
- `POST /v1/sources`: registers a phone camera, screen recording, video upload, or external RTSP camera; optionally links the source to an occupancy zone.
- `POST /v1/jobs/upload`: accepts MP4/WebM clips, validates the container signature and size, puts the clip in private temporary storage, and queues a job (optionally with a `zone_id`).
- `GET /v1/jobs/{job_id}`: returns safe status fields, including `result_summary` after the worker completes.
- `GET /v1/jobs/{job_id}/preview`: streams the annotated AI preview (bounding boxes + scores) as JPEG.
- `GET /v1/zones`: public zone configuration (capacity, polygon, location) used by the Capture app and dashboard.
- `POST /v1/zones`: creates a zone with a normalised 0..1 polygon for an existing location (pairing code required).
- `GET /v1/occupancy`: public live feed — the latest occupancy snapshot per public zone with availability labels.
- `POST /v1/assistant`: conversational space recommendations from derived occupancy metadata; uses Amazon Bedrock when enabled and a deterministic local fallback otherwise.
- Source/upload/status/preview requests require the shared `X-WIMS-Capture-Key` beta pairing code.
- All `/v1` routes are rate limited in-process (default 120 req/min per client, 10 uploads/min; configurable).
- Expired videos which have not entered processing are removed by a best-effort cleanup loop while the API runs.

## AI inference worker

```bash
python -m app.worker --mode jobs      # claim uploaded clips, analyse, persist results
python -m app.worker --mode stream    # continuous RTSP ingestion for zoned cameras
python -m app.worker --mode all       # both loops in one process
python -m app.worker --mode jobs --once   # drain the queue once and exit (cron/CI friendly)
```

How it works:

1. **Durable queue** — jobs live in the `processing_jobs` table. The worker claims a row with an atomic conditional update (`received`/`queued` → `processing`, with `claimed_by`/`claimed_at`); a stale-claim sweep requeues jobs whose worker crashed.
2. **Detection** — a pinned `yolov5s.onnx` model (SHA-256 verified on download, ~14 MB, auto-downloaded to `models/`) runs through OpenCV's DNN module on sampled frames (every `FRAME_STRIDE` frames, capped at `MAX_SAMPLED_FRAMES`).
3. **Occupancy** — if the job has a zone with a configured polygon, occupancy counts only persons whose bounding-box centre falls inside the polygon; the clip's estimate is the *peak* count observed, with mean detection confidence tracked separately.
4. **Preview** — the frame with the most detections gets bounding boxes drawn and is uploaded as JPEG to the private `wims-job-previews` bucket (served via `/v1/jobs/{id}/preview`).
5. **Cleanup** — after verified processing the raw clip is deleted immediately (`KEEP_RAW_VIDEO=true` keeps it for debugging); the job row retains only metadata and derived results.
6. **Streams** — in `stream` mode, registered `rtsp_camera` sources with a `zone_id` are read continuously (URLs are decrypted server-side, never returned), snapshots are written every `STREAM_INTERVAL_SECONDS`, and the source status/`last_seen_at` are updated.

A job is marked `completed` **only** with persisted results; failures get explicit `error_code`s (`VIDEO_UNREADABLE`, `MODEL_UNAVAILABLE`, `ZONE_NOT_FOUND`, `MAX_ATTEMPTS`, ...).

## Run locally

Use Python 3.11+ (3.12 recommended).

```bash
cd backend
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
pip install -r requirements.txt        # add -r requirements-dev.txt for pytest
cp .env.example .env
```

Set these values in `.env`:

1. `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` from the Supabase project's server-side API settings.
2. `WIMS_CAPTURE_ACCESS_CODE`: generate with `python -c "import secrets; print(secrets.token_urlsafe(24))"`. Share this separately with the people allowed to upload.
3. `WIMS_SOURCE_ENCRYPTION_KEY`: generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Keep the same key safe; rotating it requires re-encrypting registered RTSP URLs.
4. `CORS_ORIGINS`: exact frontend origin(s), for local development usually `http://localhost:3000`.

Run the API and the worker:

```bash
uvicorn app.main:app --reload --port 8000
python -m app.worker --mode all
```

Open `http://localhost:8000/docs` for the API schema and `http://localhost:8000/health` for configuration status. Do not expose the service-role key or source-encryption key to the browser, screenshots, or GitHub.

The assistant is disabled-by-default for local development. Set `BEDROCK_ENABLED=true`,
`AWS_REGION`, and `BEDROCK_MODEL_ID` only in a runtime with AWS credentials that have
`bedrock:Converse` permission. The request context contains public zone names and derived
occupancy values only; raw video and camera URLs are never sent to Bedrock. With the default
`BEDROCK_ENABLED=false`, common availability questions are answered locally without AWS.

Run tests:

```bash
python -m pytest tests -q
```

## Supabase setup

Apply the migrations in order using the Supabase SQL editor or Supabase CLI:

1. `../supabase/migrations/20261010150000_initial_wims_schema.sql`
2. `../supabase/migrations/20261010160000_wims_capture_sources.sql`
3. `../supabase/migrations/20261017120000_wims_ai_worker.sql`

They create locations, zones, processing jobs, occupancy snapshots, the source registry, job-claiming columns, access policies, a private `wims-temporary-videos` bucket (100 MiB cap), and a private `wims-job-previews` bucket for annotated JPEGs. The API and worker write with the server-only service role. Browser roles cannot read the source registry or job table; public roles can read public zone metadata and derived occupancy only.

## Phone usage

1. Deploy the Next.js web app and this API to HTTPS origins.
2. Set `NEXT_PUBLIC_WIMS_API_URL` in the web app environment to the API's HTTPS origin.
3. Set `CORS_ORIGINS` in the API environment to the web app's exact HTTPS origin.
4. Create a location and at least one zone (`POST /v1/zones` or the SQL editor), optionally with a `polygon`.
5. Open `/capture` on the phone. Enter the shared beta pairing code.
6. Choose a source mode. For the phone camera, allow permission, record a short clip, review it, then upload. Select the occupancy zone so the worker attributes people to the right space.
7. The Capture app polls the job and shows the AI result (peak persons in the zone) and the annotated bounding-box preview once the worker completes.

## External camera safety

Use only camera URLs you are authorized to access. RTSP/RTSPS addresses are encrypted by the backend using `WIMS_SOURCE_ENCRYPTION_KEY`, and the API does not return that URL from source-list responses. When an RTSP source has a zone linked, the stream worker connects continuously and publishes occupancy snapshots; without a zone it stays registered but idle.

## Deployment notes

- Host the API as a Docker web service or on a managed container/VPS host; see `Dockerfile`. Run the worker (`python -m app.worker --mode all`) next to it (same image, different command).
- Set `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_VIDEO_BUCKET`, `SUPABASE_PREVIEW_BUCKET`, `CORS_ORIGINS`, `MAX_UPLOAD_MIB`, `UPLOAD_TTL_MINUTES`, `WIMS_CAPTURE_ACCESS_CODE`, `WIMS_SOURCE_ENCRYPTION_KEY`, and the `YOLO_*`/`RATE_LIMIT_*` knobs as server environment variables.
- Enforce request-body limits and rate limiting at the hosting proxy too; the in-process limiter is best-effort and per-instance.
- The cleanup loop is best effort and needs the API service to remain running.
- Do not label a job completed until the worker has actually processed the clip and persisted valid results — the API never marks jobs completed itself.
