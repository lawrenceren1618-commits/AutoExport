# AutoExport?Supabase + Vercel ???????

| ? | ? |
|----|-----|
| ???? / GitHub / Vercel / Supabase | **AutoExport** |
| Git ??? | **Office CP**?office-cp?? ?? |
| ??? SSH | **github.com-office-cp** |

---

## 0. GitHub

```powershell
cd C:\Users\Administrator\.cursor\Cursor-projects\AutoExport
ssh -T git@github.com-office-cp

# ???? Private ?? AutoExport???????
git remote add origin git@github.com-office-cp:lawrenceren1618-commits/AutoExport.git
git branch -M main
git add .
git commit -m "Initial AutoExport scaffold"
git push -u origin main
```

??????`git@github.com:...`???? `github.com-office-cp`??

---

## 1. Supabase

1. New project?**Name = `AutoExport`**?????????
2. SQL Editor ??`supabase/migrations/20260720000000_init_ofce.sql`
3. Settings ? API??? URL / anon / service_role ? `web/.env.local`
4. `OFCE_ENV=office`???????????????

---

## 2. Vercel

1. Import ?? **`AutoExport`**
2. **Root Directory = `web`**
3. ????? `.env.local` ???Production + Preview?
4. Deploy ? `/admin/progress`

---

## 3. ???

| | ?? | ??? |
|--|------|--------|
| ??? / ?? | ?? | **AutoExport** |
| SSH | `git@github.com:...` | **`git@github.com-office-cp:...`** |
| ??? | ???? | **Office CP** |
| Supabase / Vercel | ???? | **AutoExport** |
