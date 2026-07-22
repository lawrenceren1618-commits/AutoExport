# Deploy checklist — AutoExport

逐步说明：[CLOUD_LINK_OFFICE.md](CLOUD_LINK_OFFICE.md) · [STABLE_DATA_LINK.md](STABLE_DATA_LINK.md)

**总文件夹 / 仓库 / Vercel / Supabase 项目名一律：`AutoExport`**  
本机路径：`D:\.cursor\Cursor-projects\AutoExport`  
提交人仍为 **Office CP**；SSH 别名仍为 **github.com-office-cp**。

- [x] 办公室公钥已加到 GitHub — 见 [ssh/](ssh/)
- [x] `ssh -T git@github.com-office-cp` 通过
- [x] GitHub 仓库 `AutoExport`；`origin` → `git@github.com-office-cp:lawrenceren1618-commits/AutoExport.git`；分支 `main`
- [x] **Supabase**：项目名 `AutoExport` → migration 已跑 → 本机试连通过
- [x] **Vercel**：Import `AutoExport`，Root Directory = **`web`**，已部署
- [ ] 线上冒烟：`/admin/login` → `/admin/progress`、`/admin/master-import`
- [ ] 人工总表 H01 确认入库
