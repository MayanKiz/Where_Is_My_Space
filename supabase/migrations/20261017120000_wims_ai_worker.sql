-- WIMS AI worker support: per-source zones, durable job claiming, and a private
-- preview bucket for annotated frames. Apply after 20261010160000_wims_capture_sources.sql.

-- Link a registered source to the occupancy zone that its feed observes.
alter table public.video_sources
  add column if not exists zone_id uuid references public.zones(id) on delete set null;

create index if not exists video_sources_zone_idx
  on public.video_sources (zone_id)
  where zone_id is not null;

-- Allow the worker to mark actively analysed RTSP feeds.
alter table public.video_sources
  drop constraint if exists video_sources_status_check;
alter table public.video_sources
  add constraint video_sources_status_check
  check (status in ('registered', 'ready', 'connected', 'recording', 'processing', 'streaming', 'offline', 'error'));

-- Durable job claiming: workers claim with an atomic conditional update and a claim
-- timestamp, so a crashed worker's job can be reclaimed after a stale-claim timeout.
alter table public.processing_jobs
  add column if not exists claimed_by text;
alter table public.processing_jobs
  add column if not exists claimed_at timestamptz;
alter table public.processing_jobs
  add column if not exists attempt_count integer not null default 0;

create index if not exists processing_jobs_claimable_idx
  on public.processing_jobs (created_at)
  where status in ('received', 'queued');

-- Annotated preview frames (bounding boxes) live in their own private bucket
-- because the temporary video bucket only accepts video types.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('wims-job-previews', 'wims-job-previews', false, 10485760, array['image/jpeg'])
on conflict (id) do update
set public = false,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

comment on column public.processing_jobs.claimed_by is
  'Worker identity that claimed this job; combined with claimed_at to detect stale claims.';