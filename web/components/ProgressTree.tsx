import { ProgressNode } from "@/content/progress-tree";

type Props = {
  nodes: ProgressNode[];
  forest: Map<string | null, ProgressNode[]>;
  depth: number;
};

function statusLabel(status: ProgressNode["status"]): string {
  return status === "done" ? "已完成" : "未完成";
}

export function ProgressTree({ nodes, forest, depth }: Props) {
  if (nodes.length === 0) return null;
  return (
    <ul className={depth === 0 ? "tree-root" : undefined}>
      {nodes.map((n) => {
        const children = forest.get(n.id) ?? [];
        const done = n.status === "done";
        return (
          <li key={n.id} className={done ? "node-done" : "node-pending"}>
            <div className="node-row">
              <span
                className={done ? "badge-done" : "badge-pending"}
                title={n.status}
              >
                {statusLabel(n.status)}
              </span>
              <span className="node-title">{n.title}</span>
              <span className="meta">
                · {n.module}
                {n.nextAction && n.nextAction !== "—"
                  ? ` · 下一步：${n.nextAction}`
                  : ""}
              </span>
            </div>
            {children.length > 0 ? (
              <ProgressTree nodes={children} forest={forest} depth={depth + 1} />
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}
