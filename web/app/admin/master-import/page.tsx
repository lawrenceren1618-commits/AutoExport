import { redirect } from "next/navigation";
import Link from "next/link";
import { isAdminAuthenticated } from "@/lib/admin-auth";
import { MasterImportForm } from "./MasterImportForm";

export default async function MasterImportPage() {
  if (!(await isAdminAuthenticated())) {
    redirect("/admin/login");
  }

  return (
    <main>
      <nav className="admin-nav">
        <Link href="/admin/progress">目标树</Link>
        <Link href="/admin/master-import">人工总表导入</Link>
        <Link href="/">返回首页</Link>
      </nav>
      <div className="card">
        <h1>人工总表导入（M0 / H01）</h1>
        <p className="muted">
          亦可将文件放到仓库{" "}
          <code>1_Input_Raw/00_Master_Reference/</code>
          。此处上传后须显式确认才写入沉淀表。
        </p>
        <MasterImportForm />
      </div>
    </main>
  );
}
