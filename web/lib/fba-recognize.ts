/**
 * FBA 外箱贴 / 截图文件名与 PDF 字节流轻量识别（无 OCR 大库）。
 * 识别不到的字段留空，由后台手工补；追踪码一律人工填。
 */

export type RecognizedWarehouseRow = {
  warehouse_code: string;
  fba_shipment_id: string;
  reference_id: string;
  carton_count: number | null;
  strip_count: number | null;
  source_filename: string;
  recognize_notes: string;
  preview_data_url?: string;
};

const FBA_RE = /\b(FBA[0-9A-Z]{8,})\b/gi;
const REF_RE = /\b([0-9A-Z]{6,12})\b/g;
/** 常见美东美西仓码形态 */
const WH_RE = /\b([A-Z]{3}[0-9]|[A-Z]{2}[0-9]{2}|[A-Z]{4}[0-9]?)\b/g;
const CARTON_RE = /(\d+)\s*箱/;

const KNOWN_WH = new Set([
  "HEA2",
  "AVP1",
  "MDW2",
  "GYR3",
  "RDU2",
  "LGB8",
  "ONT8",
  "FTW1",
  "SWF2",
  "CF012",
]);

function uniqueMatches(re: RegExp, text: string): string[] {
  const out: string[] = [];
  const seen = new Set<string>();
  const r = new RegExp(re.source, re.flags.includes("g") ? re.flags : re.flags + "g");
  let m: RegExpExecArray | null;
  while ((m = r.exec(text)) !== null) {
    const v = m[1].toUpperCase();
    if (!seen.has(v)) {
      seen.add(v);
      out.push(v);
    }
  }
  return out;
}

/** 从 PDF / 任意二进制里捞可打印 ASCII 片段 */
export function extractAsciiBlob(buf: Buffer): string {
  const parts: string[] = [];
  let cur = "";
  for (let i = 0; i < buf.length; i++) {
    const b = buf[i];
    if (b >= 0x20 && b <= 0x7e) {
      cur += String.fromCharCode(b);
      if (cur.length > 200) {
        parts.push(cur);
        cur = "";
      }
    } else if (cur.length >= 6) {
      parts.push(cur);
      cur = "";
    } else {
      cur = "";
    }
  }
  if (cur.length >= 6) parts.push(cur);
  return parts.join("\n");
}

export function recognizeFromTextAndName(
  text: string,
  filename: string
): RecognizedWarehouseRow {
  const combined = `${filename}\n${text}`;
  const fbas = uniqueMatches(FBA_RE, combined);
  const cartonM = combined.match(CARTON_RE);
  const carton_count = cartonM ? parseInt(cartonM[1], 10) : null;

  let warehouse_code = "";
  for (const w of uniqueMatches(WH_RE, combined)) {
    if (KNOWN_WH.has(w) || /^[A-Z]{3}\d$/.test(w)) {
      warehouse_code = w;
      break;
    }
  }
  // 文件名里「仓码 箱」常见
  const nameWh = filename.toUpperCase().match(/\b([A-Z]{3}\d)\b/);
  if (!warehouse_code && nameWh) warehouse_code = nameWh[1];

  const fba_shipment_id = fbas[0] ?? "";
  // reference：排除已是 FBA 的串；取文件名 =FBA 前一段或短码
  let reference_id = "";
  const ylp = filename.match(/YLPSV[0-9A-Z]+/i);
  if (ylp) reference_id = ylp[0].toUpperCase();
  if (!reference_id) {
    for (const c of uniqueMatches(REF_RE, combined)) {
      if (c.startsWith("FBA")) continue;
      if (KNOWN_WH.has(c)) continue;
      if (c.length >= 8 && c.length <= 12) {
        reference_id = c;
        break;
      }
    }
  }

  const notes: string[] = [];
  if (!fba_shipment_id) notes.push("未识别FBA号，请手填");
  if (!warehouse_code) notes.push("未识别仓库代码，请手填");
  if (filename.match(/\.(png|jpe?g|webp|gif)$/i)) {
    notes.push("图片无OCR：请对照截图手填空项；追踪码必填");
  }

  return {
    warehouse_code,
    fba_shipment_id,
    reference_id,
    carton_count,
    strip_count: null,
    source_filename: filename,
    recognize_notes: notes.join("；") || "已尝试识别，请核对",
  };
}

export function recognizeFileBuffer(
  buf: Buffer,
  filename: string
): RecognizedWarehouseRow {
  const lower = filename.toLowerCase();
  let text = filename;
  if (lower.endsWith(".pdf")) {
    text = `${filename}\n${extractAsciiBlob(buf)}`;
  } else {
    // 图片：仅文件名
    text = filename;
  }
  return recognizeFromTextAndName(text, filename);
}
