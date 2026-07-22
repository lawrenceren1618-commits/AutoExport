import { redirect } from "next/navigation";
import { isAdminAuthenticated } from "@/lib/admin-auth";
import { AdminNav } from "@/components/AdminNav";
import { MasterImportForm } from "./MasterImportForm";

export default async function MasterImportPage() {
  if (!(await isAdminAuthenticated())) {
    redirect("/admin/login");
  }

  return (
    <main>
      <AdminNav />
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
