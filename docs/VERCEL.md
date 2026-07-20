# Vercel — office-cp-ofce

## Bind GitHub repo

1. Vercel Dashboard → Add New Project → Import `office-cp-ofce`
2. **Root Directory** = `web`
3. Framework Preset = Next.js
4. Production Branch = `main` (or `master` until renamed)

## Environment variables (Production + Preview)

| Name | Value |
|------|--------|
| `OFCE_ENV` | `office` |
| `NEXT_PUBLIC_SUPABASE_URL` | 办公室 Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | service role（仅服务端） |
| `OFCE_ADMIN_PASSWORD` | 后台口令 |

Do **not** reuse home-PC Supabase keys. Project name on Supabase must be `office-cp-ofce`.

## After first push

```powershell
cd web
npm install
npm run build
```

Then push to GitHub; Vercel auto-deploys when the repo is linked.
