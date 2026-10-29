# WIMS Project Audit

**Repository:** `MayanKiz/Where_Is_My_Space`  
**Audited checkout:** `main` at `5c99577` (`Rename recording.mp4 to Public/recording.mp4`)  
**Audit date:** 2026-10-30  
**Scope:** read-only GitHub inspection, local verification, narrowly scoped correctness fixes. No production database migration, deployment, push, reset, force-push, branch deletion, or credential change was performed.

## Executive summary

WIMS is a substantial prototype, not a blank scaffold. The repository contains a Next.js dashboard and Capture PWA, a FastAPI API, Supabase migrations with row-level security, a durable OpenCV/YOLO worker, an assistant with a privacy-filtered context, unit tests, Docker packaging, and GitHub Actions checks.

The core local code checks pass after two small correctness fixes made in this audit checkout:

- **Backend:** 21 tests passed; Python compilation and API/worker import smoke checks passed.
- **Frontend:** TypeScript, ESLint, and production build passed. ESLint reports one non-blocking `<img>` optimization warning.
- **CI:** GitHub read access confirmed recent successful workflow runs, but the most recent listed successful run predates the current `main` commit; current-head CI status should be checked after pushing or opening a PR.
- **Production:** The public Vercel frontend responded with HTTP 200 and rendered the WIMS page. The page displayed `Sample data`, confirming that a live backend feed is not currently configured or reachable from the deployed frontend. No externally reachable backend or live AI worker was verified.

## Implemented features verified in code

### Frontend

- Next.js 15 / React / TypeScript application under `web/`.
- Dashboard route `/` with explicit live-vs-sample labeling.
- Capture route `/capture` with phone camera recording, supported screen capture, MP4/WebM upload, and RTSP/RTSPS source registration.
- Upload progress, job polling, AI result display, annotated preview display, source listing, access-code gate, and responsive styling.
- PWA manifest at `/manifest.webmanifest`.
- API client for health, public zones, occupancy, sources, uploads, job status, previews, and assistant requests.

### Backend and AI

- FastAPI service with health, source, zone, upload, job, preview, occupancy, and assistant routes.
- Upload extension/MIME/container-signature validation, size limit, temporary staging, private object upload, expiry metadata, and rollback handling.
- Shared capture pairing code with constant-time comparison.
- RTSP URL validation and Fernet encryption at rest; encrypted URL is not returned to the browser.
- Sliding-window in-process rate limits.
- YOLO ONNX model loading with optional SHA-256 verification.
- OpenCV frame sampling, person detection, polygon-based occupancy estimation, peak/mean statistics, annotated JPEG generation, and raw-video cleanup after processing.
- Durable worker queue with job claims, stale-claim recovery, attempt limits, progress updates, failed-job states, and RTSP stream ingestion.
- Assistant context limited to derived occupancy metadata; no raw video, camera URL, or credentials are passed to Bedrock or the fallback.

### Data and security

- Supabase migrations define locations, zones, processing jobs, occupancy snapshots, video sources, private video storage, and private preview storage.
- RLS is enabled on application tables.
- Public roles can read only public locations, active public zones, and derived occupancy snapshots.
- Processing jobs and video sources are server-managed and revoked from `anon`/`authenticated` roles.
- Environment examples keep service-role keys, capture codes, and encryption keys backend-only.

## Changes made during this audit

1. **Normalized polygon validation:** changed `normalize_polygon` to reject coordinates outside the documented `0..1` normalized range. The previous implementation accepted `-0.5..1.5`, which could create zones outside the video frame despite the API documentation and error message promising `0..1` coordinates.
2. **Availability clamping:** changed the public occupancy response to clamp `available_count` at zero. A detector can count more people than the configured capacity; the database generated column already clamps this, but the API calculated `capacity - occupied` directly and could return a negative availability value.
3. **Regression coverage:** added tests for slightly out-of-range polygons. Existing tests and all new tests pass.

Modified files in the local audit checkout:

- `backend/app/occupancy.py`
- `backend/app/main.py`
- `backend/tests/test_wims.py`
- `PROJECT_AUDIT.md`

These changes are local only. They have not been committed or pushed.

## Partially implemented or unverified features

- The frontend is deployed and reachable, but the observed deployment shows sample data. The repository's setup report says `NEXT_PUBLIC_WIMS_API_URL` was not configured for the Vercel project at the time of that report.
- A backend API with public HTTPS reachability was not verified in this session.
- A persistent AI worker was not verified against a real Supabase project or production upload.
- Supabase migration files are present and documented, but live project access was not available for an independent current-state check.
- Real camera/RTSP ingestion was not tested because no authorized camera endpoint was provided.
- End-to-end browser capture → private upload → worker inference → snapshot → dashboard flow was not executed against live credentials.
- The shared capture access code is suitable for a beta pairing gate, not production-grade user identity or authorization.
- Rate limiting is in-process and should be supplemented with proxy/provider-level limits for production.
- Occupancy is a sampled person-count estimate, not seat-level occupancy or tracked identity-free trajectories.

## Findings and risks

### High priority deployment blockers

