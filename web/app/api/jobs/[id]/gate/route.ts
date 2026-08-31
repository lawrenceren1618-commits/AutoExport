import { NextResponse } from "next/server";
import { getJob, updateJobMeta } from "@/lib/pipeline/jobs";
import { checkHX } from "@/lib/pipeline/handshake";

type Ctx = { params: Promise<{ id: string }> };

export async function POST(req: Request, ctx: Ctx) {
  const { id } = await ctx.params;
  const job = await getJob(id);
  if (!job) {
    return NextResponse.json({ ok: false, error: "job not found" }, { status: 404 });
  }
  const body = (await req.json().catch(() => ({}))) as {
    confirm?: boolean;
    checks_ok?: boolean;
  };
  if (!body.confirm) {
    return NextResponse.json(
      { ok: false, error: "confirm=true required" },
      { status: 400 },
    );
  }
  const checks_ok = body.checks_ok !== false;
  const hx = checkHX({
    checks_ok,
    gate_final: checks_ok ? "CONFIRMED" : "WAIT",
  });
  const updated = await updateJobMeta(id, {
    gate_final: checks_ok ? "CONFIRMED" : "REJECTED",
    gate_report: {
      ok: checks_ok,
      checks: ["user_confirmed_cross_check"],
      at: new Date().toISOString(),
    },
  });
  return NextResponse.json({
    ok: hx.ok,
    message: hx.message,
    job: updated,
  });
}
