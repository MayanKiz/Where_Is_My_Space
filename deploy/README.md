# WIMS production deployment bundle

This directory prepares the missing P0 deployment pieces without deploying anything. The current connected Supabase project is `where-is-my-space` (`eplaxnykyyhboioxlifh`) at `https://eplaxnykyyhboioxlifh.supabase.co`. Its three WIMS migrations are recorded, all five application tables exist, and the `wims-temporary-videos` and `wims-job-previews` buckets are present and private. The project currently has zero locations, zones, jobs, and snapshots.

## What this bundle provides

`docker-compose.production.yml` runs the FastAPI API and the long-lived YOLO/OpenCV worker as separate restartable containers built from `backend/Dockerfile`. The worker has a persistent model cache volume so the pinned ONNX model is downloaded once per host. The API exposes port 8000 and has a local healthcheck; place it behind a managed HTTPS reverse proxy or hosting provider before connecting Vercel.

`.env.production.example` is a placeholder-only checklist. Copy it to `.env.production` on the private host and fill in the server-only values there. Do not commit `.env.production` or send its contents through chat.

## Manual deployment sequence

1. Choose a persistent Docker host with HTTPS, restart policies, at least 2 CPU cores, 4 GB RAM, and outbound HTTPS access for the initial model download. A sleeping/free web service is not suitable for the worker.
2. Clone `MayanKiz/Where_Is_My_Space` at `main` on that host and copy `deploy/.env.production.example` to `deploy/.env.production`.
3. Fill in `SUPABASE_SERVICE_ROLE_KEY`, `WIMS_CAPTURE_ACCESS_CODE`, and `WIMS_SOURCE_ENCRYPTION_KEY`. Keep the supplied Supabase URL and bucket names unless the project is intentionally changed. Generate the pairing code and Fernet key with the commands shown in the example file.
4. Start the two services from the repository root:

   ```bash
   docker compose -f deploy/docker-compose.production.yml up -d --build
   docker compose -f deploy/docker-compose.production.yml ps
   docker compose -f deploy/docker-compose.production.yml logs --tail=100 wims-api wims-worker
   ```

5. Put the API behind an HTTPS hostname and verify that `GET https://YOUR_API_HOST/health` returns HTTP 200 with `supabase_credentials_configured`, `capture_access_configured`, and `rtsp_encryption_configured` all set to `true`. The worker should log that it is polling and should download/load the pinned model on first processing.
6. In Vercel, set the Production environment variable `NEXT_PUBLIC_WIMS_API_URL` to `https://YOUR_API_HOST` for project `where-is-my-space-wims`, then redeploy the `web/` root. Set the API's `CORS_ORIGINS` to exactly `https://where-is-my-space-wims.vercel.app` (plus any explicitly required alternate frontend origin).
7. Create a public location and zone through the protected API. Do not insert fabricated occupancy snapshots. A typical zone uses a polygon with normalized coordinates in the `0..1` range.
8. Open `https://where-is-my-space-wims.vercel.app/capture` on a phone, enter the pairing code, record a short authorized clip, select the zone, and upload it.
9. Verify the acceptance chain: upload returns a job ID; `GET /v1/jobs/{id}` moves from `received`/`processing` to `completed`; the result contains `stage: ai_processed`; the private preview endpoint returns an image; Supabase contains a new occupancy snapshot; and the dashboard changes from sample data to live data.
10. Verify cleanup after completion: the raw object is removed from `wims-temporary-videos` unless `KEEP_RAW_VIDEO=true` was intentionally enabled for debugging. Keep that setting `false` in production.

## Current blockers that still require user/provider action

- Vercel connector access is not enabled in this session, so the current Production environment variable cannot be inspected or changed through an authenticated Vercel API.
- No backend hosting provider or persistent Docker host is connected, so the API and worker cannot be deployed from this session.
- Supabase service-role credentials, the capture pairing code, and the Fernet encryption key are required on the backend host. They must be entered through the host's secret manager; they should not be pasted into chat.
- No location or zone exists yet, so even a healthy API has no configured public space to display.
- No production migration is requested or needed based on the current Supabase inspection; all three migrations are already recorded.

## Safe checks before production use

```bash
curl -fsS https://YOUR_API_HOST/health
curl -fsS https://YOUR_API_HOST/v1/zones
python -m pytest backend/tests -q
cd web && npm ci && npm run typecheck && npm run lint && npm run build
```

Do not treat `/health` alone as end-to-end success. The acceptance test requires a real authorized video, real YOLO inference, a persisted snapshot, and live dashboard output.
