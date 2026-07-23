-- AutoExport schema isolation (one Supabase project, multiple apps)
-- This app: schema autoexport. Other apps: their own schemas (e.g. home_app).
--
-- After running: Supabase Dashboard -> Settings -> API
--   Exposed schemas: add autoexport
--   (optional) Extra search path: autoexport, public

create schema if not exists autoexport;

comment on schema autoexport is
  'AutoExport (office) app data only. Isolate from other apps in this Supabase project.';

-- Move tables from public to autoexport if legacy migrations created them in public (idempotent)
do $$
declare
  t text;
begin
  foreach t in array array[
    'settled_products',
    'settled_packing',
    'settled_fnsku',
    'master_table_imports',
    'draft_documents',
    'cross_check_logs',
    'progress_nodes',
    'fba_warehouse_headers'
  ]
  loop
    if exists (
      select 1 from information_schema.tables
      where table_schema = 'public' and table_name = t
    ) and not exists (
      select 1 from information_schema.tables
      where table_schema = 'autoexport' and table_name = t
    ) then
      execute format('alter table public.%I set schema autoexport', t);
    end if;
  end loop;
end $$;

grant usage on schema autoexport to postgres, anon, authenticated, service_role;
grant all on all tables in schema autoexport to postgres, service_role;
grant select on all tables in schema autoexport to anon, authenticated;
grant all on all sequences in schema autoexport to postgres, service_role;

alter default privileges in schema autoexport
  grant all on tables to postgres, service_role;
alter default privileges in schema autoexport
  grant select on tables to anon, authenticated;