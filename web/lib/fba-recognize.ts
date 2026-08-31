/**
 * FBA 外箱贴 / 仓头识别：
 * - 主路径：PDF 文本层 ASCII（无 OCR）
 * - 备用：仅当主路径无法抽出仓码+货件号时，才试 Tesseract（已设计流程保留，不删除）
 * - 先判渠道（FC 运营中心 vs AWD），再按规则库抽字段
 * - 宁空不填错；确认闸门仍强制
 */

import { convertWithTesseractBackup } from "@/lib/pipeline/ocr-dual-convert";
import {
  allKnownWarehouses,
  awdWarehouses,
  detectCartonChannel,
  fcWarehouses,
  pdfJunkTokens,
  type CartonChannel,
} from "@/lib/pipeline/carton-destination";

export type RecognizedWarehouseRow = {
  warehouse_code: string;
  fba_shipment_id: string;
  reference_id: string;
  carton_count: number | null;
  strip_count: number | null;
  source_filename: string;
  recognize_notes: string;
  tracking_id?: string;
  preview_data_url?: string;
  ocr_used?: boolean;
  ocr_text_preview?: string;
};

const FBA_RE = /\b(FBA[0-9A-Z]{8,})\b/gi;
/** Must keep the hyphen so PDF `startxref` does not become STARTXREF. */
const AWD_RE = /\b(STAR-[0-9A-Z]+)\b/gi;
const WH_RE = /\b([A-Z]{3}[0-9]|[A-Z]{2}[0-9]{2}|[A-Z]{4}[0-9]?)\b/g;
/** 常见承运追踪形态（建议值，须人工确认）；不含无标签的 8 位乱码 */
const TRACK_RE =
  /\b(1Z[0-9A-Z]{16}|TBA\d{12}|[A-Z]{2}\d{9}[A-Z]{2}|\d{12,22})\b/gi;

const KNOWN_WH = allKnownWarehouses();
const FC_WH = fcWarehouses();
const AWD_WH = awdWarehouses();
const PDF_JUNK = pdfJunkTokens();

function uniqueMatches(re: RegExp, text: string): string[] {
  const out: string[] = [];
  const seen = new Set<string>();
  const r = new RegExp(re.source, re.flags.includes("g") ? re.flags : `${re.flags}g`);
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

function isPdfJunkChunk(s: string): boolean {
  const u = s.replace(/[^A-Z0-9]/gi, "").toUpperCase();
  if (!u) return true;
  if (PDF_JUNK.has(u)) return true;
  if (u.includes("STARTXREF") || u.includes("FLATEDECODE")) return true;
  return false;
}

export function extractAsciiBlob(buf: Buffer): string {
  const parts: string[] = [];
  let cur = "";
  for (let i = 0; i < buf.length; i++) {
    const b = buf[i];
    if (b >= 0x20 && b <= 0x7e) {
      cur += String.fromCharCode(b);
      if (cur.length > 200) {
        if (!isPdfJunkChunk(cur)) parts.push(cur);
        cur = "";
      }
    } else if (cur.length >= 6) {
      if (!isPdfJunkChunk(cur)) parts.push(cur);
      cur = "";
    } else {
      cur = "";
    }
  }
  if (cur.length >= 6 && !isPdfJunkChunk(cur)) parts.push(cur);
  return parts.join("\n");
}

/** 中文 OCR 常在字间插空格：货 件 → 货件 */
export function normalizeOcrText(text: string): string {
  return text
    .replace(/(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])/g, "")
    .replace(/[ \t]+/g, " ")
    .replace(/\n{3,}/g, "\n\n");
}

function collectWarehousesInOrder(text: string, channel?: CartonChannel): string[] {
  const out: string[] = [];
  const seen = new Set<string>();
  const allow =
    channel === "AWD" ? AWD_WH : channel === "FC" ? FC_WH : KNOWN_WH;
  for (const m of text.matchAll(/货件名称\s*[:：]?\s*([A-Z]{3}\d|[A-Z]{2}\d{2})/gi)) {
    const w = m[1].toUpperCase();
    if (channel === "AWD") continue;
    if (!seen.has(w)) {
      seen.add(w);
      out.push(w);
    }
  }
  for (const w of uniqueMatches(WH_RE, text)) {
    if (!allow.has(w)) continue;
    if (!seen.has(w)) {
      seen.add(w);
      out.push(w);
    }
  }
  return out;
}

