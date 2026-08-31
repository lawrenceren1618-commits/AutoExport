import { NextResponse } from "next/server";
import { getJob, updateJobMeta } from "@/lib/pipeline/jobs";
import type { JobMeta } from "@/lib/pipeline/stages";

type Ctx = { params: Promise<{ id: string }> };

type PlanLineIn = {
  size?: string;
  color?: string;
  qty_strips?: number;
  qty_cartons?: number;
  strips_per_pack?: number;
  packs_per_carton?: number;
  strips_per_carton?: number;
  fnsku?: string;
  amazon_sku?: string;
  gram_weight?: string;
};

/**
 * PATCH job meta (手补计划行等)。不删字段；只合并传入的 meta 片段。
 */
export async function POST(req: Request, ctx: Ctx) {
  const { id } = await ctx.params;
  const job = await getJob(id);
  if (!job) {
    return NextResponse.json({ ok: false, error: "job not found" }, { status: 404 });
  }

  const body = (await req.json().catch(() => ({}))) as {
    lines?: PlanLineIn[];
    total_strips?: number;
    plan_mode?: string;
  };

  if (!Array.isArray(body.lines) || body.lines.length === 0) {
    return NextResponse.json(
      { ok: false, error: "lines required (至少一行手补规格)" },
      { status: 400 },
    );
  }

  const lines = body.lines.map((ln) => {
    const stripsPerPack = Number(ln.strips_per_pack) || undefined;
    const packsPerCarton = Number(ln.packs_per_carton) || undefined;
    let stripsPerCarton = Number(ln.strips_per_carton) || undefined;
    if (!stripsPerCarton && stripsPerPack && packsPerCarton) {
      stripsPerCarton = stripsPerPack * packsPerCarton;
    }
    const qtyCartons = Number(ln.qty_cartons) || undefined;
    let qtyStrips = Number(ln.qty_strips) || undefined;
    if (!qtyStrips && qtyCartons && stripsPerCarton) {
      qtyStrips = qtyCartons * stripsPerCarton;
    }
    return {
      size: (ln.size || "").trim(),
      color: (ln.color || "").trim() || null,
      qty_strips: qtyStrips ?? null,
      qty_cartons: qtyCartons ?? null,
      strips_per_pack: stripsPerPack ?? null,
      packs_per_carton: packsPerCarton ?? null,
      strips_per_carton: stripsPerCarton ?? null,
      fnsku: (ln.fnsku || "").trim() || null,
      amazon_sku: (ln.amazon_sku || "").trim() || null,
      gram_weight: (ln.gram_weight || "").trim() || null,
    };
  });

  const sumStrips = lines.reduce(
    (a, ln) => a + (typeof ln.qty_strips === "number" ? ln.qty_strips : 0),
    0,
  );
  const total_strips =
    typeof body.total_strips === "number" && body.total_strips > 0
      ? body.total_strips
      : sumStrips || job.meta?.total_strips;

  const patch: Partial<JobMeta> & { plan_mode?: string } = {
    lines: lines as JobMeta["lines"],
    total_strips,
    plan_mode: body.plan_mode || "manual_lines",
  };

  const updated = await updateJobMeta(id, patch);
  return NextResponse.json({
    ok: true,
    job: updated,
    note: "手补计划行已写入；生成订单仍须行内含 FNSKU + 条/包 + 箱规（或沉淀库可匹配）",
  });
}
