import { NextResponse } from "next/server";
import { isAdminAuthenticated } from "@/lib/admin-auth";
import {
  patchArchiveEntry,
  readArchiveIndexFile,
  writeLocalUnitPrices,
  type ArchiveCostPendingLine,
} from "@/lib/pipeline/archive-index";

export const runtime = "nodejs";

type Body = {
  entry_id: string;
  confirm: boolean;
  batch_total_cost: number;
  lines: ArchiveCostPendingLine[];
};

/**
 * 确认单价截图识别结果：
 * - 云端索引：仅 batch_total_cost + 截图路径；清除 pending 明细
 * - 本地：各规格单价 JSON
 */
export async function POST(req: Request) {
  if (!(await isAdminAuthenticated())) {
    return NextResponse.json({ ok: false, error: "unauthorized" }, { status: 401 });
  }

  let body: Body;
  try {
    body = (await req.json()) as Body;
  } catch {
    return NextResponse.json({ ok: false, error: "invalid_json" }, { status: 400 });
  }

  if (!body.entry_id || body.confirm !== true) {
    return NextResponse.json(
      { ok: false, error: "entry_id and confirm=true required" },
      { status: 400 },
    );
  }
  if (!Number.isFinite(body.batch_total_cost) || body.batch_total_cost < 0) {
    return NextResponse.json({ ok: false, error: "batch_total_cost invalid" }, { status: 400 });
  }

  const entry = readArchiveIndexFile().entries.find(
    (e) => e.id === body.entry_id || e.job_id === body.entry_id,
  );
  if (!entry) {
    return NextResponse.json({ ok: false, error: "entry_not_found" }, { status: 404 });
  }

  const lines = (body.lines || []).filter(
    (l) => l && typeof l.unit_price === "number" && Number.isFinite(l.unit_price),
  ) as { label: string; unit_price: number; carton_count?: number | null }[];

  if (!lines.length) {
    return NextResponse.json(
      { ok: false, error: "at_least_one_unit_price_required" },
      { status: 400 },
    );
  }

  const local = writeLocalUnitPrices({
    entry_id: entry.id,
    order_code: entry.order_code,
    batch_total_cost: body.batch_total_cost,
    lines,
    screenshot_name: entry.cost?.screenshot?.name,
  });
  if (!local.ok) {
    return NextResponse.json(
      { ok: false, error: local.error || "local_write_failed" },
      { status: 500 },
    );
  }

  const patched = patchArchiveEntry(entry.id, {
    cost: {
      status: "confirmed",
      batch_total_cost: Number(body.batch_total_cost.toFixed(2)),
      screenshot: entry.cost?.screenshot,
      confirmed_at: new Date().toISOString(),
      // 故意不带 pending / 规格单价
    },
  });

  if (!patched.ok) {
    return NextResponse.json(
      { ok: false, error: patched.error || "cloud_patch_failed", local_path: local.path },
      { status: 500 },
    );
  }

  return NextResponse.json({
    ok: true,
    entry: patched.entry,
    local_path: local.path,
    message: "已确认：云端仅批次总成本；本地已写规格单价。",
  });
}
