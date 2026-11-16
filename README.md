# AKGEC Campus Occupancy Dashboard

A real-time occupancy dashboard adapted from the upstream campus occupancy project for **AKGEC**. The dashboard is organized into three campus areas: **Library**, **LT (Lecture Theatre)**, and **CS-IT Canteen**.

## Features

- Live occupancy cards with FREE, MODERATE, FULL, and OFFLINE states
- Separate Library, LT, and CS-IT Canteen sections
- Responsive student dashboard and protected admin panel
- Region and camera management from the admin panel
- FastAPI backend with WebSocket broadcasts
- YOLO-based people counting and optional reserved-seat detection for library cameras
- Local camera simulator for development without cameras

## Project layout

```text
.
├── backend/       FastAPI API, database, seed data, camera worker, simulator
├── counter/       Optional on-premise counter utility
├── src/           React + Vite dashboard and admin UI
├── index.html
├── package.json
└── render.yaml    Example backend deployment configuration
```

## Run locally

### 1. Start the backend

```bash
cd backend
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload
```

The API and interactive docs are available at `http://localhost:8000` and `http://localhost:8000/docs`. The backend seeds four Library regions, one LT region, and one CS-IT Canteen region when the database is empty.

### 2. Start the dashboard

In a second terminal, from the repository root:

```bash
npm install
npm run dev
```

Open the Vite URL shown in the terminal (normally `http://localhost:5173`). The frontend defaults to the local API and WebSocket endpoints. For a remote backend, set `VITE_API_BASE_URL` and `VITE_WS_URL` in a `.env.local` file before starting Vite. A mock-only offline admin login can be enabled with `VITE_DEMO_ADMIN_PASSWORD`; it is not server authentication and should not be used in production.

## Camera and simulator configuration

The camera IDs must match the region IDs created by the backend:

| Area | Camera ID | Dashboard section |
|---|---|---|
| Library cameras | `cam_01`–`cam_04` | `library` |
| Lecture Theatre | `cam_lt_01` | `lt` |
| CS-IT Canteen | `cam_canteen_01` | `canteen` |

Run a local mock feed with `python backend/ml_stub.py`. It posts simulated counts to `http://localhost:8000` by default. To use a different API, set `OCCUPANCY_API_BASE_URL`.

For real YOLO camera input, install the optional computer-vision dependencies with `pip install -r backend/requirements_cv.txt`, then run for example:

```bash
python backend/cv_camera.py --camera-id cam_lt_01 --source 0
# or run every camera configured in backend/cv_camera.py
python backend/cv_camera.py --multi
```

Use the `--backend` option or `OCCUPANCY_API_BASE_URL` environment variable when the API is not on localhost. Camera hardware, camera placement, capacities, and deployment settings must be configured for the actual campus environment; the sample occupancy counts are demo data, not measured live values.

## Checks

```bash
npm run build
```

Backend requirements are listed in `backend/requirements.txt`; computer-vision requirements are kept separately so the API can run without installing YOLO/PyTorch.

## Attribution

See [SOURCE_ATTRIBUTION.md](SOURCE_ATTRIBUTION.md) for the upstream project and asset acknowledgements. The upstream repository did not contain a tracked `LICENSE` file, so this copy does not claim an MIT license.
