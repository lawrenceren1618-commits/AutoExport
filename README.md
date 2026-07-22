# AutoExport

**本机总文件夹名：`AutoExport`**  
**本机路径：`D:\.cursor\Cursor-projects\AutoExport`**

订单 / 出货 / 货代 / 报关 — 本地脚手架 + 云端后台。

## 命名约定

| 项 | 值 |
|----|-----|
| 总文件夹 / GitHub / Vercel / Supabase | **AutoExport** |
| 本机绝对路径 | `D:\.cursor\Cursor-projects\AutoExport` |
| Git 提交人 | **Office CP**（不改） |
| 办公室 SSH | **github.com-office-cp** |
| 历史旧名（勿再用） | `Order_Freight_Customs_Export` / `office-cp-ofce` |

## Git

```powershell
cd D:\.cursor\Cursor-projects\AutoExport
git remote -v
# git@github.com-office-cp:lawrenceren1618-commits/AutoExport.git
```

## Supabase / Vercel

见 [docs/CLOUD_LINK_OFFICE.md](docs/CLOUD_LINK_OFFICE.md)、[docs/STABLE_DATA_LINK.md](docs/STABLE_DATA_LINK.md)。

端到端发货流水线：[Templates/End_to_End_Shipment_Pipeline.md](Templates/End_to_End_Shipment_Pipeline.md)。  
旁注：同级 `_workspace_archive_AutoExport_20260720` 不是业务仓，见 [docs/WORKSPACE_ARCHIVE.md](docs/WORKSPACE_ARCHIVE.md)。

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
