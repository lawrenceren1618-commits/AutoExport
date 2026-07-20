/**
 * Canonical field mapping — keep in sync with Scripts/canonical_schema.json
 * and Templates/Canonical_Data_Schema.md
 */

export const HEADER_MAP: Record<string, string> = {
  主体: "entity_code",
  主体代码: "entity_code",
  公司代码: "entity_code",
  entity: "entity_code",
  entity_code: "entity_code",
  公司名: "company_name",
  公司名称: "company_name",
  company: "company_name",
  company_name: "company_name",
  品牌: "brand",
  商品品牌: "brand",
  brand: "brand",
  颜色: "color",
  COLOR: "color",
  color: "color",
  尺寸: "size",
  尺寸项: "size",
  规格尺寸: "size",
  size: "size",
  克重: "gram_weight",
  面料克重: "gram_weight",
  "WEIGHT/规格": "gram_weight",
  WEIGHT: "gram_weight",
  gram_weight: "gram_weight",
  "条数/包": "strips_per_pack",
  条数每包: "strips_per_pack",
  strips_per_pack: "strips_per_pack",
  "包数/箱": "packs_per_carton",
  包数每箱: "packs_per_carton",
  packs_per_carton: "packs_per_carton",
  "条数/箱": "strips_per_carton",
  条数每箱: "strips_per_carton",
  strips_per_carton: "strips_per_carton",
  外箱尺寸: "carton_lwh_cm",
  "外箱尺寸（长*宽*高）": "carton_lwh_cm",
  纸箱规格: "carton_lwh_cm",
  carton_size_cm: "carton_lwh_cm",
  carton_lwh_cm: "carton_lwh_cm",
  内包装尺寸: "inner_pack_lwh_cm",
  内盒: "inner_pack_lwh_cm",
  包装尺寸: "inner_pack_lwh_cm",
  inner_pack_lwh_cm: "inner_pack_lwh_cm",
  包装方式: "pack_method",
  包装: "pack_method",
  pack_method: "pack_method",
  fnsku: "fnsku",
  FNSKU: "fnsku",
  产品标签: "fnsku",
  标签: "fnsku",
  毛重: "gross_kg",
  "G.W.": "gross_kg",
  gross_kg: "gross_kg",
  净重: "net_kg",
  "N.W.": "net_kg",
  net_kg: "net_kg",
  体积: "volume_cbm",
  CBM: "volume_cbm",
  volume_cbm: "volume_cbm",
  下单日期: "order_date",
  订单日期: "order_date",
  order_date: "order_date",
  生效日期: "confirmed_order_date",
  confirmed_order_date: "confirmed_order_date",
  订单编号: "order_code",
  订单号: "order_code",
  "P.O#": "order_code",
  order_code: "order_code",
  数量: "qty_strips",
  总条数: "qty_strips",
  QTY: "qty_strips",
  qty_strips: "qty_strips",
  箱数: "qty_cartons",
  总箱数: "qty_cartons",
  件数: "qty_cartons",
  CTNS: "qty_cartons",
  qty_cartons: "qty_cartons",
  中文品名: "product_name_zh",
  品名: "product_name_zh",
  product_name_zh: "product_name_zh",
  英文品名: "product_name_en",
  product_name_en: "product_name_en",
  HS: "hs_code",
  "HS CODE": "hs_code",
  海关编码: "hs_code",
  商品编号: "hs_code",
  hs_code: "hs_code",
  是否退税: "tax_rebate",
  退税: "tax_rebate",
  tax_rebate: "tax_rebate",
  "1039单价": "declare_unit_price_1039",
  报关单价: "declare_unit_price_1039",
  每箱报关单价: "declare_unit_price_1039",
  declare_unit_price_1039: "declare_unit_price_1039",
  FBA: "fba_shipment_id",
  FBA货件号: "fba_shipment_id",
  海外订单号: "fba_shipment_id",
  货件编号: "fba_shipment_id",
  fba_shipment_id: "fba_shipment_id",
  追踪编码: "tracking_id",
  追踪号: "tracking_id",
  tracking: "tracking_id",
  tracking_id: "tracking_id",
  仓库代码: "warehouse_code",
  warehouse_code: "warehouse_code",
  仓库地址: "warehouse_address",
  FBA地址: "warehouse_address",
  warehouse_address: "warehouse_address",
};

export type CanonicalRow = {
  entity_code?: string;
  company_name?: string;
  brand?: string;
  color?: string;
  size?: string;
  gram_weight?: string;
  strips_per_pack?: number | null;
  packs_per_carton?: number | null;
  strips_per_carton?: number | null;
  pack_method?: "heat_shrink" | "carton" | string;
  inner_pack_lwh_cm?: string;
  carton_lwh_cm?: string;
  fnsku?: string;
  hs_code?: string;
  product_name_zh?: string;
  product_name_en?: string;
  tax_rebate?: string;
  declare_unit_price_1039?: number | null;
  order_code?: string;
  order_date?: string | null;
  confirmed_order_date?: string | null;
  qty_strips?: number | null;
  qty_cartons?: number | null;
  fba_shipment_id?: string;
  tracking_id?: string;
  warehouse_code?: string;
  warehouse_address?: string;
  gross_kg?: number | null;
  net_kg?: number | null;
  volume_cbm?: number | null;
  sku_key?: string;
  product_key?: string;
  data_tier?: "settled" | "temporary";
  unmapped?: Record<string, unknown>;
};

