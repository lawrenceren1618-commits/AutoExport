import { NextRequest, NextResponse } from "next/server";
import { isAdminAuthenticated } from "@/lib/admin-auth";
import { getSupabaseService } from "@/lib/supabase/client";
import {
  recognizeFileBufferAsync,
  type RecognizedWarehouseRow,
} from "@/lib/fba-recognize";

export const runtime = "nodejs";
/** PDF 文本抽取很快；不再跑 OCR */
export const maxDuration = 30;

type SaveRowBody = {
  order_code?: string;
  split_leg_id?: string;
  rows: {
    warehouse_code?: string | null;
    fba_shipment_id?: string | null;
    reference_id?: string | null;
    carton_count?: number | null;
    strip_count?: number | null;
    source_filename?: string | null;
    recognize_notes?: string | null;
    tracking_id?: string | null;
    warehouse_address?: string | null;
  }[];
};

function isPdfFile(file: File): boolean {
  const name = (file.name || "").toLowerCase();
  const type = (file.type || "").toLowerCase();
  return name.endsWith(".pdf") || type === "application/pdf";
}

/** POST: multipart 仅 PDF 文本抽取；或 JSON 确认保存参考 */
export async function POST(req: NextRequest) {
  if (!(await isAdminAuthenticated())) {
    return NextResponse.json({ error: "未登录后台" }, { status: 401 });
  }

  const ctype = req.headers.get("content-type") || "";

  if (ctype.includes("application/json")) {
    let body: SaveRowBody;
    try {
      body = (await req.json()) as SaveRowBody;
    } catch {
      return NextResponse.json({ error: "invalid_json" }, { status: 400 });
    }
    const rows = Array.isArray(body.rows) ? body.rows : [];
    if (!rows.length) {
      return NextResponse.json({ error: "rows required" }, { status: 400 });
    }
    const sb = getSupabaseService();
    if (!sb) {
      return NextResponse.json(
        { error: "未配置 Supabase，无法写入仓头" },
        { status: 503 },
      );
    }
    const inserted: unknown[] = [];
    for (const r of rows) {
      const { data, error } = await sb
        .from("fba_warehouse_headers")
        .insert({
          order_code: (body.order_code || "").trim() || null,
          split_leg_id: (body.split_leg_id || "").trim() || null,
          warehouse_code: r.warehouse_code || null,
          fba_shipment_id: r.fba_shipment_id || null,
          reference_id: r.reference_id || null,
          carton_count: r.carton_count ?? null,
          strip_count: null,
          source_filename: r.source_filename || null,
          recognize_notes: r.recognize_notes || null,
          tracking_id: (r.tracking_id || "").trim() || null,
          warehouse_address: r.warehouse_address || null,
          status: (r.tracking_id || "").trim() ? "tracking_set" : "pending_tracking",
        })
        .select()
        .single();
      if (error) {
        return NextResponse.json(
          { error: `写入失败: ${error.message}`, rows: inserted },
          { status: 500 },
        );
      }
      inserted.push(data);
    }
    return NextResponse.json({
      saved: inserted.length,
      rows: inserted,
      handshake: "M4_headers_from_draft",
    });
  }

  const form = await req.formData();
  const order_code = String(form.get("order_code") ?? "").trim();
  const split_leg_id = String(form.get("split_leg_id") ?? "").trim();
  const save = String(form.get("save") ?? "") === "1";
  const files = form.getAll("files").filter((f): f is File => f instanceof File);

  if (files.length === 0) {
    return NextResponse.json({ error: "请至少上传一个 PDF" }, { status: 400 });
  }

  const nonPdf = files.filter((f) => !isPdfFile(f));
  if (nonPdf.length) {
    return NextResponse.json(
      {
        error: `已停用截图/OCR。仅接受 PDF（拒绝：${nonPdf.map((f) => f.name).join("、")}）`,
      },
      { status: 400 },
    );
  }

  const rows: RecognizedWarehouseRow[] = [];
  for (const file of files) {
    const buf = Buffer.from(await file.arrayBuffer());
    const name = file.name || `upload_${Date.now()}.pdf`;
    const partRows = await recognizeFileBufferAsync(buf, name, file.type);
    rows.push(
      ...partRows.map((row) => ({
        ...row,
        strip_count: null,
      })),
    );
  }

  if (!save) {
    return NextResponse.json({
      rowCount: rows.length,
      rows,
      note: "已从 PDF 文本层归类（无 OCR）。有则填入，无则空置请手补；确认后点「确认保存参考」。",
    });
  }

  const sb = getSupabaseService();
  if (!sb) {
    return NextResponse.json(
      { error: "未配置 Supabase。解析结果已返回；请配置后再保存。", rows },
      { status: 503 },
    );
  }

  const inserted: unknown[] = [];
  for (const r of rows) {
    const { data, error } = await sb
      .from("fba_warehouse_headers")
      .insert({
        order_code: order_code || null,
        split_leg_id: split_leg_id || null,
        warehouse_code: r.warehouse_code || null,
        fba_shipment_id: r.fba_shipment_id || null,
        reference_id: r.reference_id || null,
        carton_count: r.carton_count,
        strip_count: null,
        source_filename: r.source_filename,
        recognize_notes: r.recognize_notes,
        tracking_id: r.tracking_id || null,
        status: r.tracking_id ? "tracking_set" : "pending_tracking",
      })
      .select()
      .single();
    if (error) {
      return NextResponse.json(
        {
          error: `写入失败: ${error.message}`,
          rows,
        },
        { status: 500 },
      );
    }
    inserted.push(data);
  }

  return NextResponse.json({
    saved: inserted.length,
    rows: inserted,
    handshake: "M4_headers_pending_tracking",
  });
}

/** GET: 列出仓头（可按 order_code / split_leg_id 过滤） */
export async function GET(req: NextRequest) {
  if (!(await isAdminAuthenticated())) {
    return NextResponse.json({ error: "未登录后台" }, { status: 401 });
  }
  const sb = getSupabaseService();
  if (!sb) {
    return NextResponse.json({ error: "未配置 Supabase", rows: [] }, { status: 503 });
  }
  const { searchParams } = new URL(req.url);
  const order_code = searchParams.get("order_code");
  const split_leg_id = searchParams.get("split_leg_id");

  let q = sb
    .from("fba_warehouse_headers")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(100);
  if (order_code) q = q.eq("order_code", order_code);
  if (split_leg_id) q = q.eq("split_leg_id", split_leg_id);

  const { data, error } = await q;
  if (error) {
    return NextResponse.json(
      { error: `读取失败（可能未建表）: ${error.message}`, rows: [] },
      { status: 500 },
    );
  }
  return NextResponse.json({ rows: data ?? [] });
}
