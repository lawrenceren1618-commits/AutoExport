import { NextResponse } from "next/server";
import { createJob, listJobs } from "@/lib/pipeline/jobs";
import type { PlanLine } from "@/lib/pipeline/numbering";

export async function GET() {
  const { jobs, source, db_error } = await listJobs();
  return NextResponse.json({
    ok: true,
    source,
    db_error: db_error || undefined,
    jobs,
    local_store_hint:
      source === "memory" || source === "db+local"
        ? "2_Processed_AI/cloud_job_store/shipment_jobs.json"
        : undefined,
  });
}

export async function POST(req: Request) {
  const body = (await req.json().catch(() => ({}))) as {
    entity_code?: "C04" | "C07";
    ship_date?: string;
    order_date?: string;
    actual_delivery_date?: string;
    total_strips?: number;
    lines?: PlanLine[];
    /** @deprecated user must not set; ignored if present */
    project_code?: string;
  };

  if (!body.entity_code || (body.entity_code !== "C04" && body.entity_code !== "C07")) {
    return NextResponse.json(
      { ok: false, error: "entity_code must be C04|C07" },
      { status: 400 },
    );
  }
  if (!body.ship_date) {
    return NextResponse.json({ ok: false, error: "ship_date required" }, { status: 400 });
  }

  try {
    const result = await createJob({
      entity_code: body.entity_code,
      ship_date: body.ship_date,
      order_date: body.order_date,
      actual_delivery_date: body.actual_delivery_date,
      total_strips: body.total_strips,
      lines: body.lines,
    });
    return NextResponse.json({
      ok: true,
      source: result.source,
      job: result.job,
      warning: result.error || undefined,
      note: body.project_code
        ? "project_code is auto-generated; client-supplied value ignored"
        : undefined,
    });
  } catch (e) {
    return NextResponse.json(
      { ok: false, error: e instanceof Error ? e.message : String(e) },
      { status: 400 },
    );
  }
}
