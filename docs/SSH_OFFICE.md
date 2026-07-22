# 办公室 vs 家里：用 SSH 区分「哪台机器在推」，用 git 身份区分「提交显示名」

## 两层不要混

| 层 | 作用 | 怎么配 |
|----|------|--------|
| **SSH 密钥 / Host 别名** | 向 GitHub **认证**推送；可区分家里机 vs 办公室机 | 每台电脑一把密钥；办公室用专用 Host |
| **git user.name / user.email** | 每条 commit 上显示的**作者** | 本仓库 local：`Office CP` + 你的邮箱 |

结论：**可以**靠特定 SSH 链接（Host 别名 + 专用密钥）区分办公室提交推送；家里继续用原有 `git@github.com:...`。同一 GitHub 账号下添加**第二把**公钥即可。

## 办公室机（本机）约定

已（或应按下文）生成：

- 私钥：`~/.ssh/id_ed25519_office_cp_ofce`
- 公钥：`~/.ssh/id_ed25519_office_cp_ofce.pub`
- SSH 别名：**`github.com-office-cp`**

`~/.ssh/config` 片段：

```sshconfig
Host github.com-office-cp
  HostName github.com
  User git
  IdentityFile ~/.ssh/id_ed25519_office_cp_ofce
  IdentitiesOnly yes
```

### 1. 把办公室公钥加到 GitHub

GitHub → Settings → SSH and GPG keys → New SSH key  
Title 建议：`AutoExport-office`（历史 title `office-cp-ofce` 也可保留）  
粘贴 `.pub` 文件内容。

### 2. 本仓库 remote 使用办公室别名（不要用默认 github.com）

仓库创建好后：

```powershell
# 将 YOUR_USER 换成你的 GitHub 用户名（本机已用 lawrenceren1618-commits）
git remote add origin git@github.com-office-cp:YOUR_USER/AutoExport.git
# 若已有 origin：
# git remote set-url origin git@github.com-office-cp:YOUR_USER/AutoExport.git
```

推送时会走**办公室专用密钥**，与家里默认 `git@github.com:YOUR_USER/...` 分离。  
密钥文件名仍可为 `id_ed25519_office_cp_ofce`（本机已有，不必改文件名）。

### 3. 提交人显示（与 SSH 独立）

本仓库已设（仅 local，不改全局）：

```powershell
git config user.name "Office CP"
git config user.email "lawrenceren1618@gmail.com"
```

家里仓库可继续用家里的 `user.name`（例如你的真名），这样 GitHub 提交历史上也能看出作者字段差异。

## 家里机（已有 SSH）保持不动

- 继续：`git@github.com:YOUR_USER/<家里仓库>.git`
- 使用家里已有的 `id_ed25519` / `id_rsa` 等
- **不要**把办公室私钥拷到家里，也**不要**把家里私钥拷到办公室

## 自检

```powershell
ssh -T git@github.com-office-cp
# 成功会看到：Hi <username>! You've successfully authenticated...
```

在本仓库：

```powershell
git remote -v
# 应看到 github.com-office-cp，而不是裸的 github.com
```
