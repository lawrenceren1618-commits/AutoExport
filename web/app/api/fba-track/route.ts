import { NextRequest, NextResponse } from "next/server";
import { isAdminAuthenticated } from "@/lib/admin-auth";
import { getSupabaseService } from "@/lib/supabase/client";
import { recognizeFileBuffer, RecognizedWarehouseRow } from "@/lib/fba-recognize";

export const runtime = "nodejs";

/** POST: 上传 PDF/截图 → 识别仓头（不入库）；可选 save=1 写入 fba_warehouse_headers */
export async function POST(req: NextRequest) {
  if (!(await isAdminAuthenticated())) {
    return NextResponse.json({ error: "未登录后台" }, { status: 401 });
  }

  const form = await req.formData();
  const order_code = String(form.get("order_code") ?? "").trim();
  const split_leg_id = String(form.get("split_leg_id") ?? "").trim();
  const save = String(form.get("save") ?? "") === "1";
  const files = form.getAll("files").filter((f): f is File => f instanceof File);

  if (files.length === 0) {
    return NextResponse.json({ error: "请至少上传一个文件（PDF 或截图）" }, { status: 400 });
  }

  const rows: RecognizedWarehouseRow[] = [];
  for (const file of files) {
    const buf = Buffer.from(await file.arrayBuffer());
    const row = recognizeFileBuffer(buf, file.name);
    if (file.type.startsWith("image/") && buf.length < 2_000_000) {
      row.preview_data_url = `data:${file.type};base64,${buf.toString("base64")}`;
    }
    rows.push(row);
  }

  if (!save) {
    return NextResponse.json({
      rowCount: rows.length,
      rows,
      note: "仅识别预览；核对后勾选保存，再逐行填写追踪编码",
    });
  }

  const sb = getSupabaseService();
  if (!sb) {
    return NextResponse.json(
      {
        error:
          "未配置 Supabase。识别结果已返回；请配置后再保存仓头。",
        rows,
      },
      { status: 503 }
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
        strip_count: r.strip_count,
        source_filename: r.source_filename,
        recognize_notes: r.recognize_notes,
        tracking_id: null,
        status: "pending_tracking",
      })
      .select()
      .single();
    if (error) {
      return NextResponse.json(
        {
          error: `写入失败（请先在 Supabase 执行 migrations/20260722000000_fba_warehouse_headers.sql）: ${error.message}`,
          rows,
        },
        { status: 500 }
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
      {
        error: `读取失败（可能未建表）: ${error.message}`,
        rows: [],
      },
      { status: 500 }
    );
  }
  return NextResponse.json({ rows: data ?? [] });
}
