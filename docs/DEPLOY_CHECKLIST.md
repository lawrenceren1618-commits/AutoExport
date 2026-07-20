# Deploy checklist — office-cp-ofce

逐步说明：[CLOUD_LINK_OFFICE.md](CLOUD_LINK_OFFICE.md)

- [x] 办公室公钥已加到 GitHub（Title: `office-cp-ofce`）— 见 [ssh/](ssh/)
- [ ] `ssh -T git@github.com-office-cp` 认证成功（首次需 known_hosts）
- [ ] 创建私有仓库 `office-cp-ofce`；`git remote add origin git@github.com-office-cp:YOUR_USER/office-cp-ofce.git` 并 push
- [ ] **Supabase**：新建项目 `office-cp-ofce`（勿用家里项目）→ 跑 migration → 复制 API 密钥
- [ ] `web/.env.local`：`OFCE_ENV=office` + 办公室 URL/anon/service_role + 后台口令
- [ ] **Vercel**：Import **本仓库** `office-cp-ofce`，Root Directory = **`web`**，环境变量与 `.env.local` 一致（Production+Preview）
- [ ] 部署后打开 `/admin/progress`、`/admin/master-import`