/** 取仓码 i 到下一仓之间的片段（每仓箱数/追踪只在本段内找） */
function warehouseSegment(text: string, warehouses: string[], i: number): string {
  if (!warehouses[i]) return text;
  const upper = text.toUpperCase();
  const wh = warehouses[i].toUpperCase();
  let start = upper.indexOf(wh);
  if (start < 0) start = 0;
  let end = text.length;
  for (let j = i + 1; j < warehouses.length; j++) {
    const next = upper.indexOf(warehouses[j].toUpperCase(), start + wh.length);
    if (next > start) {
      end = next;
      break;
    }
  }
  return text.slice(start, end);
}

/** 每仓箱数：本段内「N箱」；排除「共 N 个箱子」总箱 */
function cartonInSegment(seg: string): number | null {
  const matches = [...seg.matchAll(/(\d+)\s*箱/g)];
  for (const m of matches) {
    const idx = m.index ?? 0;
    const before = seg.slice(Math.max(0, idx - 4), idx);
    if (/共/.test(before)) continue;
    const n = parseInt(m[1], 10);
    if (Number.isFinite(n) && n > 0 && n < 100_000) return n;
  }
  return null;
}

function trackingInSegment(seg: string, channel?: CartonChannel): string {
  const labeled = seg.match(/(?:货件)?追踪(?:编码|编号)\s*[:：]?\s*([A-Z0-9]{6,30})/i);
  if (labeled?.[1]) {
    const v = labeled[1].toUpperCase();
    if (!v.startsWith("FBA") && !v.startsWith("STAR")) return v;
  }
  if (channel === "AWD") return "";
  for (const t of uniqueMatches(TRACK_RE, seg)) {
    if (t.startsWith("FBA") || t.startsWith("STAR")) continue;
    if (KNOWN_WH.has(t)) continue;
    if (PDF_JUNK.has(t)) continue;
    return t;
  }
  return "";
}

function shipmentInSegment(seg: string, channel?: CartonChannel): string {
  if (channel === "AWD") {
    return uniqueMatches(AWD_RE, seg)[0] || "";
  }
  if (channel === "FC") {
    return uniqueMatches(FBA_RE, seg)[0] || "";
  }
  const fbas = uniqueMatches(FBA_RE, seg);
  if (fbas[0]) return fbas[0];
  return uniqueMatches(AWD_RE, seg)[0] || "";
}

function cartonFromFilename(filename: string): number | null {
  const m = filename.match(/(\d+)\s*箱/);
  if (!m) return null;
  const n = parseInt(m[1], 10);
  return Number.isFinite(n) && n > 0 && n < 100_000 ? n : null;
}

function channelNote(channel: CartonChannel, signals: string[]): string {
  if (channel === "AWD") {
    return `建议渠道=AWD（${signals.join(",") || "规则库"}）；运营中心/AWD 确认后仓码形态固定`;
  }
  if (channel === "FC") {
    return `建议渠道=运营中心FC（${signals.join(",") || "规则库"}）`;
  }
  return "渠道未判定（FC运营中心 或 AWD）；宁空不填错，请手选后确认";
}

/**
 * 优先按「货件名称」切段；每段抽仓码 / FBA / 本仓箱数 / 追踪。
 * 切不出多段时，再按 FBA 列表对齐仓码（箱数仍按仓段，不用总箱）。
 */