1. **No verified public backend/worker service.** The frontend cannot show live occupancy or process uploads until the API and worker run against the intended Supabase project.
2. **Required runtime secrets and configuration are external.** Backend deployment needs `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `WIMS_CAPTURE_ACCESS_CODE`, `WIMS_SOURCE_ENCRYPTION_KEY`, CORS origins, and worker settings. These must be configured through the hosting provider, never committed.
3. **Frontend API origin is not verified in production.** Set `NEXT_PUBLIC_WIMS_API_URL` to the deployed HTTPS API origin and redeploy after backend health is confirmed.
4. **Live data requires configured locations/zones and a successful processed job.** A deployed UI alone cannot produce real occupancy values.

### Medium priority engineering risks

- The Dockerfile runs API and worker in one process container, which is acceptable for a demo but less robust than separate managed services with independent scaling and restart behavior.
- Worker/model downloads require outbound network access and sufficient disk/CPU. Model startup and inference time should be measured on the selected host.
- `X-Forwarded-For` is used for the in-process rate-limit key. In production, the application should trust forwarded headers only when traffic is behind a known proxy or use a provider-aware client identity.
- The frontend intentionally uses a plain `<img>` for the dynamic preview, producing one Next.js lint warning. This is not a correctness failure but can be improved with an appropriate image strategy.
- The current checkout's `npm ci` reports 3 vulnerabilities (2 high, 1 critical). No force upgrade was run because dependency changes may be breaking; review with `npm audit`, update deliberately, and rerun the build.

### Low priority product limitations

- Peak person count can overestimate instantaneous occupancy when people move through a zone.
- No authentication, role management, reservations, or identity-aware audit trail exists yet.
- RTSP source health/last-seen behavior needs real-device validation.
- Public deployment status and configuration should be kept synchronized with the setup report; the report references an older verified commit than the current checkout.

## Verification evidence

### Local checks

```text
Backend:
- python3 -m compileall -q app                 PASS
- python3 -m pytest tests -q                   PASS (21 passed)
- API route smoke check                         PASS
- Worker import/settings smoke check            PASS

Frontend:
- npm ci                                       PASS
- npm run typecheck                            PASS
- npm run lint                                 PASS with 1 warning
- npm run build                                PASS
```

The frontend build generated routes `/`, `/capture`, and `/manifest.webmanifest`.

### GitHub connector and repository checks

The GitHub connector successfully accessed `MayanKiz/Where_Is_My_Space` and fetched repository metadata, root files, commits, pull requests, workflows, and Actions run history. The local clone was clean before audit edits and had no pre-existing uncommitted user changes.

The repository has active workflows:

- `.github/workflows/backend-checks.yml`
- `.github/workflows/web-checks.yml`

The latest observed successful web workflow was on commit `206916f`; a successful run for the current `5c99577` checkout was not observed in the fetched run list.

### Public deployment check

`https://where-is-my-space-wims.vercel.app` responded with HTTP 200 from Vercel during this audit. The rendered page included `Sample data`. This confirms frontend reachability, not backend, Supabase, worker, or end-to-end production health.

## Prioritized implementation checklist

### P0 — required before a credible live demo

- [ ] Deploy the FastAPI API to a public HTTPS host.
- [ ] Run the worker persistently on the same Supabase project; prefer a separate service if the host supports it.
- [ ] Configure backend secrets and production CORS without exposing them to the browser.
- [ ] Apply and verify all three Supabase migrations in order.
- [ ] Configure `NEXT_PUBLIC_WIMS_API_URL` in Vercel and redeploy.
- [ ] Create at least one public location and active zone.
- [ ] Run an authorized synthetic MP4/WebM upload and verify job completion, snapshot persistence, private preview access, cleanup, and dashboard refresh.

### P1 — production hardening

- [ ] Add provider-level rate limiting, request-size limits, timeouts, logs, health/readiness separation, and restart policies.
- [ ] Replace the shared beta code with proper authentication/authorization before broad access.
- [ ] Reconcile deployment documentation with the actual current commit and environment configuration.
- [ ] Review npm vulnerabilities and upgrade dependencies deliberately.
- [ ] Add integration tests with mocked Supabase storage/database boundaries and API validation cases.
- [ ] Verify forwarded-header handling behind the selected reverse proxy.

### P2 — accuracy and product expansion

- [ ] Test authorized RTSP cameras and source-health transitions.
- [ ] Add multi-frame tracking and calibrate occupancy semantics with real campus footage.
- [ ] Add seat-level or capacity-aware estimation only after validating the product definition.
- [ ] Add operational metrics for inference latency, queue age, failed jobs, and stale claims.

## Manual launch sequence

1. Provision a persistent HTTPS-capable backend/worker host.
2. Configure backend values from `backend/.env.example` through the host's secret manager.
3. Start the API with `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
4. Start the worker with `python -m app.worker --mode all` or run jobs and stream modes as separate services.
5. Confirm `/health` reports Supabase, capture access, and RTSP encryption configuration as enabled.
6. Set Vercel's `NEXT_PUBLIC_WIMS_API_URL` to the API origin and redeploy.
7. Apply the migrations in this order, if not already applied:
   - `20261010150000_initial_wims_schema.sql`
   - `20261010160000_wims_capture_sources.sql`
   - `20261017120000_wims_ai_worker.sql`
8. Create a location and zone, then run an authorized test upload through `/capture`.
9. Confirm that only completed worker results appear as AI results and that raw video is removed according to the configured retention policy.

## Final status

The codebase is locally verifiable and the frontend is publicly reachable, but WIMS is **not yet independently verified as a live end-to-end occupancy service**. The remaining blockers are deployment/configuration and real-environment validation rather than a missing application scaffold. No production action was taken during this audit.
