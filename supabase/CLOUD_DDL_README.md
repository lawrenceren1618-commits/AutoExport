-- AutoExport cloud DDL pack (run in Supabase SQL Editor as one script)
-- Isolation: cloud schema only; does not touch local disk.
-- Order: init → fba headers → schema move → channel interfaces → shipment jobs

\i is not available in Dashboard; paste contents of migrations in order, or run this combined file's sections.

-- ===== BEGIN 20260720000000 (excerpt: ensure schema) =====
create extension if not exists "pgcrypto";
create schema if not exists autoexport;
grant usage on schema autoexport to postgres, anon, authenticated, service_role;

-- If full init already applied, the following CREATE IF NOT EXISTS are no-ops.
-- Prefer running each file from supabase/migrations/ in date order in SQL Editor.

-- NOTE: This stub only ensures schema exists. For first-time projects, run ALL five
-- migration files from supabase/migrations/ in chronological order in the SQL Editor.
-- After DDL: Settings → API → Exposed schemas → include autoexport.
