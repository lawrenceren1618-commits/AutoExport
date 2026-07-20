import { redirect } from "next/navigation";
import Link from "next/link";
import { isAdminAuthenticated } from "@/lib/admin-auth";
import { loadProgressNodes, buildProgressForest } from "@/lib/progress";
import { ProgressTree } from "@/components/ProgressTree";

export default async function AdminProgressPage() {
  if (!(await isAdminAuthenticated())) {
    redirect("/admin/login");
  }
  const { nodes, source } = await loadProgressNodes();
  const forest = buildProgressForest(nodes);
  const roots = forest.get(null) ?? [];

  return (
    <main>
      <nav className="admin-nav">
        <Link href="/admin/progress">目标树</Link>
        <Link href="/admin/master-import">人工总表导入</Link>
        <Link href="/">返回首页</Link>
      </nav>
      <div className="card">
        <h1>目标树（仅后台）</h1>
        <p className="muted">
          数据源：{source === "supabase" ? "Supabase progress_nodes" : "本地 progress-tree.ts 回退"}
          。看清当前 status 与 next_action，决定下一步。
        </p>
        <div className="tree">
          <ProgressTree nodes={roots} forest={forest} depth={0} />
        </div>
      </div>
    </main>
  );
}
