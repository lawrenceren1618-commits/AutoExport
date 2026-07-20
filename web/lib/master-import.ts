/**
 * Normalize master-table column headers (Chinese / English aliases) → canonical keys.
 */
const HEADER_MAP: Record<string, string> = {
  主体: "entity_code",
  主体代码: "entity_code",
  entity: "entity_code",
  entity_code: "entity_code",
  品牌: "brand",
  brand: "brand",
  颜色: "color",
  color: "color",
  尺寸: "size",
  size: "size",
  克重: "gram_weight",
  gram_weight: "gram_weight",
  条数每箱: "strips_per_carton",
  "条数/箱": "strips_per_carton",
  strips_per_carton: "strips_per_carton",
  包数每箱: "packs_per_carton",
  "包数/箱": "packs_per_carton",
  packs_per_carton: "packs_per_carton",
  外箱尺寸: "carton_size_cm",
  carton_size_cm: "carton_size_cm",
  fnsku: "fnsku",
  FNSKU: "fnsku",
  产品标签: "fnsku",
  毛重: "gross_kg",
  gross_kg: "gross_kg",
  净重: "net_kg",
  net_kg: "net_kg",
  体积: "volume_cbm",
  volume_cbm: "volume_cbm",
  下单日期: "confirmed_order_date",
  生效日期: "confirmed_order_date",
  confirmed_order_date: "confirmed_order_date",
};

export type CanonicalRow = {
  entity_code?: string;
  brand?: string;
  color?: string;
  size?: string;
  gram_weight?: string;
  strips_per_carton?: number | null;
  packs_per_carton?: number | null;
  carton_size_cm?: string;
  fnsku?: string;
  gross_kg?: number | null;
  net_kg?: number | null;
  volume_cbm?: number | null;
  confirmed_order_date?: string | null;
  sku_key?: string;
  product_key?: string;
};

function normHeader(h: string): string {
  const t = String(h).trim();
  return HEADER_MAP[t] ?? HEADER_MAP[t.toLowerCase()] ?? t;
}

function toNum(v: unknown): number | null {
  if (v == null || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

export function mapSheetRows(
  rawRows: Record<string, unknown>[]
): CanonicalRow[] {
  return rawRows.map((raw) => {
    const out: CanonicalRow = {};
    for (const [k, v] of Object.entries(raw)) {
      const key = normHeader(k);
      if (key === "entity_code") {
        const s = String(v ?? "")
          .toUpperCase()
          .replace(/[^C047]/g, "");
        out.entity_code = s.includes("C04")
          ? "C04"
          : s.includes("C07")
            ? "C07"
            : String(v ?? "").trim() || undefined;
      } else if (
        key === "strips_per_carton" ||
        key === "packs_per_carton" ||
        key === "gross_kg" ||
        key === "net_kg" ||
        key === "volume_cbm"
      ) {
        (out as Record<string, unknown>)[key] = toNum(v);
      } else if (key === "confirmed_order_date") {
        if (v instanceof Date) {
          out.confirmed_order_date = v.toISOString().slice(0, 10);
        } else if (v != null && v !== "") {
          out.confirmed_order_date = String(v).slice(0, 10);
        }
      } else if (
        [
          "brand",
          "color",
          "size",
          "gram_weight",
          "carton_size_cm",
          "fnsku",
        ].includes(key)
      ) {
        (out as Record<string, unknown>)[key] =
          v == null || v === "" ? undefined : String(v).trim();
      }
    }
    const brand = out.brand ?? "";
    const color = out.color ?? "";
    const size = out.size ?? "";
    out.sku_key = [brand, size, color].filter(Boolean).join("|") || undefined;
    out.product_key = out.sku_key;
    return out;
  });
}
