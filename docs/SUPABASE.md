# Supabase — AutoExport

**Storage:** one Supabase project named **AutoExport**, with all app tables in PostgreSQL schema **`autoexport`** (not `public`). The same Supabase project can host other apps; each app uses its own schema.

## Dashboard (required)

Settings → API:

- **Exposed schemas:** must include `autoexport` (keep `public` if other apps need it).
- Optional **Extra search path:** `autoexport, public`

## Environment (web)

| Variable | Purpose |
|----------|---------|
| `NEXT_PUBLIC_SUPABASE_URL` | Project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | anon public |
| `SUPABASE_SERVICE_ROLE_KEY` | service_role (server only) |
| `NEXT_PUBLIC_SUPABASE_SCHEMA` | Optional; default in code is `autoexport` |
| `SUPABASE_DB_SCHEMA` | Server-only override for schema name |
| `OFCE_ENV` | `office` |

Copy keys from Settings → API into `web/.env.local` (never commit secrets).

## SQL Editor — migration order

**Greenfield** (no tables yet), run in order:

1. [`supabase/migrations/20260720000000_init_ofce.sql`](../supabase/migrations/20260720000000_init_ofce.sql) — schema `autoexport` + core tables  
2. [`supabase/migrations/20260722000000_fba_warehouse_headers.sql`](../supabase/migrations/20260722000000_fba_warehouse_headers.sql) — FBA warehouse headers  
3. *(Optional on greenfield)* [`supabase/migrations/20260722010000_schema_autoexport.sql`](../supabase/migrations/20260722010000_schema_autoexport.sql) — idempotent grants + public→autoexport move (no-op if step 1–2 already used `autoexport`)

**Already ran old migrations in `public`:** run step 3 **after** the two files above (or instead of re-running 1–2 if tables already exist in `public`). Step 3 moves tables from `public` to `autoexport` and applies grants.

Or use `supabase db push` from the repo root when the CLI is linked to this project.

## App routes

- Admin progress: `/admin/progress`
- FBA tracking: `/admin/fba-track`
