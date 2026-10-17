# WIMS Production Setup Report

Date: 2026-10-17
Repository: `MayanKiz/Where_Is_My_Space`
Production branch: `main`
Verified commit: `6f56f9814e5ab61347392096cfbeb1396c312f09`

## 1. Completed checklist

- [x] Audited repository structure, README files, frontend, backend, migrations, tests, and CI workflows.
- [x] Confirmed the existing implementation is not a blank scaffold: Next.js frontend, FastAPI API, Supabase schema, durable AI worker, capture flow, dashboard, and CI are present.
- [x] Confirmed no committed environment files or service-role credentials.
- [x] Ran frontend TypeScript, ESLint, and production build successfully.
- [x] Ran backend syntax checks and all 18 unit tests successfully.
- [x] Confirmed the backend health route returns a safe configuration status when production credentials are absent.
- [x] Inspected the existing Vercel project. It was linked to `MayanKiz/Where_Is_My_Space_final`, not the requested repository.
- [x] Created the correct Vercel project `where-is-my-space-wims`, linked to `MayanKiz/Where_Is_My_Space`, with `web/` as the root directory.
- [x] Verified the new Vercel production deployment reached `READY`.
- [x] Inspected the production Supabase project `where-is-my-space` (`eplaxnykyyhboioxlifh`).
- [x] Applied the missing AI-worker migration safely; no destructive or duplicate schema operation was used.
- [x] Re-verified Supabase tables, columns, foreign keys, RLS flags, and migration history.

## 2. Supabase status

Project status: `ACTIVE_HEALTHY`

Recorded migrations:

| Repository migration | Supabase status |
|---|---|
| `20261010150000_initial_wims_schema.sql` | Applied; recorded as `initial_wims_schema` |
| `20261010160000_wims_capture_sources.sql` | Applied; recorded as `wims_capture_sources` |
| `20261017120000_wims_ai_worker.sql` | Applied during this task; recorded as `wims_ai_worker` (version `20261017061525`) |

Verified tables:

- `public.locations`
- `public.zones`
- `public.processing_jobs`
- `public.occupancy_snapshots`
- `public.video_sources`

Verified protections and worker fields:

- RLS enabled on all five application tables.
- Public roles can read only public locations, active public zones, and derived occupancy snapshots.
- `processing_jobs` and `video_sources` have no public policies and are inaccessible to `anon`/`authenticated` through the documented grants.
- `processing_jobs` includes `claimed_by`, `claimed_at`, and `attempt_count`.
- `video_sources` includes `zone_id` and the `streaming` status.
- Private storage buckets are configured by the migrations: `wims-temporary-videos` and `wims-job-previews`.

Supabase advisors reported:

- Security INFO: RLS-enabled `processing_jobs` and `video_sources` have no policies. This is intentional for the server-only tables and matches the migration's explicit grants.
- Performance INFO: foreign-key indexes on `processing_jobs.location_id` and `processing_jobs.zone_id` are not present; this is a future optimization, not a deployment blocker. Several indexes are currently unused because the production tables contain zero rows.

## 3. Frontend deployment

Vercel project: `where-is-my-space-wims`

Production URL: https://where-is-my-space-wims.vercel.app

Deployment status: `READY`
Deployment ID: `dpl_iSkPSiUT3iMb2gW9sz9r2M3e2uV7`
Deployment source: `MayanKiz/Where_Is_My_Space`, branch `main`, commit `6f56f9814e5ab61347392096cfbeb1396c312f09`
Root directory: `web/`

Important: the new Vercel project currently has **no environment variables**. Until `NEXT_PUBLIC_WIMS_API_URL` is set to a deployed HTTPS backend URL, the dashboard will use its documented sample-data fallback and capture uploads cannot reach the API.

## 4. Backend and AI worker

Backend API URL: **Not deployed**
Backend health-check status: **Not externally verifiable**
AI worker deployment: **Not deployed**
Processing test: **Not run against production**, because backend service credentials and a persistent worker host were not available in this session.

Local safe-failure check:

- `GET /health` returned HTTP 200 and correctly reported all three production configuration flags as false.
- `GET /v1/occupancy` and `GET /v1/zones` returned HTTP 503 with `SUPABASE_NOT_CONFIGURED`, rather than exposing data or claiming the service is live.

The repository's Dockerfile and separate worker command are present, but a host with persistent process support and the required environment secrets is still required. No worker-running claim is made.

## 5. Tests executed

Frontend (`web/`):

- `npm ci` — passed.
- `npm run typecheck` — passed.
- `npm run lint` — passed with one existing Next.js warning about using `<img>` for the AI preview.
- `npm run build` — passed; routes `/`, `/capture`, and `/manifest.webmanifest` generated successfully.
- npm reported dependency audit findings: 8 vulnerabilities (7 high, 1 critical). No `npm audit fix --force` was run because it could introduce breaking changes.

Backend (`backend/`):

- `python -m compileall -q app` — passed.
- `python -m pytest tests -q` — passed, 18 tests.
- FastAPI route smoke test — passed when run with the application lifespan.
- Worker import/CLI smoke checks are covered by the repository CI workflow and existing implementation.

Repository state after the audit: clean; no source changes or commits were created.

## 6. Exact manual actions remaining

1. Choose a persistent backend/worker host that supports the included Docker image and two processes (API and worker). Keep the API and worker on the same Supabase project.
2. Configure backend-only secrets from `backend/.env.example` on that host:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `WIMS_CAPTURE_ACCESS_CODE`
   - `WIMS_SOURCE_ENCRYPTION_KEY`
   - `CORS_ORIGINS=https://where-is-my-space-wims.vercel.app`
   - the documented bucket names and worker settings.
3. Run the API with `uvicorn app.main:app` and the worker with `python -m app.worker --mode all` (or separate managed services), then verify `/health` reports all required configuration flags as true.
4. Add the resulting API HTTPS origin to the Vercel production environment as `NEXT_PUBLIC_WIMS_API_URL`, then redeploy the frontend.
5. Create at least one location and public zone using the protected API or Supabase SQL editor.
6. Run an authorized synthetic MP4/WebM upload through `/capture`; verify job creation, worker processing, private preview access, snapshot persistence, and dashboard updates.
7. Apply hosting-level request-size limits, rate limiting, restart policies, and logs. Do not expose service-role credentials or the capture code in frontend variables.
8. For real RTSP testing, use only an authorized camera and remove/expire test data when finished.

No secrets should be pasted into chat. No billing approval or hosting credentials were available to complete the backend deployment automatically.
