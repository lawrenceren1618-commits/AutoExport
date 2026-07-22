import { redirect } from "next/navigation";
import { isAdminAuthenticated } from "@/lib/admin-auth";
import {
  PROGRESS_TREE,
  buildProgressForest,
  summarizeProgress,
} from "@/content/progress-tree";
import { ProgressTree } from "@/components/ProgressTree";
import { AdminNav } from "@/components/AdminNav";

/**
 * 工作总结仅后台：以本地 progress-tree.ts 为当前进度真相来源
 *（Supabase progress_nodes 建库同步后再改回可切换）。
 */
export default async function AdminProgressPage() {
  if (!(await isAdminAuthenticated())) {
    redirect("/admin/login");
  }
  const nodes = PROGRESS_TREE;
  const forest = buildProgressForest(nodes);
  const roots = forest.get(null) ?? [];
  const { done, pending, total } = summarizeProgress(nodes);

  return (
    <main>
      <AdminNav />
      <div className="card">
        <h1>工作总结（仅后台）</h1>
        <p className="muted">
          树状列出各任务与完成目标。已完成标绿，未完成标黄。日常作业请用顶栏「FBA仓头/追踪码」。
        </p>
        <div className="summary-bar">
          叶子任务：共 {total} 项 ·{" "}
          <span className="badge-done">已完成 {done}</span>{" "}
          <span className="badge-pending">未完成 {pending}</span>
        </div>
        <div className="legend">
          <span>
            <span className="badge-done">已完成</span> 绿色
          </span>
          <span>
            <span className="badge-pending">未完成</span> 黄色（进行中 /
            待办 / 阻塞）
          </span>
        </div>
        <div className="tree">
          <ProgressTree nodes={roots} forest={forest} depth={0} />
        </div>
      </div>
    </main>
  );
}
