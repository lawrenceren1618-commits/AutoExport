import { NextRequest, NextResponse } from "next/server";
import * as XLSX from "xlsx";
import { isAdminAuthenticated } from "@/lib/admin-auth";
import { getSupabaseService } from "@/lib/supabase/client";
import { mapSheetRows, CanonicalRow } from "@/lib/master-import";

export const runtime = "nodejs";

async function parseFile(file: File): Promise<CanonicalRow[]> {
  const buf = Buffer.from(await file.arrayBuffer());
  const wb = XLSX.read(buf, { type: "buffer", cellDates: true });
  const sheet = wb.Sheets[wb.SheetNames[0]];
  const raw = XLSX.utils.sheet_to_json<Record<string, unknown>>(sheet, {
    defval: null,
  });
  return mapSheetRows(raw);
}

export async function POST(req: NextRequest) {
  if (!(await isAdminAuthenticated())) {
    return NextResponse.json({ error: "未登录后台" }, { status: 401 });
  }

  const form = await req.formData();
  const file = form.get("file");
  const mode = String(form.get("mode") ?? "preview");
  const confirmed = String(form.get("confirmed") ?? "") === "true";

  if (!(file instanceof File)) {
    return NextResponse.json({ error: "缺少文件" }, { status: 400 });
  }

  let rows: CanonicalRow[];
  try {
    rows = await parseFile(file);
  } catch (e) {
    return NextResponse.json(
      { error: `解析失败: ${e instanceof Error ? e.message : String(e)}` },
      { status: 400 }
    );
  }

  if (mode === "preview" || !confirmed) {
    return NextResponse.json({
      rowCount: rows.length,
      rows: rows.slice(0, 50),
      handshake: "H01_pending_confirm",
    });
  }

  // H01: confirmed ingest only
  const sb = getSupabaseService();
  if (!sb) {
    return NextResponse.json(
      {
        error:
          "未配置办公室 Supabase（NEXT_PUBLIC_SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY）。预览已可用；请先按 docs/SUPABASE.md 建库。",
        rowCount: rows.length,
        handshake: "H01_blocked_no_supabase",
      },
      { status: 503 }
    );
  }

  let insertedProducts = 0;
  let insertedPacking = 0;
  let insertedFnsku = 0;

  for (const r of rows) {
    const entity = r.entity_code === "C04" || r.entity_code === "C07" ? r.entity_code : null;
    if (!entity || !r.brand) continue;

    if (r.sku_key) {
      const { error } = await sb.from("settled_products").upsert(
        {
          sku_key: r.sku_key,
          brand: r.brand,
          entity_code: entity,
          color: r.color ?? null,
          size: r.size ?? null,
          gram_weight: r.gram_weight ?? null,
          confirmed_order_date: r.confirmed_order_date ?? null,
          source: "master_table",
          confirmed_by_user: true,
          updated_at: new Date().toISOString(),
        },
        { onConflict: "sku_key,brand,entity_code" }
      );
      if (!error) insertedProducts += 1;
    }

    if (r.product_key) {
      const { error } = await sb.from("settled_packing").insert({
        product_key: r.product_key,
        brand: r.brand,
        entity_code: entity,
        strips_per_carton: r.strips_per_carton,
        packs_per_carton: r.packs_per_carton,
        carton_size_cm: r.carton_lwh_cm ?? null,
        gross_kg: r.gross_kg,
        net_kg: r.net_kg,
        volume_cbm: r.volume_cbm,
        effective_order_date: r.confirmed_order_date ?? null,
        source: "master_table",
        confirmed_by_user: true,
      });
      if (!error) insertedPacking += 1;
    }

    if (r.fnsku) {
      const { error } = await sb.from("settled_fnsku").upsert(
        {
          fnsku: r.fnsku,
          entity_code: entity,
          brand: r.brand,
          color: r.color ?? null,
          size: r.size ?? null,
          amazon_store_key: entity,
          source: "master_table",
          confirmed_by_user: true,
          updated_at: new Date().toISOString(),
        },
        { onConflict: "fnsku,entity_code" }
      );
      if (!error) insertedFnsku += 1;
    }
  }

  await sb.from("master_table_imports").insert({
    file_name: file.name,
    row_count: rows.length,
    confirmed_at: new Date().toISOString(),
    notes: "H01 confirmed via /api/master-import",
  });

  return NextResponse.json({
    ok: true,
    handshake: "H01_done",
    rowCount: rows.length,
    insertedProducts,
    insertedPacking,
    insertedFnsku,
  });
}
