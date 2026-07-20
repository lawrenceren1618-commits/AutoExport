import {
  PROGRESS_TREE,
  ProgressNode,
  buildProgressForest,
} from "@/content/progress-tree";
import { getSupabaseAnon } from "@/lib/supabase/client";

export async function loadProgressNodes(): Promise<{
  nodes: ProgressNode[];
  source: "supabase" | "local";
}> {
  const sb = getSupabaseAnon();
  if (sb) {
    const { data, error } = await sb
      .from("progress_nodes")
      .select("id,parent_id,title,status,module,next_action,sort")
      .order("sort");
    if (!error && data && data.length > 0) {
      return {
        source: "supabase",
        nodes: data.map((r) => ({
          id: r.id as string,
          parentId: (r.parent_id as string | null) ?? null,
          title: r.title as string,
          status: r.status as ProgressNode["status"],
          module: r.module as string,
          nextAction: (r.next_action as string) ?? "",
          sort: r.sort as number,
        })),
      };
    }
  }
  return { nodes: PROGRESS_TREE, source: "local" };
}

export { buildProgressForest };
