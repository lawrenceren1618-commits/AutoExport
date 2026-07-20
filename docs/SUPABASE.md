# Supabase — office-cp-ofce

1. Create a **new** project named `office-cp-ofce` (do not reuse home projects).
2. SQL Editor → paste and run [`supabase/migrations/20260720000000_init_ofce.sql`](../supabase/migrations/20260720000000_init_ofce.sql).
3. Project Settings → API → copy URL + anon + service_role into `web/.env.local` and Vercel.

Isolation check: set `OFCE_ENV=office` in the app; home projects should use a different value if any.
