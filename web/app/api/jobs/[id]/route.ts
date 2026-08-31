import { NextResponse } from "next/server";
import { deleteJob, getJob } from "@/lib/pipeline/jobs";
import {
  INPUT_SECTIONS,
  OUTPUT_SECTIONS,
  ARCHIVE_SECTION,
  FLOW_DEFAULTS,
  UI_META,
} from "@/lib/pipeline/schema";
import { preflightJob } from "@/lib/pipeline/preflight";
import { handshakeCatalog } from "@/lib/pipeline/handshake";
import { getMeta, phaseOf, stageFocus, PIPELINE_STEPS } from "@/lib/pipeline/stages";

type Ctx = { params: Promise<{ id: string }> };

export async function GET(_req: Request, ctx: Ctx) {
  const { id } = await ctx.params;
  const job = await getJob(id);
  if (!job) {
    return NextResponse.json({ ok: false, error: "job not found" }, { status: 404 });
  }
  const meta = getMeta(job);
  const uploads = meta.uploads || {};
  const preflight = preflightJob({
    hasShipPlan: Boolean(uploads.ship_plan || (meta.lines && meta.lines.length)),
    hasCartonTracking: Boolean(uploads.carton_and_tracking),
    hasFreightInbound: Boolean(uploads.freight_inbound),
    wantOutputs: OUTPUT_SECTIONS.map((s) => s.id),
  });
  const phase = phaseOf(job);
  return NextResponse.json({
    ok: true,
    job,
    phase,
    stage: stageFocus(phase),
    ui: UI_META,
    flow: FLOW_DEFAULTS,
    steps: PIPELINE_STEPS,
    sections: {
      input: INPUT_SECTIONS,
      output: OUTPUT_SECTIONS,
      archive: ARCHIVE_SECTION,
    },
    handshakes: handshakeCatalog(),
    preflight,
  });
}

export async function DELETE(_req: Request, ctx: Ctx) {
  const { id } = await ctx.params;
  const job = await getJob(id);
  if (!job) {
    return NextResponse.json({ ok: false, error: "job not found" }, { status: 404 });
  }
  const ok = await deleteJob(id);
  return NextResponse.json({ ok, id });
}
