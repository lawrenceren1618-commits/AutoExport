import { redirect } from "next/navigation";
import { isAdminAuthenticated } from "@/lib/admin-auth";
import {
  buildArchiveTree,
  mergeArchiveEntries,
  readArchiveIndexFile,
} from "@/lib/pipeline/archive-index";
import { listJobs } from "@/lib/pipeline/jobs";
import { ArchiveTree } from "@/components/ArchiveTree";
import { OpsNav } from "@/components/OpsNav";

export default async function OpsArchivesPage() {
  if (!(await isAdminAuthenticated())) {
    redirect("/ops/login");
  }

  const file = readArchiveIndexFile();
  const { jobs } = await listJobs();
  const entries = mergeArchiveEntries(file.entries, jobs);
  const tree = buildArchiveTree(entries);
  const cartonSum = entries.reduce((s, e) => s + (e.carton_count ?? 0), 0);

  return (
    <main>
      <OpsNav />
      <div className="card arch-card">
        <header className="arch-header">
          <p className="arch-kicker">库务 · 索引视图</p>
          <h1>发货存档</h1>
          <p className="muted">
            按<strong>实际交货日</strong>归类（无则 = 订单交货日）；不用做任务时间。节点显示短码 · 批次 · 整票箱数（悬停见 EF 长号）。点「详细」看规格箱数；点「单价」上传截图确认（云端只留批次总成本）。注意行高列宽、一屏可读。
          </p>
        </header>
        <div className="summary-bar arch-summary">
          共 <strong>{entries.length}</strong> 票
          {cartonSum > 0 ? (
            <>
              {" "}
              · 合计箱数 <strong>{cartonSum}</strong>
            </>
          ) : null}
        </div>
        <ArchiveTree tree={tree} />
      </div>
    </main>
  );
}