export function recognizeManyFromText(
  text: string,
  filename: string,
  opts?: { ocr_used?: boolean },
): RecognizedWarehouseRow[] {
  const normalized = normalizeOcrText(text);
  const combined = `${filename}\n${normalized}`;
  const preview = normalized.replace(/\s+/g, " ").trim().slice(0, 220);
  const { channel, signals } = detectCartonChannel(combined);

  const namedParts = normalized.split(/(?=货件名称)/).filter((p) => /货件名称/.test(p));
  if (namedParts.length >= 2 && channel !== "AWD") {
    return namedParts.map((part, i) => {
      const whs = collectWarehousesInOrder(part, "FC");
      const warehouse_code = whs[0] || "";
      const fba_shipment_id = shipmentInSegment(part, "FC");
      const carton_count = cartonInSegment(part) ?? cartonFromFilename(filename);
      const tracking_id = trackingInSegment(part, "FC");
      const notes: string[] = [];
      if (opts?.ocr_used) notes.push("已OCR");
      notes.push(channelNote("FC", signals));
      notes.push(`按货件段拆行 ${i + 1}/${namedParts.length}（箱数=本仓）`);
      if (!warehouse_code) notes.push("未识别仓码，可改");
      if (!fba_shipment_id) notes.push("未识别FBA，可改");
      if (carton_count == null) notes.push("未识别本仓箱数，可改");
      if (!tracking_id) notes.push("未识别追踪码，可手改");
      else notes.push("追踪为识别建议，不对可改");
      return {
        warehouse_code,
        fba_shipment_id,
        reference_id: "",
        carton_count,
        strip_count: null,
        source_filename: `${filename}#${i + 1}`,
        tracking_id,
        recognize_notes: notes.join("；"),
        ocr_used: Boolean(opts?.ocr_used),
        ocr_text_preview: preview || undefined,
      };
    });
  }

  const fbas = uniqueMatches(FBA_RE, combined);
  const awds = uniqueMatches(AWD_RE, combined);
  const shipmentIds = channel === "AWD" ? awds : channel === "FC" ? fbas : fbas.length ? fbas : awds;
  const warehouses = collectWarehousesInOrder(combined, channel);

  if (shipmentIds.length <= 1) {
    return [recognizeFromTextAndName(normalized, filename, opts)];
  }

  return shipmentIds.map((fba, i) => {
    const warehouse_code = warehouses[i] || "";
    const seg = warehouseSegment(combined, warehouses, i);
    const carton_count = cartonInSegment(seg) ?? cartonFromFilename(filename);
    const tracking_id = trackingInSegment(seg, channel);
    const notes: string[] = [];
    if (opts?.ocr_used) notes.push("已OCR");
    notes.push(channelNote(channel, signals));
    notes.push(`多货件拆行 ${i + 1}/${shipmentIds.length}（箱数=本仓段内）`);
    if (!warehouse_code) notes.push("未对齐仓码，可改");
    if (carton_count == null) notes.push("未识别本仓箱数，可改");
    if (!tracking_id) notes.push("未识别追踪码，可手改");
    else notes.push("追踪为识别建议，不对可改");
    return {
      warehouse_code,
      fba_shipment_id: fba,
      reference_id: "",
      carton_count,
      strip_count: null,
      source_filename: `${filename}#${i + 1}`,
      tracking_id,
      recognize_notes: notes.join("；"),
      ocr_used: Boolean(opts?.ocr_used),
      ocr_text_preview: preview || undefined,
    };
  });
}

export function recognizeFromTextAndName(
  text: string,
  filename: string,
  opts?: { ocr_used?: boolean },
): RecognizedWarehouseRow {
  const normalized = normalizeOcrText(text);
  const combined = `${filename}\n${normalized}`;
  const { channel, signals } = detectCartonChannel(combined);
  const fbas = uniqueMatches(FBA_RE, combined);
  const awds = uniqueMatches(AWD_RE, combined);
  const carton_count = cartonInSegment(combined) ?? cartonFromFilename(filename);

  const whs = collectWarehousesInOrder(combined, channel);
  let warehouse_code = whs[0] || "";
  if (!warehouse_code && channel === "FC") {
    const nameWh = filename.toUpperCase().match(/\b([A-Z]{3}\d)\b/);
    if (nameWh && FC_WH.has(nameWh[1])) warehouse_code = nameWh[1];
  }

  const fba_shipment_id = shipmentInSegment(combined, channel) || (channel === "AWD" ? awds[0] : fbas[0]) || "";

  const tracking_id = trackingInSegment(combined, channel);

  const notes: string[] = [];
  if (opts?.ocr_used) notes.push("已OCR");
  notes.push(channelNote(channel, signals));
  if (!fba_shipment_id) notes.push("未识别货件号，可改");
  if (!warehouse_code) notes.push("未识别仓库代码，可改");
  if (carton_count == null) notes.push("未识别本仓箱数，可改");
  if (!tracking_id) notes.push("未识别追踪码，可手改");
  else notes.push("追踪为识别建议，不对可改");
  notes.push("请核对后点确认（规则库只给建议）");

  const preview = normalized.replace(/\s+/g, " ").trim().slice(0, 180);

  return {
    warehouse_code,
    fba_shipment_id,
    reference_id: "",
    carton_count,
    strip_count: null,
    source_filename: filename,
    tracking_id,
    recognize_notes: notes.join("；") || "已识别，请核对后确认",
    ocr_used: Boolean(opts?.ocr_used),
    ocr_text_preview: preview || undefined,
  };
}

