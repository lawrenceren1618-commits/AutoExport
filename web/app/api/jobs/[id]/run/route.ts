import { NextResponse } from "next/server";
import { getJob } from "@/lib/pipeline/jobs";
import { runJobStep } from "@/lib/pipeline/runner";
import type { RunStepId } from "@/lib/pipeline/stages";
import { wavePreflight, type WaveId } from "@/lib/pipeline/wave-preflight";

type Ctx = { params: Promise<{ id: string }> };

const ALLOWED: RunStepId[] = [
  "extract_plan",
  "enrich_master",
  "gen_order",
  "gen_product_labels",
  "extract_warehouse",
  "decide_batch",
  "gen_trio",
  "pack_shipment_labels",
  "gate",
  "archive",
];

export async function POST(req: Request, ctx: Ctx) {
  const { id } = await ctx.params;
  const job = await getJob(id);
  if (!job) {
    return NextResponse.json({ ok: false, error: "job not found" }, { status: 404 });
  }

  const body = (await req.json().catch(() => ({}))) as {
    step?: string;
    confirm_gate?: boolean;
    wave?: WaveId;
  };

  const steps: RunStepId[] = [];
  if (body.wave === "after_plan") {
    steps.push("extract_plan", "enrich_master", "gen_order", "gen_product_labels");
  } else if (body.wave === "trio_after_carton") {
    steps.push("extract_warehouse", "decide_batch", "gen_trio");
  } else if (body.wave === "after_inbound") {
    steps.push("pack_shipment_labels", "gate");
  } else if (body.wave === "finalize") {
    steps.push("archive");
  } else if (body.step && ALLOWED.includes(body.step as RunStepId)) {
    steps.push(body.step as RunStepId);
  } else {
    return NextResponse.json(
      { ok: false, error: "step or wave required", allowed_steps: ALLOWED },
      { status: 400 },
    );
  }

  if (body.wave) {
    const pf = wavePreflight(job, body.wave);
    if (!pf.ok) {
      return NextResponse.json(
        {
          ok: false,
          error: "预检未通过，已阻断生成",
          preflight: pf,
          issues: pf.issues,
        },
        { status: 409 },
      );
    }
  }

  let current = job;
  const results = [];
  for (const step of steps) {
    const r = await runJobStep(current, step, { confirm_gate: body.confirm_gate });
    results.push({
      step: r.step,
      ok: r.ok,
      message: r.message,
      mock: r.mock,
      issues: r.issues,
    });
    current = r.job;
    if (!r.ok && step !== "gate") {
      return NextResponse.json(
        {
          ok: false,
          error: r.message,
          results,
          issues: r.issues || [],
          job: current,
        },
        { status: 409 },
      );
    }
  }

  return NextResponse.json({
    ok: results.every((r) => r.ok || r.step === "gate"),
    results,
    job: current,
  });
}
