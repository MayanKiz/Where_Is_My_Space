

```md
# Where Is My Space? (WIMS)

> **Find your space before you reach there.**  
> Intelligence for physical spaces.

WIMS is a campus spatial-intelligence project that estimates how spaces are being used and helps people find suitable study areas before walking there.

## Live Application

**Frontend:** https://where-is-my-space-wims.vercel.app

The web app includes a mobile-first **WIMS Capture** route at `/capture`. Users can open the deployed link on a phone without installing Python, OpenCV, or YOLO.

## Features

- Live occupancy dashboard
- Mobile-first video capture interface
- Phone camera recording
- Screen-share recording where supported
- MP4 and WebM video upload
- Authorized RTSP/IP camera registration
- Occupancy zones with polygon support
- AI person detection using OpenCV and YOLO
- Annotated preview frames with bounding boxes
- Durable background processing jobs
- Private temporary video storage
- Automatic raw-video cleanup after processing
- Supabase-backed metadata and occupancy snapshots
- Installable PWA support

## Architecture

```text
Phone / Laptop Browser
        |
        v
Next.js Frontend on Vercel
        |
        v
FastAPI Upload API
        |
        +----------------------+
        |                      |
        v                      v
Supabase Metadata       Private Video Storage
        |
        v
AI Worker
(OpenCV + YOLO)
        |
        v
Occupancy Snapshots
        |
        v
Live Dashboard
```

## Project Structure

```text
.
├── backend/
│   ├── app/
│   │   ├── detector.py
│   │   ├── main.py
│   │   ├── occupancy.py
│   │   ├── ratelimit.py
│   │   └── worker.py
│   ├── tests/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
├── web/
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── .env.example
├── supabase/
│   └── migrations/
├── docs/
├── IMPLEMENTATION_PLAN.md
└── WIMS_SETUP_REPORT.md
```

## Frontend

The frontend is built with:

- Next.js
- React
- TypeScript
- Tailwind CSS
- Supabase JavaScript client

### Frontend Routes

| Route | Description |
|---|---|
| `/` | Occupancy dashboard |
| `/capture` | Mobile capture and upload studio |
| `/manifest.webmanifest` | PWA manifest |

### Run Frontend Locally

```bash
cd web
npm install
cp .env.example .env.local
npm run dev
```

Open:

```text
http://localhost:3000
```

Set the API URL in `web/.env.local`:

```env
NEXT_PUBLIC_WIMS_API_URL=http://localhost:8000
```

### Frontend Checks

```bash
npm run typecheck
npm run lint
npm run build
```

## Backend API

The backend is built with:

- FastAPI
- Python
- Supabase
- OpenCV
- YOLO ONNX
- Pydantic Settings

### Main API Endpoints

| Endpoint | Description |
|---|---|
| `GET /health` | Service and configuration health |
| `GET /v1/sources` | List registered sources |
| `POST /v1/sources` | Register a capture or RTSP source |
| `POST /v1/jobs/upload` | Upload a video and create a processing job |
| `GET /v1/jobs/{job_id}` | Get processing status |
| `GET /v1/jobs/{job_id}/preview` | Get annotated AI preview |
| `GET /v1/zones` | List occupancy zones |
| `POST /v1/zones` | Create a zone |
| `GET /v1/occupancy` | Get the latest public occupancy data |

Capture, upload, job-status, and preview requests require the configured beta pairing header:

```text
X-WIMS-Capture-Key
```

### Run Backend Locally

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Start the API:

```bash
uvicorn app.main:app --reload --port 8000
```

Start the AI worker separately:

```bash
python -m app.worker --mode all
```

Available worker modes:

```bash
python -m app.worker --mode jobs
python -m app.worker --mode stream
python -m app.worker --mode all
python -m app.worker --mode jobs --once
```

### Backend Tests

```bash
python -m compileall -q app
python -m pytest tests -q
```

## Environment Variables

### Frontend

```env
NEXT_PUBLIC_WIMS_API_URL=https://your-api-domain.example
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
```

Never put backend secrets in frontend variables.

### Backend

```env
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=

SUPABASE_VIDEO_BUCKET=wims-temporary-videos
SUPABASE_PREVIEW_BUCKET=wims-job-previews

