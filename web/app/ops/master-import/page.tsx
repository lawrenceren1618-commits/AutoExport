import { redirect } from "next/navigation";
import { isAdminAuthenticated } from "@/lib/admin-auth";
import { OpsNav } from "@/components/OpsNav";
import { MasterImportForm } from "@/app/admin/master-import/MasterImportForm";

export default async function OpsMasterImportPage() {
  if (!(await isAdminAuthenticated())) {
    redirect("/ops/login");
  }

  return (
    <main>
      <OpsNav />
      <div className="card">
        <h1>人工总表导入（H01）</h1>
        <p className="muted">
          亦可将文件放到{" "}
          <code>1_Input_Raw/00_Master_Reference/</code>
          。上传后须显式确认才写入沉淀。
        </p>
        <MasterImportForm />
      </div>
    </main>
  );
}
