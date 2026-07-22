# AutoExport：Supabase + Vercel 链接

| 项 | 值 |
|----|-----|
| **总文件夹（本机）** | `D:\.cursor\Cursor-projects\AutoExport` |
| GitHub / Vercel / Supabase 项目名 | **AutoExport** |
| Git 提交人 | **Office CP**（office-cp）— 不改 |
| 办公室 SSH | **github.com-office-cp** |

旧名 `Order_Freight_Customs_Export` / `office-cp-ofce` 仅作历史；**一律以 AutoExport 为准**。若旧文件夹还在，确认无用后可删除，避免开错窗口。

---

## GitHub（已完成可跳过）

```powershell
cd D:\.cursor\Cursor-projects\AutoExport
ssh -T git@github.com-office-cp
git remote -v
# 应为：git@github.com-office-cp:lawrenceren1618-commits/AutoExport.git
```

---

## Supabase

1. 项目名：**AutoExport**
2. SQL Editor 执行：`supabase/migrations/20260720000000_init_ofce.sql`（这是建表，**不要**贴进 `.env`）
3. Settings → API，把下面三项**值**粘到 `web/.env.local` 等号右侧：
   - Project URL → `NEXT_PUBLIC_SUPABASE_URL`
   - anon public → `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - service_role → `SUPABASE_SERVICE_ROLE_KEY`
4. `OFCE_ENV=office`；`OFCE_ADMIN_PASSWORD=` 你的后台口令

---

## Vercel

1. Import 仓库 **AutoExport**
2. Root Directory = **`web`**
