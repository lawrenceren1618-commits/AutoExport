# Office SSH quick setup

## 1. Keys (on the machine only)

```text
Private: %USERPROFILE%\.ssh\id_ed25519_office_cp_ofce
Public:  %USERPROFILE%\.ssh\id_ed25519_office_cp_ofce.pub
```

In-repo public copy (reference): `docs/ssh/id_ed25519_office_cp_ofce.pub`

## 2. `%USERPROFILE%\.ssh\config` Host snippet

```sshconfig
Host github.com-office-cp
  HostName github.com
  User git
  IdentityFile ~/.ssh/id_ed25519_office_cp_ofce
  IdentitiesOnly yes
```

## 3. Remote URL pattern

本机已验证账号：**`lawrenceren1618-commits`**  
仓库名：**`AutoExport`**

```text
git@github.com-office-cp:lawrenceren1618-commits/AutoExport.git
```

```powershell
git remote add origin git@github.com-office-cp:lawrenceren1618-commits/AutoExport.git
# or update existing:
# git remote set-url origin git@github.com-office-cp:lawrenceren1618-commits/AutoExport.git
```

## 4. Add the public key on GitHub

GitHub → Settings → SSH and GPG keys → New SSH key → paste contents of the `.pub` file (title e.g. `AutoExport-office`).

## 5. Test (when ready — do not block on this)

```powershell
ssh -T git@github.com-office-cp
```
