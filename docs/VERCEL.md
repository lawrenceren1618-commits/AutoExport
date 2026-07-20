# Vercel — AutoExport

1. Import GitHub 仓库 **`AutoExport`**
2. **Root Directory** = `web`
3. Framework = Next.js；Production Branch = `main`
4. 环境变量（与 `web/.env.local` 一致，Production + Preview）：

| Name | 值从哪来 |
|------|----------|
| `OFCE_ENV` | `office` |
| `OFCE_ADMIN_PASSWORD` | 你的后台口令 |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase API → Project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | anon public |
| `SUPABASE_SERVICE_ROLE_KEY` | service_role |

勿使用家里项目的密钥。Supabase / Vercel 项目名均为 **AutoExport**。
