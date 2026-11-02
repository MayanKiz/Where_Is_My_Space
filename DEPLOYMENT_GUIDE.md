# WIMS Deployment Guide (Railway + Vercel)

This guide walks through deploying the **Where Is My Space? (WIMS)** stack:

| Component | Host | What runs |
|---|---|---|
| Frontend (dashboard + capture) | **Vercel** | Next.js app in `web/` |
| API | **Railway** (service 1) | `uvicorn app.main:app` |
| AI Worker (OpenCV + YOLO) | **Railway** (service 2) | `python -m app.worker --mode all` |
| Database + Storage | **Supabase** | migrations in `supabase/migrations/` |

---

## 0. Prerequisites

- Git repo pushed to GitHub (`MayanKiz/Where_Is_My_Space`).
- A **Supabase** project with all three migrations applied
  (`20261010150000_initial_wims_schema.sql`, `20261010160000_wims_capture_sources.sql`,
  `20261017120000_wims_ai_worker.sql`).
- Supabase **service-role key**, a generated capture access code, and a Fernet key
  (see `backend/.env.example`).

---

## 1. Deploy the backend API on Railway

1. On [railway.app](https://railway.app), create a **New Project** → **Deploy from GitHub repo**.
2. Select the `Where_Is_My_Space` repo.
3. Railway will detect the service. Set the service's **Root Directory** to `backend`
   (so it uses `backend/Dockerfile` and `backend/railway.json`).
4. Add the environment variables (from `backend/.env.example` / `deploy/.env.production.example`):
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `SUPABASE_VIDEO_BUCKET=wims-temporary-videos`
   - `SUPABASE_PREVIEW_BUCKET=wims-job-previews`
   - `CORS_ORIGINS=https://where-is-my-space-wims.vercel.app`
   - `WIMS_CAPTURE_ACCESS_CODE=<generated>`
   - `WIMS_SOURCE_ENCRYPTION_KEY=<generated>`
   - `MAX_UPLOAD_MIB=100`, `UPLOAD_TTL_MINUTES=30`, etc. (optional tuning)
   - `YOLO_MODEL_PATH=/app/models/yolov5s.onnx`
   - `YOLO_MODEL_URL=https://github.com/ultralytics/yolov5/releases/download/v7.0/yolov5s.onnx`
   - `YOLO_MODEL_SHA256=8bc25a47abdbe2fd23e30eb948746bf856b031ea3cc815166687f52db9f8c659`
5. Deploy. Verify with `GET /health` — it should report Supabase, capture access, and RTSP encryption as configured.

> **API port:** Railway injects `$PORT`; the start command binds to it via `--port $PORT`.

---

## 2. Deploy the AI Worker on Railway

Create a **second service** in the same Railway project (same image, different command):

1. In the project, **New Service** → appDeploy from GitHub repo** → same repo, root directory `backend`.
2. In **Settings → Deploy**, set the start command to:
   ```
   python -m app.worker --mode all
   ```
   (You can add `railway.worker.json` to the repo to automate this.)
3. Add the **same environment variables** as the API.
4. **Attach a volume** mounted at `/app/models` so the YOLO model downloads **once**
   and is cached across restarts (the model is ~15 MB).

---

## 3. Deploy the frontend on Vercel

1. Import the repo in [vercel.com](https://vercel.com).
2. Set **Root Directory** to `web` (contains `package.json` and `vercel.json`).
3. Framework preset: **Next.js** (auto-detected).
4. Add environment variable:
   ```
   NEXT_PUBLIC_WIMS_API_URL=https://<your-railway-api>.up.railway.app
   ```
   (Use the public URL of the Railway API service above.)
5. Deploy.

---

## 4. End-to-end checks

```bash
# API health
curl -fsS https://YOUR_API_HOST/health

# Backend tests
python -m pytest backend/tests -q

# Frontend checks
cd web && npm ci && npm run typecheck && npm run lint && npm run build
```

### Demo acceptance test
1. Open the deployed Vercel `/capture` URL on a phone.
2. Enter the beta pairing code (matches `WIMS_CAPTURE_ACCESS_CODE`).
3. Record/upload a short clip and choose an occupancy zone.
4. Wait for the worker → you should see an AI result (peak persons) and an annotated preview on the dashboard.

---

## Security notes

- `SUPABASE_SERVICE_ROLE_KEY`, `WIMS_CAPTURE_ACCESS_CODE`, and `WIMS_SOURCE_ENCRYPTION_KEY`
  are **backend-only**. Never put them in Vercel/frontend env vars or commit them.
- RTSP URLs are encrypted server-side and never returned to the browser.
- The video storage bucket must remain private.
- A received file is **not** an AI result — only worker-processed jobs become results.
