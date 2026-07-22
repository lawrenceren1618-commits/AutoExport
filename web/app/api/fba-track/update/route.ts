import { NextRequest, NextResponse } from "next/server";
import { isAdminAuthenticated } from "@/lib/admin-auth";
import { getSupabaseService } from "@/lib/supabase/client";

export const runtime = "nodejs";

type PatchBody = {
  id: string;
  tracking_id?: string;
  warehouse_code?: string;
  fba_shipment_id?: string;
  reference_id?: string;
  warehouse_address?: string;
  carton_count?: number | null;
  strip_count?: number | null;
  status?: string;
};

/** PATCH: 更新单行（主要填追踪编码；亦可改正识别字段） */
export async function PATCH(req: NextRequest) {
  if (!(await isAdminAuthenticated())) {
    return NextResponse.json({ error: "未登录后台" }, { status: 401 });
  }
  const sb = getSupabaseService();
  if (!sb) {
    return NextResponse.json({ error: "未配置 Supabase" }, { status: 503 });
  }

  let body: PatchBody;
  try {
    body = (await req.json()) as PatchBody;
  } catch {
    return NextResponse.json({ error: "JSON 无效" }, { status: 400 });
  }
  if (!body.id) {
    return NextResponse.json({ error: "缺少 id" }, { status: 400 });
  }

  const patch: Record<string, unknown> = {
    updated_at: new Date().toISOString(),
  };
  if (body.tracking_id !== undefined) {
    patch.tracking_id = body.tracking_id.trim() || null;
    if (body.tracking_id.trim()) {
      patch.status = "tracking_filled";
    }
  }
  if (body.warehouse_code !== undefined) patch.warehouse_code = body.warehouse_code.trim() || null;
  if (body.fba_shipment_id !== undefined)
    patch.fba_shipment_id = body.fba_shipment_id.trim() || null;
  if (body.reference_id !== undefined) patch.reference_id = body.reference_id.trim() || null;
  if (body.warehouse_address !== undefined)
    patch.warehouse_address = body.warehouse_address.trim() || null;
  if (body.carton_count !== undefined) patch.carton_count = body.carton_count;
  if (body.strip_count !== undefined) patch.strip_count = body.strip_count;
  if (body.status !== undefined) patch.status = body.status;

  const { data, error } = await sb
    .from("fba_warehouse_headers")
    .update(patch)
    .eq("id", body.id)
    .select()
    .single();

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
  return NextResponse.json({ row: data, handshake: "P9_tracking_updated" });
}
