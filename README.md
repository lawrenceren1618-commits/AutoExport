# AutoExport

办公室端：订单 / 出货 / 货代 / 报关 — 自动化导出与云端后台。

## 与家里项目隔离

| 平台 | 名称 |
|------|------|
| GitHub | `AutoExport` |
| Vercel | 同名项目，Root Directory = `web` |
| Supabase | 独立项目 `AutoExport` |

Git 提交身份（本仓库 local）：**Office CP** / `lawrenceren1618@gmail.com`。

**推送认证**：办公室用 SSH 别名 `github.com-autoexport`（与家里默认 `github.com` 密钥分离）。材料：[docs/ssh/](docs/ssh/)。

## 快速开始

### 1. GitHub remote（办公室 SSH）

1. 公钥已在 GitHub（或见 `docs/ssh/*.pub`）
2. 网页新建 Private 仓库 **`AutoExport`**
3. 绑定 remote：

```powershell
git remote add origin git@github.com-autoexport:lawrenceren1618-commits/AutoExport.git
git branch -M main
git add .
git commit -m "Initial AutoExport scaffold"
git push -u origin main
ssh -T git@github.com-autoexport
```

### 2–4. Supabase + Vercel

见 [docs/CLOUD_LINK.md](docs/CLOUD_LINK.md)。

1. Supabase **新建**项目名 `AutoExport` → 跑 `supabase/migrations/…init.sql` → 复制密钥  
2. `web/.env.local`：`AUTOEXPORT_ENV=office` + 办公室密钥  
3. Vercel Import 仓库 `AutoExport`，**Root Directory = `web`**

```powershell
cd web
copy .env.local.example .env.local
npm install
npm run dev
```

- `/admin/progress` 目标树（仅后台）  
- `/admin/master-import` 总表 H01  

## 业务架构

[Templates/Architecture_Modules_Handshake.md](Templates/Architecture_Modules_Handshake.md)
