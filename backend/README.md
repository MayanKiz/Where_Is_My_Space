# WIMS API

FastAPI service for receiving MP4 uploads, storing the video in a **private temporary Supabase Storage bucket**, and creating a server-side processing job. This is a separate service from the Next.js frontend so other people can upload through the deployed website without installing Python.

## Current status

- `GET /health`: reports whether Supabase credentials are configured.
- `POST /v1/jobs/upload`: validates MP4 input, applies a size limit, uploads it to private temporary storage, and records a processing job in Supabase.
- `GET /v1/jobs/{job_id}`: returns the public-safe status fields for that unguessable job ID.
- Expired, unprocessed uploads are cleaned up by the service while it is running.
- **The AI worker is not implemented in this stage.** An accepted upload will report `received`, not a fabricated `completed` detection result. Video processing, progress updates, occupancy snapshots, and deletion after processing are later steps.

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
# Fill the server-only Supabase URL and service-role key in .env
uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000/docs` for the API schema and `http://localhost:8000/health` for the health status. Do not expose the service-role key to the browser, source code, screenshots, or GitHub.

## Supabase setup

Apply `../supabase/migrations/20261010150000_initial_wims_schema.sql` in the Supabase SQL editor. It creates the metadata tables, access policies, and a private `wims-temporary-videos` bucket with a 100 MiB upload cap. The backend service role is used for writes; public clients do not receive job-table access.

## Important deployment notes

- Deploy this service separately from the Next.js app (for example, as a Docker web service or on a managed container/VPS host).
- Set `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_VIDEO_BUCKET`, `CORS_ORIGINS`, `MAX_UPLOAD_MIB`, `UPLOAD_TTL_MINUTES` in the backend environment settings.
- Set the frontend's `NEXT_PUBLIC_WIMS_API_URL` to this service's HTTPS origin. The frontend must not contain the service-role key.
- Enforce the request-body limit at the hosting proxy too; this protects the API before multipart parsing.
- Uploads are temporarily stored in a private bucket. The cleanup loop needs the API service to remain running. Before a public launch, add external rate limiting/abuse monitoring and durable worker/queue handling.
- A stored upload is **not** proof that the AI analysed it. Do not label a job complete until a worker has actually processed the video and stored results.
