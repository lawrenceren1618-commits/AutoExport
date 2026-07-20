# AutoExport

**本机总文件夹名：`AutoExport`**（路径：`...\Cursor-projects\AutoExport`）

订单 / 出货 / 货代 / 报关 — 本地脚手架 + 云端后台。

## 命名约定

| 项 | 值 |
|----|-----|
| 总文件夹 / GitHub / Vercel / Supabase | **AutoExport** |
| Git 提交人 | **Office CP**（不改） |
| 办公室 SSH | **github.com-office-cp** |

## Git

```powershell
cd C:\Users\Administrator\.cursor\Cursor-projects\AutoExport
git remote -v
# git@github.com-office-cp:lawrenceren1618-commits/AutoExport.git
```

## Supabase / Vercel

见 [docs/CLOUD_LINK_OFFICE.md](docs/CLOUD_LINK_OFFICE.md)、[docs/STABLE_DATA_LINK.md](docs/STABLE_DATA_LINK.md)。

本地环境变量模板：`web/.env.local`（等号后粘贴 API 密钥，不要粘 SQL）。

```powershell
cd web
npm install
npm run dev
```

- `/admin/progress` 工作总结（仅后台）
- `/admin/master-import` 总表 H01

## 业务架构

[Templates/Architecture_Modules_Handshake.md](Templates/Architecture_Modules_Handshake.md)

**新对话交接（复制提示词）：** [Templates/Next_Session_Handoff.md](Templates/Next_Session_Handoff.md)
