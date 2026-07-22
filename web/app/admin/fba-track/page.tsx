import { redirect } from "next/navigation";
import { isAdminAuthenticated } from "@/lib/admin-auth";
import { AdminNav } from "@/components/AdminNav";
import { FbaTrackPanel } from "./FbaTrackPanel";

export default async function FbaTrackPage() {
  if (!(await isAdminAuthenticated())) {
    redirect("/admin/login");
  }

  return (
    <main>
      <AdminNav />
      <div className="card" style={{ marginBottom: "1rem" }}>
        <h1>FBA 仓头 · 截图/外箱贴识别 · 追踪编码</h1>
        <p className="muted">
          流水线 P9：上传亚马逊外箱贴 PDF 或货件截图 → 自动抽仓码/FBA 号（能识别则填）→
          <strong>由你输入追踪编码</strong>并保存。供后续货代下单（H42）使用。
        </p>
      </div>
      <FbaTrackPanel />
    </main>
  );
}
