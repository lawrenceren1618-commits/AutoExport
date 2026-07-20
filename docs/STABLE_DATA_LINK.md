# AutoExport：稳定数据链路（推荐做法）

## 推荐架构（最稳）

```text
本机 Cursor / 总表文件
        │
        │  HTTPS（后台 API）
        ▼
   Vercel（web）  ──service_role──►  Supabase Postgres（权威库）
        ▲
        │  Git push（代码）
   GitHub AutoExport
```

| 传什么 | 走哪条路 | 不要用 |
|--------|----------|--------|
| **业务数据**（总表、沉淀、草稿、进度） | **Supabase**（经 Vercel API 或本机填好的 `.env.local`） | 飞书当主库、Excel 当唯一真相、邮件传表长期存 |
| **代码** | GitHub → Vercel 自动部署 | 手工拖文件夹上服务器 |
| **密钥** | Vercel Env + 本机 `.env.local` | 写进仓库、写进飞书 |

原则：**Supabase = 唯一权威数据源**；本地 `1_Input_Raw` 只是上传前暂存；对照/终审都读库。

---

## 三步把链路接稳

### 1. Supabase（已建项目后）

1. SQL Editor 执行仓库内：`supabase/migrations/20260720000000_init_ofce.sql`
2. **Settings → API** 复制：
   - Project URL → `NEXT_PUBLIC_SUPABASE_URL`
   - `anon` → `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - `service_role` → `SUPABASE_SERVICE_ROLE_KEY`（仅服务端）
3. 本机 `web/.env.local` 与 **Vercel → AutoExport → Environment Variables** 填**同一套办公室密钥**，并加上：
   - `OFCE_ENV=office`
   - `OFCE_ADMIN_PASSWORD=你的口令`

Production **和** Preview 都勾选，避免预览环境连错库。

### 2. Vercel

- Import 仓库 **AutoExport**
- **Root Directory = `web`**
- Deploy 成功后，数据写入走站点上的 `/api/master-import`（服务端用 service_role），比浏览器直连 anon 更稳、权限更可控。

### 3. 传总表（H01）

稳定顺序：

1. 打开已部署站点或本地 `npm run dev` → `/admin/login`
2. **人工总表导入** → 先「仅预览」核对行列
3. 再点「我已确认，写入沉淀库」→ 写入 `settled_*` 表

不要：直接把 Excel 丢进 Supabase Storage 当数据库用；大文件可先放 Storage，但**结构化字段仍要进表**。

---

## 为什么这样更稳

1. **TLS + 官方 SDK**：Vercel ↔ Supabase 用 HTTPS，比自建 FTP/网盘可靠  
2. **密钥隔离**：`service_role` 只在 API 路由，前端拿不到  
3. **H01 确认闸门**：预览 ≠ 入库，减少脏数据  
4. **办公室 / 家里隔离**：独立 Supabase 项目 + `OFCE_ENV=office`，避免串库  
5. **代码与数据分离**：改代码靠 Git；改数据靠库，互不影响  

---

## 自检清单

- [ ] migration 已跑，能在 Table Editor 看到 `settled_products` 等表  
- [ ] `.env.local` 里 URL 属于 **AutoExport** 项目（不是家里项目）  
- [ ] Vercel 环境变量与本地一致  
- [ ] `/admin/master-import` 预览成功，确认入库后 Table 有行  
- [ ] 后台口令在生产环境已设置（非默认 `change-me`）  

卡在某一步时，把报错原文（脱敏后）发我即可。