function rowsLackIdentity(rows: RecognizedWarehouseRow[]): boolean {
  if (!rows.length) return true;
  return rows.every((r) => !r.warehouse_code && !r.fba_shipment_id);
}

function emptyRow(filename: string, note: string): RecognizedWarehouseRow {
  return {
    warehouse_code: "",
    fba_shipment_id: "",
    reference_id: "",
    carton_count: null,
    strip_count: null,
    source_filename: filename,
    tracking_id: "",
    recognize_notes: note,
    ocr_used: false,
  };
}

async function tryTesseractBackup(
  buf: Buffer,
  filename: string,
  reason: string,
): Promise<RecognizedWarehouseRow[]> {
  const ocr = await convertWithTesseractBackup(buf);
  if (ocr.ok && ocr.text.trim()) {
    const preview = ocr.text.replace(/\s+/g, " ").trim().slice(0, 240);
    const rows = recognizeManyFromText(`${filename}\n${ocr.text}`, filename, {
      ocr_used: true,
    });
    for (const r of rows) {
      r.ocr_used = true;
      r.ocr_text_preview = preview;
      r.recognize_notes = `主路径失败（${reason}）后启用备用 Tesseract；${r.recognize_notes}；仍须确认`;
    }
    return rows;
  }
  return [
    emptyRow(
      filename,
      `主路径失败（${reason}）；备用 Tesseract 亦无可用文本${ocr.error ? `（${ocr.error}）` : ""}。请手填后确认`,
    ),
  ];
}

/** Sync：仅主路径（PDF 文本层）。备用 OCR 只在 async 入口。 */
export function recognizeFileBuffer(
  buf: Buffer,
  filename: string,
): RecognizedWarehouseRow {
  const lower = filename.toLowerCase();
  if (lower.endsWith(".pdf")) {
    return recognizeFromTextAndName(
      `${filename}\n${extractAsciiBlob(buf)}`,
      filename,
    );
  }
  return emptyRow(filename, "非 PDF：主路径不处理；请走异步识别（失败后才备用 OCR）或手填");
}

/** 主路径 PDF 文本层；抽不出仓+货件号才试 Tesseract。确认闸门仍强制。 */
export async function recognizeFileBufferAsync(
  buf: Buffer,
  filename: string,
  mimeHint?: string,
): Promise<RecognizedWarehouseRow[]> {
  const lower = filename.toLowerCase();
  const mime = (mimeHint || "").toLowerCase();
  const isPdf = lower.endsWith(".pdf") || mime === "application/pdf";
  const isImg =
    /\.(png|jpe?g|webp|gif|bmp)$/i.test(lower) || mime.startsWith("image/");

  if (isImg) {
    return tryTesseractBackup(buf, filename, "非PDF/无文本层");
  }

  if (!isPdf) {
    return [emptyRow(filename, "仅支持 PDF（主）或图片（主失败后备用 OCR）；请改传或手填")];
  }

  const blob = extractAsciiBlob(buf);
  const text = `${filename}\n${blob}`;
  let rows = blob.trim()
    ? recognizeManyFromText(text, filename)
    : [emptyRow(filename, "PDF 无可用文本层")];
  if (!blob.trim() || rowsLackIdentity(rows)) {
    return tryTesseractBackup(
      buf,
      filename,
      blob.trim() ? "文本层未抽出仓码与货件号" : "PDF 无可用文本层",
    );
  }
  for (const r of rows) {
    if (!r.recognize_notes.includes("PDF")) {
      r.recognize_notes = `${r.recognize_notes}；来源=主路径 PDF 文本层`;
    }
    r.ocr_used = false;
  }
  return rows;
}
