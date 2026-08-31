import { NextResponse } from "next/server";
import { getJob } from "@/lib/pipeline/jobs";
import { EXPORT_RULES, OUTPUT_SECTIONS, ARCHIVE_SECTION } from "@/lib/pipeline/schema";
import { canEnterSaveMode } from "@/lib/pipeline/preflight";
import { checkHX } from "@/lib/pipeline/handshake";

type Ctx = { params: Promise<{ id: string }> };

export async function POST(req: Request, ctx: Ctx) {
  const { id } = await ctx.params;
  const job = await getJob(id);
  if (!job) {
    return NextResponse.json({ ok: false, error: "job not found" }, { status: 404 });
  }
  const body = (await req.json().catch(() => ({}))) as {
    kind?: "shipment_label_pack" | "label_pack" | "product_label_pack" | "archive" | "all_outputs";
    checks_ok?: boolean;
  };
  const kind =
    body.kind === "label_pack" ? "shipment_label_pack" : body.kind || "all_outputs";

  if (kind === "archive") {
    const hx = checkHX({
      checks_ok: body.checks_ok === true,
      gate_final: job.gate_final,
    });
    if (!hx.ok || !canEnterSaveMode("archive", job.gate_final)) {
      return NextResponse.json(
        { ok: false, error: hx.message, gate_final: job.gate_final },
        { status: 409 },
      );
    }
  }

  return NextResponse.json({
    ok: true,
    job_id: id,
    kind,
    outputs: OUTPUT_SECTIONS.map((s) => ({ id: s.id, label: s.label })),
    archive: ARCHIVE_SECTION,
    rules: EXPORT_RULES,
    download: `/api/jobs/${id}/download?section=<section_id>`,
    note: "Download via signed URL or local-blob fallback; generators: order wired, trio partial",
  });
}
