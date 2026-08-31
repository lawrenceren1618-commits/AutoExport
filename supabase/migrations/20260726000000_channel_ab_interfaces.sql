-- Channel A/B + interface registry (cloud placeholders)
-- Heavy binaries stay in Storage; this stores interface metadata + settled snapshot pointer.
-- Apply after 20260722010000_schema_autoexport.sql

create schema if not exists autoexport;

create table if not exists autoexport.data_source_interfaces (
  id text primary key,
  task text,
  needs text,
  channel text check (channel is null or channel in ('A', 'B', 'shared')),
  module text,
  obtain jsonb not null default '{}'::jsonb,
  cloud jsonb not null default '{"status":"pending_cloud"}'::jsonb,
  updated_at timestamptz not null default now()
);

comment on table autoexport.data_source_interfaces is
  'Mirror of Scripts/data_source_interfaces.json entries; GitHub remains source for code; this table for runtime/cloud lookup.';

create table if not exists autoexport.settled_config (
  key text primary key,
  value jsonb not null,
  source_file text not null default 'Scripts/settled_knowledge_db.json',
  confirmed_at date,
  updated_at timestamptz not null default now()
);

comment on table autoexport.settled_config is
  'Flattened confirmed_defaults / entities slices from settled_knowledge_db; fundamental DB sync target.';

create table if not exists autoexport.user_io_projects (
  project_id text primary key,
  entity_code text,
  status text not null default 'scaffold',
  black_box_relpath text,
  gate_final text not null default 'WAIT',
  meta jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table autoexport.user_io_projects is
  'Channel A project registry; file blobs in Storage buckets user-io-in / user-io-out (pending).';

grant select on autoexport.data_source_interfaces to anon, authenticated;
grant select on autoexport.settled_config to anon, authenticated;
grant select on autoexport.user_io_projects to anon, authenticated;
grant all on autoexport.data_source_interfaces to service_role;
grant all on autoexport.settled_config to service_role;
grant all on autoexport.user_io_projects to service_role;
