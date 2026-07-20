import { ProgressNode } from "@/content/progress-tree";

type Props = {
  nodes: ProgressNode[];
  forest: Map<string | null, ProgressNode[]>;
  depth: number;
};

export function ProgressTree({ nodes, forest, depth }: Props) {
  if (nodes.length === 0) return null;
  return (
    <ul>
      {nodes.map((n) => {
        const children = forest.get(n.id) ?? [];
        return (
          <li key={n.id}>
            <span className={`status-${n.status}`}>[{n.status}]</span>{" "}
            <span className="node-title">{n.title}</span>
            <span className="meta">
              · {n.module} · 下一步：{n.nextAction}
            </span>
            {children.length > 0 ? (
              <ProgressTree nodes={children} forest={forest} depth={depth + 1} />
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}
