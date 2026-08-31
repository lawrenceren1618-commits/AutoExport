import { NextResponse } from "next/server";
import { isAdminAuthenticated } from "@/lib/admin-auth";
import {
  buildArchiveTree,
  mergeArchiveEntries,
  readArchiveIndexFile,
} from "@/lib/pipeline/archive-index";
import { listJobs } from "@/lib/pipeline/jobs";

/** 库务存档索引树（不进 workspace 主路径） */
export async function GET() {
  if (!(await isAdminAuthenticated())) {
    return NextResponse.json({ ok: false, error: "unauthorized" }, { status: 401 });
  }

  const file = readArchiveIndexFile();
  const { jobs, source } = await listJobs();
  const entries = mergeArchiveEntries(file.entries, jobs);
  const tree = buildArchiveTree(entries);

  return NextResponse.json({
    ok: true,
    source: { index_file: true, jobs: source },
    ticket_count: entries.length,
    carton_sum: entries.reduce((s, e) => s + (e.carton_count ?? 0), 0),
    tree,
    entries,
  });
}
