-- WIMS initial schema. Run this migration in the Supabase SQL editor or via Supabase CLI.
-- Raw MP4s belong in a private temporary bucket and must be deleted after processing.
-- The backend uses SUPABASE_SERVICE_ROLE_KEY; never expose it to the browser.

create extension if not exists pgcrypto;

create table if not exists public.locations (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  name text not null,
  campus_name text,
  is_public boolean not null default true,
  created_at timestamptz not null default now()
);

create table if not exists public.zones (
  id uuid primary key default gen_random_uuid(),
  location_id uuid not null references public.locations(id) on delete cascade,
  slug text not null,
  name text not null,
  description text,
  capacity integer not null check (capacity >= 0),
  -- Optional normalized image/video polygon: [[x1,y1], [x2,y2], ...], 0.0–1.0 coordinates.
  polygon jsonb,
  is_active boolean not null default true,
  is_public boolean not null default true,
  created_at timestamptz not null default now(),
  unique (location_id, slug)
);

create table if not exists public.processing_jobs (
  id uuid primary key default gen_random_uuid(),
  location_id uuid references public.locations(id) on delete set null,
  zone_id uuid references public.zones(id) on delete set null,
  source_type text not null default 'mp4'
    check (source_type in ('mp4', 'webcam', 'rtsp')),
  original_filename text,
  mime_type text,
  size_bytes bigint check (size_bytes is null or size_bytes >= 0),
  -- Private storage object key only; never expose it as a public URL.
  storage_path text,
  status text not null default 'received'
    check (status in ('received', 'queued', 'processing', 'completed', 'failed', 'expired')),
  progress_percent smallint not null default 0
    check (progress_percent between 0 and 100),
  error_code text,
  result_summary jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz,
  expires_at timestamptz,
  video_deleted_at timestamptz
);

create table if not exists public.occupancy_snapshots (
  id bigint generated always as identity primary key,
  zone_id uuid not null references public.zones(id) on delete cascade,
  job_id uuid references public.processing_jobs(id) on delete set null,
  occupied_count integer not null check (occupied_count >= 0),
  capacity_count integer not null check (capacity_count >= 0),
  available_count integer generated always as (greatest(capacity_count - occupied_count, 0)) stored,
  confidence numeric(5,4) check (confidence is null or (confidence >= 0 and confidence <= 1)),
  detector_version text,
  observed_at timestamptz not null default now()
);

create index if not exists zones_location_active_idx
  on public.zones (location_id, is_active);
create index if not exists processing_jobs_status_created_idx
  on public.processing_jobs (status, created_at desc);
create index if not exists processing_jobs_expiry_idx
  on public.processing_jobs (expires_at)
  where expires_at is not null;
create index if not exists occupancy_snapshots_zone_observed_idx
  on public.occupancy_snapshots (zone_id, observed_at desc);
create index if not exists occupancy_snapshots_job_idx
  on public.occupancy_snapshots (job_id);

alter table public.locations enable row level security;
alter table public.zones enable row level security;
alter table public.processing_jobs enable row level security;
alter table public.occupancy_snapshots enable row level security;

-- Public clients can read public location/zone metadata and derived occupancy only.
-- Writes and all job details remain server-side via the service role.
drop policy if exists "Public can read public locations" on public.locations;
create policy "Public can read public locations"
  on public.locations for select to anon, authenticated
  using (is_public = true);

drop policy if exists "Public can read active public zones" on public.zones;
create policy "Public can read active public zones"
  on public.zones for select to anon, authenticated
  using (
    is_public = true
    and is_active = true
    and exists (
      select 1 from public.locations l
      where l.id = location_id and l.is_public = true
    )
  );

drop policy if exists "Public can read occupancy for public zones" on public.occupancy_snapshots;
create policy "Public can read occupancy for public zones"
  on public.occupancy_snapshots for select to anon, authenticated
  using (
    exists (
      select 1 from public.zones z
      join public.locations l on l.id = z.location_id
      where z.id = zone_id and z.is_public = true and z.is_active = true and l.is_public = true
    )
  );

revoke all on public.processing_jobs from anon, authenticated;
grant select on public.locations, public.zones, public.occupancy_snapshots to anon, authenticated;
grant all on public.locations, public.zones, public.processing_jobs, public.occupancy_snapshots to service_role;
grant usage, select on all sequences in schema public to service_role;

-- A private bucket is the temporary hand-off between the web app and the processing worker.
-- Backend uploads/deletes use the service role; there are no public object policies.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('wims-temporary-videos', 'wims-temporary-videos', false, 104857600, array['video/mp4'])
on conflict (id) do update
set public = false,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

comment on table public.processing_jobs is
  'Server-managed processing jobs. Client roles cannot read or write this table.';
comment on table public.occupancy_snapshots is
  'Derived occupancy metadata only; no video frames or biometric identifiers.';
