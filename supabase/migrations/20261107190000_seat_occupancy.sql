-- Optional Supabase mirror for deployments that need seat data outside local SQLite.
create table if not exists public.seats (
  id bigint generated always as identity primary key,
  label text not null unique,
  x1 double precision not null, y1 double precision not null,
  x2 double precision not null, y2 double precision not null,
  status text not null default 'EMPTY' check (status in ('EMPTY', 'OCCUPIED', 'RESERVED')),
  created_at timestamptz not null default now()
);

create table if not exists public.seat_sessions (
  id bigint generated always as identity primary key,
  seat_id bigint not null references public.seats(id) on delete cascade,
  start_time timestamptz not null,
  end_time timestamptz,
  duration_minutes numeric(10,2)
);
