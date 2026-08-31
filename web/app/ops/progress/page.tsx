import { redirect } from "next/navigation";
import { isAdminAuthenticated } from "@/lib/admin-auth";
import {
  PROGRESS_TREE,
  buildProgressForest,
  summarizeProgress,
} from "@/content/progress-tree";
import { ProgressTree } from "@/components/ProgressTree";
import { OpsNav } from "@/components/OpsNav";

export default async function OpsProgressPage() {
  if (!(await isAdminAuthenticated())) {
    redirect("/ops/login");
  }
  const nodes = PROGRESS_TREE;
  const forest = buildProgressForest(nodes);
  const roots = forest.get(null) ?? [];
  const { done, pending, total } = summarizeProgress(nodes);

  return (
    <main>
      <OpsNav />
      <div className="card">
        <h1>进度树（库务）</h1>
        <p className="muted">
          不对做单主路径暴露。日常发货请用「作业」。
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
            <span className="badge-pending">未完成</span> 黄色
          </span>
        </div>
        <div className="tree">
          <ProgressTree nodes={roots} forest={forest} depth={0} />
        </div>
      </div>
    </main>
  );
}
