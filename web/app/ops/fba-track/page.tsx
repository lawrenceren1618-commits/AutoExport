import { redirect } from "next/navigation";
import { isAdminAuthenticated } from "@/lib/admin-auth";
import { OpsNav } from "@/components/OpsNav";
import { FbaTrackPanel } from "@/app/admin/fba-track/FbaTrackPanel";

export default async function OpsFbaTrackPage() {
  if (!(await isAdminAuthenticated())) {
    redirect("/ops/login");
  }

  return (
    <main>
      <OpsNav />
      <div className="card" style={{ marginBottom: "1rem" }}>
        <h1>FBA 仓头 · 追踪编码（库务）</h1>
        <p className="muted">
          仅上传 <strong>PDF</strong>（文本层归类；无 OCR / 不收截图）。有则填入，无则空置手补 →
          「确认保存参考」临时存储供货代调用（H42）。
        </p>
      </div>
      <FbaTrackPanel />
    </main>
  );
}
