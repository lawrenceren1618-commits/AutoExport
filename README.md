# AutoExport

办公室端项目总文件夹名：**AutoExport**。

订单 / 出货 / 货代 / 报关 — 本地脚手架 + 云端后台。

## 命名约定（请分清）

| 项 | 值 | 说明 |
|----|-----|------|
| **总文件夹 / 仓库 / Vercel / Supabase 项目名** | `AutoExport` | 产品与云端项目名 |
| **Git 提交人** | `Office CP`（office-cp） | **不改**；仅影响 commit 作者显示 |
| **办公室 SSH 别名** | `github.com-office-cp` | 区分家里机推送，与提交人一致保留 office-cp |

## 快速开始

### GitHub（SSH 仍用 office-cp 别名）

```powershell
cd C:\Users\Administrator\.cursor\Cursor-projects\AutoExport
ssh -T git@github.com-office-cp
git remote add origin git@github.com-office-cp:lawrenceren1618-commits/AutoExport.git
git branch -M main
git add .
git commit -m "Initial AutoExport scaffold"
git push -u origin main
```

### Supabase / Vercel

项目名均建为 **`AutoExport`**（勿与家里项目同名）。详见 [docs/CLOUD_LINK_OFFICE.md](docs/CLOUD_LINK_OFFICE.md)。

Vercel Root Directory = `web`。

本地：

```powershell
cd web
copy .env.local.example .env.local
npm install
npm run dev
```

## 业务架构

[Templates/Architecture_Modules_Handshake.md](Templates/Architecture_Modules_Handshake.md)
