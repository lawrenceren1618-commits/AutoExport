# Supabase — AutoExport

1. 新建（或使用）项目，名称：**AutoExport**（勿复用家里项目）
2. SQL Editor **依次**执行：  
   - [`supabase/migrations/20260720000000_init_ofce.sql`](../supabase/migrations/20260720000000_init_ofce.sql)  
   - [`supabase/migrations/20260722000000_fba_warehouse_headers.sql`](../supabase/migrations/20260722000000_fba_warehouse_headers.sql)（FBA 仓头/追踪码）  
   → SQL 只在这里跑，**不要**写进 `.env`
3. Settings → API：把 URL / anon / service_role **分别**粘到 `web/.env.local` 对应等号右侧
4. `OFCE_ENV=office`
5. 后台作业页：`/admin/fba-track`（上传外箱贴/截图 → 识别仓头 → 手填追踪码）
