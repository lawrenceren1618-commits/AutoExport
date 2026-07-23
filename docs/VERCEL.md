# Vercel — AutoExport

1. Import GitHub repository **`AutoExport`**
2. **Root Directory** = `web`
3. Framework = Next.js; Production Branch = `main`
4. Environment variables (match `web/.env.local`, Production + Preview):

| Name | Value |
|------|--------|
| `OFCE_ENV` | `office` |
| `OFCE_ADMIN_PASSWORD` | Your admin password |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase → Settings → API → Project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | anon public |
| `SUPABASE_SERVICE_ROLE_KEY` | service_role |
| `NEXT_PUBLIC_SUPABASE_SCHEMA` | `autoexport` (optional; code defaults to this) |

Do not use keys from a home-PC Supabase project. Supabase and Vercel project names should both be **AutoExport**.

**Supabase side:** Settings → API → **Exposed schemas** must include `autoexport` so PostgREST and `@supabase/supabase-js` can query app tables. Multi-app: other Vercel deployments on the same Supabase project set their own `NEXT_PUBLIC_SUPABASE_SCHEMA`.