CORS_ORIGINS=https://where-is-my-space-wims.vercel.app

MAX_UPLOAD_MIB=100
UPLOAD_TTL_MINUTES=30
TEMP_UPLOAD_DIR=/tmp/wims-upload-staging

RATE_LIMIT_PER_MINUTE=120
UPLOAD_RATE_LIMIT_PER_MINUTE=10

WIMS_CAPTURE_ACCESS_CODE=
WIMS_SOURCE_ENCRYPTION_KEY=

YOLO_MODEL_PATH=models/yolov5s.onnx
YOLO_MODEL_URL=https://github.com/ultralytics/yolov5/releases/download/v7.0/yolov5s.onnx
DETECTION_CONFIDENCE=0.35
DETECTION_IOU=0.45
FRAME_STRIDE=5
MAX_SAMPLED_FRAMES=60
POLL_SECONDS=5
STALE_CLAIM_MINUTES=30
KEEP_RAW_VIDEO=false
STREAM_INTERVAL_SECONDS=10
```

Never expose these values:

- `SUPABASE_SERVICE_ROLE_KEY`
- `WIMS_CAPTURE_ACCESS_CODE`
- `WIMS_SOURCE_ENCRYPTION_KEY`

## Supabase Setup

Apply the following migrations in order:

```text
supabase/migrations/20261010150000_initial_wims_schema.sql
supabase/migrations/20261010160000_wims_capture_sources.sql
supabase/migrations/20261017120000_wims_ai_worker.sql
```

The migrations create:

- Locations
- Occupancy zones
- Processing jobs
- Occupancy snapshots
- Video source registry
- Worker job-claiming fields
- Private temporary video bucket
- Private AI preview bucket
- Row-level security policies
- Required indexes and constraints

### Supabase Security

- Raw videos are stored in private storage.
- RTSP URLs are encrypted before being stored.
- Browser clients cannot access service-managed jobs.
- Browser clients cannot access saved RTSP URLs.
- Raw videos are deleted after verified processing.
- Only derived occupancy metadata is retained.

## AI Worker

The AI worker:

1. Claims queued jobs atomically.
2. Recovers stale jobs from crashed workers.
3. Downloads and verifies the pinned YOLO model.
4. Samples video frames using OpenCV.
5. Detects people.
6. Applies optional occupancy-zone polygons.
7. Calculates peak occupancy.
8. Uploads an annotated preview to private storage.
9. Saves occupancy snapshots.
10. Deletes the raw video after successful processing.

A job is marked `completed` only after processing results have been persisted successfully.

## Deployment Status

### Frontend

- Platform: Vercel
- Project: `where-is-my-space-wims`
- Repository: `MayanKiz/Where_Is_My_Space`
- Root directory: `web/`
- Status: Deployed

### Backend and Worker

The FastAPI backend and AI worker must run on a persistent service that supports:

- Docker or Python
- Long-running processes
- Environment secrets
- Health checks
- Automatic restarts
- Persistent worker execution

The backend and worker are not deployed until a suitable persistent host and production secrets are configured.

## Production Setup Checklist

- [x] Repository implementation audited
- [x] Frontend TypeScript checks passed
- [x] Frontend lint passed
- [x] Frontend production build passed
- [x] Backend compilation passed
- [x] Backend unit tests passed
- [x] Supabase project verified
- [x] All three Supabase migrations applied
- [x] RLS and private storage verified
- [x] Correct Vercel project created
- [x] Frontend deployed to Vercel
- [ ] Backend API deployed
- [ ] AI worker deployed
- [ ] Production environment variables configured
- [ ] End-to-end upload and AI processing tested
- [ ] Live RTSP camera tested
- [ ] Production-grade authentication added

## Privacy and Safety

Use only camera footage that you are authorized to capture.

WIMS does not use face recognition. The system stores occupancy metadata instead of biometric identities. Raw video should be temporary and deleted after processing.

Do not commit:

- `.env` files
- Service-role keys
- API tokens
- Capture pairing codes
- Encryption keys
- Private camera URLs

## Documentation

Additional documentation is available in the [`docs/`](docs/) directory.

The complete setup audit is available in [`WIMS_SETUP_REPORT.md`](WIMS_SETUP_REPORT.md).

## License

See [`LICENSE`](LICENSE).
```
