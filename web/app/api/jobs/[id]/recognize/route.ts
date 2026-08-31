import { NextResponse } from "next/server";
import { getJob, updateJobMeta } from "@/lib/pipeline/jobs";
import { getMeta } from "@/lib/pipeline/stages";

type Ctx = { params: Promise<{ id: string }> };

type RecogRowIn = {
  warehouse_code?: string;
  fba_shipment_id?: string;
  reference_id?: string;
  tracking_id?: string;
  carton_count?: number | null;
  source_filename?: string;
  recognize_notes?: string;
};

/** Confirm / amend multi-warehouse recognition rows before trio wave. */
export async function POST(req: Request, ctx: Ctx) {
  const { id } = await ctx.params;
  const job = await getJob(id);
  if (!job) {
    return NextResponse.json({ ok: false, error: "job not found" }, { status: 404 });
  }
  const body = (await req.json().catch(() => ({}))) as {
    rows?: RecogRowIn[];
    /** @deprecated single-row fields — still accepted and mapped to one row */
    warehouse_code?: string;
    fba_shipment_id?: string;
    reference_id?: string;
    tracking_id?: string;
    carton_count?: number | null;
    confirm?: boolean;
  };

  const meta = getMeta(job);
  const prevRows = meta.carton_recognition?.rows || [];

  let rows: {
    warehouse_code: string;
    fba_shipment_id: string;
    reference_id: string;
    carton_count: number | null;
    strip_count: number | null;
    source_filename: string;
    recognize_notes: string;
    tracking_id: string;
  }[];

  if (Array.isArray(body.rows) && body.rows.length > 0) {
    rows = body.rows.map((r, i) => {
      const prev = prevRows[i];
      return {
        warehouse_code: String(r.warehouse_code ?? prev?.warehouse_code ?? "")
          .trim()
          .toUpperCase(),
        fba_shipment_id: String(r.fba_shipment_id ?? prev?.fba_shipment_id ?? "")
          .trim()
          .toUpperCase(),
        reference_id: String(r.reference_id ?? prev?.reference_id ?? "")
          .trim()
          .toUpperCase(),
        tracking_id: String(r.tracking_id ?? prev?.tracking_id ?? "").trim(),
        carton_count:
          r.carton_count !== undefined
            ? r.carton_count
            : (prev?.carton_count ?? null),
        strip_count: prev?.strip_count ?? null,
        source_filename: String(r.source_filename ?? prev?.source_filename ?? ""),
        recognize_notes: String(r.recognize_notes ?? prev?.recognize_notes ?? ""),
      };
    });
  } else {
    const prev = prevRows[0];
    rows = [
      {
        warehouse_code: String(body.warehouse_code ?? prev?.warehouse_code ?? "")
          .trim()
          .toUpperCase(),
        fba_shipment_id: String(body.fba_shipment_id ?? prev?.fba_shipment_id ?? "")
          .trim()
          .toUpperCase(),
        reference_id: String(body.reference_id ?? prev?.reference_id ?? "")
          .trim()
          .toUpperCase(),
        tracking_id: String(body.tracking_id ?? prev?.tracking_id ?? "").trim(),
        carton_count:
          body.carton_count !== undefined
            ? body.carton_count
            : (prev?.carton_count ?? null),
        strip_count: prev?.strip_count ?? null,
        source_filename: prev?.source_filename ?? "",
        recognize_notes: prev?.recognize_notes ?? "",
      },
    ];
  }

  // Drop completely empty rows
  rows = rows.filter(
    (r) =>
      r.warehouse_code ||
      r.fba_shipment_id ||
      r.reference_id ||
      r.tracking_id ||
      r.source_filename,
  );

  if (body.confirm) {
    if (rows.length === 0) {
      return NextResponse.json(
        { ok: false, error: "至少一行仓库识别结果", issues: ["无有效行"] },
        { status: 400 },
      );
    }
    const issues: string[] = [];
    rows.forEach((r, i) => {
      if (!r.warehouse_code) issues.push(`第${i + 1}行缺仓库代码`);
      if (!r.fba_shipment_id) issues.push(`第${i + 1}行缺货件号`);
    });
    if (issues.length) {
      return NextResponse.json(
        { ok: false, error: "确认前每行须具备仓库代码与货件号", issues },
        { status: 400 },
      );
    }
  }

  const updated = await updateJobMeta(id, {
    carton_recognition: {
      rows,
      tracking_id: rows.map((r) => r.tracking_id).filter(Boolean).join(";"),
      user_confirmed: body.confirm === true,
      confirmed_at: body.confirm ? new Date().toISOString() : undefined,
    },
    extracts: {
      ...(meta.extracts || {}),
      warehouse: {
        status: body.confirm ? "user_confirmed" : "pending_confirm",
        warehouses: rows.map((r) => ({
          warehouse_code: r.warehouse_code,
          fba_shipment_id: r.fba_shipment_id,
          tracking_id: r.tracking_id,
          reference_id: r.reference_id,
        })),
        count: rows.length,
      },
    },
  });

  return NextResponse.json({
    ok: true,
    confirmed: body.confirm === true,
    rows,
    job: updated,
  });
}