const BRAND_BY_ENTITY: Record<string, string> = {
  C04: "WIGENIUS",
  C07: "Dressmaker",
};

function normHeader(h: string): string {
  const t = String(h).trim();
  return HEADER_MAP[t] ?? HEADER_MAP[t.toLowerCase()] ?? t;
}

function toNum(v: unknown): number | null {
  if (v == null || v === "") return null;
  if (typeof v === "number" && Number.isFinite(v)) return v;
  const n = Number(String(v).replace(/,/g, "").trim());
  return Number.isFinite(n) ? n : null;
}

function toDateStr(v: unknown): string | null {
  if (v == null || v === "") return null;
  if (v instanceof Date && !Number.isNaN(v.getTime())) {
    return v.toISOString().slice(0, 10);
  }
  const s = String(v).trim().replace(/\./g, "-");
  return s.slice(0, 10) || null;
}

export function normalizeEntityCode(v: unknown): string | undefined {
  const raw = String(v ?? "").toUpperCase();
  if (raw.includes("C04")) return "C04";
  if (raw.includes("C07")) return "C07";
  const m = raw.match(/C0[47]/);
  return m ? m[0] : undefined;
}

export function normalizePackMethod(v: unknown): string | undefined {
  if (v == null || v === "") return undefined;
  const s = String(v);
  if (/热缩/.test(s) || /shrink/i.test(s)) return "heat_shrink";
  if (/纸箱/.test(s) || /carton/i.test(s)) return "carton";
  if (s === "heat_shrink" || s === "carton") return s;
  return s.trim();
}

export function normalizeLwh(v: unknown): string | undefined {
  if (v == null || v === "") return undefined;
  return String(v)
    .trim()
    .replace(/×/g, "*")
    .replace(/x/gi, "*")
    .replace(/\s*cm\s*/gi, "")
    .replace(/\s+/g, "");
}

export function applyBrandDefault(row: CanonicalRow): CanonicalRow {
  if (!row.brand && row.entity_code && BRAND_BY_ENTITY[row.entity_code]) {
    row.brand = BRAND_BY_ENTITY[row.entity_code];
  }
  return row;
}

export function mapSheetRows(
  rawRows: Record<string, unknown>[]
): CanonicalRow[] {
  return rawRows.map((raw) => {
    const out: CanonicalRow = { unmapped: {} };
    for (const [k, v] of Object.entries(raw)) {
      const key = normHeader(k);
      if (!(key in HEADER_MAP) && HEADER_MAP[k] === undefined && HEADER_MAP[k.toLowerCase()] === undefined) {
        // still might be canonical already
        const known = Object.values(HEADER_MAP).includes(key);
        if (!known && key !== String(k).trim()) {
          // mapped
        } else if (!known) {
          out.unmapped![k] = v;
          continue;
        }
      }

      switch (key) {
        case "entity_code":
          out.entity_code = normalizeEntityCode(v);
          break;
        case "pack_method":
          out.pack_method = normalizePackMethod(v);
          break;
        case "carton_lwh_cm":
        case "inner_pack_lwh_cm":
          out[key] = normalizeLwh(v);
          break;
        case "strips_per_pack":
        case "packs_per_carton":
        case "strips_per_carton":
        case "qty_strips":
        case "qty_cartons":
        case "gross_kg":
        case "net_kg":
        case "volume_cbm":
        case "declare_unit_price_1039":
          (out as Record<string, unknown>)[key] = toNum(v);
          break;
        case "order_date":
        case "confirmed_order_date":
          (out as Record<string, unknown>)[key] = toDateStr(v);
          break;
        case "company_name":
        case "brand":
        case "color":
        case "size":
        case "gram_weight":
        case "fnsku":
        case "hs_code":
        case "product_name_zh":
        case "product_name_en":
        case "tax_rebate":
        case "order_code":
        case "fba_shipment_id":
        case "tracking_id":
        case "warehouse_code":
        case "warehouse_address":
          if (v != null && v !== "") {
            (out as Record<string, unknown>)[key] = String(v).trim();
          }
          break;
        default:
          if (Object.values(HEADER_MAP).includes(key)) {
            if (v != null && v !== "") {
              (out as Record<string, unknown>)[key] = String(v).trim();
            }
          } else {
            out.unmapped![k] = v;
          }
      }
    }

    if (
      out.strips_per_carton == null &&
      out.strips_per_pack != null &&
      out.packs_per_carton != null
    ) {
      out.strips_per_carton = out.strips_per_pack * out.packs_per_carton;
    }

    applyBrandDefault(out);

    const brand = out.brand ?? "";
    const color = out.color ?? "";
    const size = out.size ?? "";
    out.sku_key = [brand, size, color].filter(Boolean).join("|") || undefined;
    out.product_key = out.sku_key;
    out.data_tier = out.fba_shipment_id || out.tracking_id ? "temporary" : "settled";

    if (out.unmapped && Object.keys(out.unmapped).length === 0) {
      delete out.unmapped;
    }
    return out;
  });
}
