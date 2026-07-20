# 办公室端：Supabase + Vercel 链接与项目区�?

目标：与**家里电脑**上的项目完全隔离——不�?GitHub 仓库、不�?Supabase 项目、不�?Vercel 项目、不同环境变量�?

统一前缀�?*`office-cp-ofce`**

---

## 0. 先完�?GitHub（SSH 已加公钥后）

```powershell
cd C:\Users\Administrator\.cursor\Cursor-projects\AutoExport

# 自检办公�?SSH（应看到 Hi <你的用户�?!�?
ssh -T git@github.com-office-cp

# 若还没有远程仓库：在 GitHub 网页新建 Private 仓库 office-cp-ofce（不要勾�?README�?
# 本机 SSH 已验证用户：lawrenceren1618-commits
git remote add origin git@github.com-office-cp:lawrenceren1618-commits/office-cp-ofce.git
git branch -M main
git add .
git commit -m "Initial office-cp-ofce scaffold"
git push -u origin main
```

家里仓库继续用：`git@github.com:YOUR_USER/<家里仓库>.git`（不要用 `github.com-office-cp`）�?

---

## 1. Supabase（先建库，再�?Vercel 填密钥）

### 1.1 新建独立项目（不要打开家里那个�?

1. 打开 [https://supabase.com/dashboard](https://supabase.com/dashboard)
2. **New project**
3. 填写�?
   - **Name**：`office-cp-ofce`（必须与家里项目名不同）
   - **Database password**：另存密码管理器（与家里不同�?
   - **Region**：自选（可与家里不同�?
4. 等待项目 Ready

### 1.2 跑迁�?

1. 左侧 **SQL** �?**New query**
2. 打开本仓库文件：`supabase/migrations/20260720000000_init_ofce.sql`
3. 全选粘�?�?**Run**
4. 确认出现表：`settled_products`、`settled_packing`、`settled_fnsku`、`progress_nodes` �?

### 1.3 复制 API 密钥（仅办公室项目）

**Project Settings �?API**�?

| 复制�?| 环境变量�?|
|--------|------------|
| Project URL | `NEXT_PUBLIC_SUPABASE_URL` |
| `anon` `public` | `NEXT_PUBLIC_SUPABASE_ANON_KEY` |
| `service_role` `secret` | `SUPABASE_SERVICE_ROLE_KEY`（勿提交、勿给前端） |

### 1.4 本机 `.env.local`

```powershell
cd web
copy .env.local.example .env.local
# 用记事本打开 web\.env.local，填入上�?+�?
# OFCE_ENV=office
# OFCE_ADMIN_PASSWORD=你自己设的后台口�?
```

**隔离自检**：`OFCE_ENV` 必须�?`office`；URL/Key 必须来自名为 `office-cp-ofce` 的项目，禁止粘贴家里项目�?Key�?

---

## 2. Vercel（绑定办公室仓库�?

### 2.1 新建独立项目

1. 打开 [https://vercel.com/dashboard](https://vercel.com/dashboard)
2. **Add New�?�?Project**
3. **Import** GitHub 仓库 **`office-cp-ofce`**（不要选家里的仓库�?
4. 配置�?

| �?| �?|
|----|-----|
| Project Name | `office-cp-ofce`（可改显示名，建议一致） |
| **Root Directory** | **`web`**（点 Edit 选中�?|
| Framework | Next.js |
| Production Branch | `main` |

### 2.2 环境变量（Production + Preview 都勾选）

�?`.env.local` 相同�?

- `OFCE_ENV` = `office`
- `NEXT_PUBLIC_SUPABASE_URL` = 办公�?Project URL
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` = 办公�?anon
- `SUPABASE_SERVICE_ROLE_KEY` = 办公�?service_role
- `OFCE_ADMIN_PASSWORD` = 后台口令

### 2.3 Deploy

�?**Deploy**。成功后打开�?

- `/` 首页
- `/admin/login` �?`/admin/progress`（目标树�?
- `/admin/master-import`（总表 H01�?

---

## 3. 与家里项目对照表（贴在墙上）

| | 家里 | 办公�?|
|--|------|--------|
| GitHub 仓库 | 原有名字 | **`office-cp-ofce`** |
| SSH remote | `git@github.com:...` | **`git@github.com-office-cp:...`** |
| git 作�?| 家里习惯 | **`Office CP`** |
| Supabase 项目�?| 家里原名 | **`office-cp-ofce`** |
| Vercel 项目 | 家里原项�?| **新项目，�?office-cp-ofce，Root=`web`** |
| `OFCE_ENV` | （若有）勿用 office | **`office`** |

---

## 4. 常见踩坑

1. Vercel Root 忘了设成 `web` �?构建失败或找不到 Next 应用  
2. 把家�?Supabase Key 填进办公�?Vercel �?数据串项目；�?`OFCE_ENV=office` + 核对 URL 域名  
3. 只填 Production 没填 Preview �?PR 预览连错�? 
4. �?`service_role` 写进前端代码 �?禁止；只放服务器环境变量  

完成后把 checklist 勾掉：见 [DEPLOY_CHECKLIST.md](DEPLOY_CHECKLIST.md)�?
