## WIMS implementation plan (working document)

We are building the actual project in this repository, not just planning it.

### Product goal
Where Is My Space? helps campus users find available study spaces. First end-to-end demo: user uploads an MP4 → local Python/FastAPI processes it → computer vision produces labelled detection/occupancy results → only useful metadata is written to Supabase → the web dashboard shows results and timestamps.

### Agreed constraints
- Developer machine: laptop/PC.
- First input: uploaded recorded MP4; webcam and authorized campus CCTV are later sources.
- Supabase from the start for zone configuration and occupancy metadata.
- Next.js frontend can be hosted on Vercel; Python video processing is a separate service and is not assumed to run on Vercel.
- No face recognition. Raw videos are temporary processing inputs and must not be persisted by default.
- Keep each meaningful change in its own Git commit.
- Do not describe mock numbers as live, and do not claim features/deployment until verified.

### Implementation sequence
1. **Frontend scaffold**: add a Next.js + TypeScript + Tailwind app under `web/`, preserving current docs. Verify local startup.
2. **Dashboard UI**: WIMS dashboard, clear “demo/not connected” status, source upload panel, zones and occupancy cards. Mock examples must be explicitly labelled.
3. **Supabase schema**: locations, zones/seats configuration, occupancy snapshots and processing jobs; apply RLS and use server-side credentials only where appropriate. Verify insert/read against a real project.
4. **Python API skeleton**: FastAPI health route, upload size/type validation, temporary file handling, cleanup. Verify with a small MP4.
5. **Vision pipeline**: OpenCV + YOLO person detection, bounding-box preview and counts. Treat “person count” separately from exact chair occupancy.
6. **Zone occupancy**: configurable polygons/seat areas and explicit occupancy-estimation rules; persist counts and timestamps to Supabase.
7. **Dashboard integration**: real processing-job status and processed occupancy updates; no fake live values.
8. **Verification and deployment**: test frontend, API, database, upload error cases, cleanup and responsive UI. Deploy frontend and backend separately only after tests pass.

### Acceptance criteria for the first implementation
- Existing `README.md` and `docs/` remain unchanged.
- A Next.js app lives in `web/`.
- A developer can install dependencies and start the app locally using its README instructions.
- No API keys or Supabase secrets are committed.
- This first change does not claim camera, upload, AI, database or deployment functionality yet.

### Immediate next action
Create the `web/` Next.js scaffold in this repo, commit that as a single focused change, then implement the dashboard UI in a separate commit.