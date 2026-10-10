-- Add source management for the mobile WIMS Capture app.
-- Apply after 20261010150000_initial_wims_schema.sql.

create table if not exists public.video_sources (
  id uuid primary key default gen_random_uuid(),
  location_id uuid references public.locations(id) on delete set null,
  name text not null check (char_length(name) between 1 and 120),
  source_type text not null
    check (source_type in ('phone_camera', 'screen_share', 'uploaded_video', 'rtsp_camera')),
  status text not null default 'registered'
    check (status in ('registered', 'ready', 'connected', 'recording', 'processing', 'offline', 'error')),
  device_label text,
  -- URL is encrypted by the API service before it ever reaches this column.
  -- Never return this column to browser clients.
  stream_url_ciphertext text,
  metadata jsonb not null default '{}'::jsonb,
  last_seen_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.processing_jobs
  add column if not exists source_id uuid references public.video_sources(id) on delete set null;

alter table public.processing_jobs
  drop constraint if exists processing_jobs_source_type_check;

alter table public.processing_jobs
  add constraint processing_jobs_source_type_check
  check (source_type in ('mp4', 'webcam', 'rtsp', 'phone_camera', 'screen_share', 'uploaded_video'));

create index if not exists video_sources_location_created_idx
  on public.video_sources (location_id, created_at desc);
create index if not exists video_sources_type_status_idx
  on public.video_sources (source_type, status);
create index if not exists processing_jobs_source_created_idx
  on public.processing_jobs (source_id, created_at desc);

alter table public.video_sources enable row level security;
revoke all on public.video_sources from anon, authenticated;
grant all on public.video_sources to service_role;

update storage.buckets
set public = false,
    file_size_limit = 104857600,
    allowed_mime_types = array['video/mp4', 'video/webm']
where id = 'wims-temporary-videos';

comment on table public.video_sources is
  'Metadata for sources added through WIMS Capture. RTSP URLs are encrypted server-side and never returned to clients.';
comment on column public.video_sources.stream_url_ciphertext is
  'Fernet-encrypted RTSP/RTSPS URL; requires WIMS_SOURCE_ENCRYPTION_KEY to register network cameras.';
