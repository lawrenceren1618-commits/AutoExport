-- Cloud workspace jobs (B composition as sections; runtime = cloud)
-- Buckets expected (create in Dashboard if not exists):
--   job-uploads, job-outputs, label-source (read-only), templates

create schema if not exists autoexport;

create table if not exists autoexport.shipment_jobs (
  id uuid primary key default gen_random_uuid(),
  project_code text not null,
  entity_code text not null check (entity_code in ('C04', 'C07')),
  ship_date date,
  status text not null default 'open'
    check (status in ('open', 'processing', 'pre_final', 'gate_wait', 'final', 'archived', 'blocked')),
  gate_final text not null default 'WAIT'
    check (gate_final in ('WAIT', 'CONFIRMED', 'REJECTED')),
  meta jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (project_code)
);

create table if not exists autoexport.job_artifacts (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null references autoexport.shipment_jobs(id) on delete cascade,
  section_id text not null,
  direction text not null check (direction in ('in', 'out', 'archive')),
  file_name text not null,
  content_type text,
  byte_size bigint,
  sha256 text,
  storage_path text not null,
  save_mode text not null default 'upload_raw'
    check (save_mode in ('upload_raw', 'draft', 'pre_final', 'final', 'archive')),
  meta jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists job_artifacts_job_idx on autoexport.job_artifacts (job_id, section_id);

create table if not exists autoexport.job_handshake_log (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null references autoexport.shipment_jobs(id) on delete cascade,
  handshake_id text not null,
  ok boolean not null default false,
  payload jsonb not null default '{}'::jsonb,
  message text,
  created_at timestamptz not null default now()
);

grant select, insert, update on autoexport.shipment_jobs to authenticated;
grant select, insert, update, delete on autoexport.job_artifacts to authenticated;
grant select, insert on autoexport.job_handshake_log to authenticated;
grant all on autoexport.shipment_jobs to service_role;
grant all on autoexport.job_artifacts to service_role;
grant all on autoexport.job_handshake_log to service_role;
grant select on autoexport.shipment_jobs to anon;
grant select on autoexport.job_artifacts to anon;
