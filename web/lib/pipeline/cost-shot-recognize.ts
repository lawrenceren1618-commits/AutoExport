/**
 * 单价截图 OCR（TypeScript 源码，不是视频）。
 * Windows 资源管理器常把 .ts 当成 MPEG-2 传输流，请用 Cursor / VS Code 打开。
 * 人读说明：Templates/Cost_Shot_Recognize.md
 * 主路径 tesseract；并行 LlamaParse 对照（不替代主路径）。
 * 见 Templates/Ocr_Dual_Convert_Compare.md · Ship_Stats_Correspondence S3。
 */

import {
  dualConvertCompare,
  type DualConvertCompare,
} from "./ocr-dual-convert";

export type CostShotProposal = {
  ocr_ok: boolean;
  ocr_text_preview: string;
  amounts: number[];
  proposed_lines: { label: string; unit_price: number | null; carton_count?: number | null }[];
  proposed_batch_total: number | null;
  error?: string;
  dual_compare?: DualConvertCompare;
};

function extractAmounts(text: string): number[] {
  const out: number[] = [];
  const seen = new Set<string>();
  const re = /(\d{1,7}(?:\.\d{1,2})?)/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    const n = Number(m[1]);
    if (!Number.isFinite(n) || n <= 0) continue;
    if (n > 1_000_000) continue;
    const key = n.toFixed(2);
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(n);
  }
  return out;
}

async function ocrImage(buf: Buffer): Promise<{ text: string; ok: boolean; error?: string; ms: number }> {
  const t0 = Date.now();
  try {
    const { createWorker } = await import("tesseract.js");
    const worker = await createWorker("eng+chi_sim");
    try {
      const ret = await worker.recognize(buf);
      return { text: ret.data.text || "", ok: true, ms: Date.now() - t0 };
    } finally {
      await worker.terminate();
    }
  } catch (e) {
    try {
      const { createWorker } = await import("tesseract.js");
      const worker = await createWorker("eng");
      try {
        const ret = await worker.recognize(buf);
        return { text: ret.data.text || "", ok: true, ms: Date.now() - t0 };
      } finally {
        await worker.terminate();
      }
    } catch (e2) {
      return {
        text: "",
        ok: false,
        ms: Date.now() - t0,
        error: e2 instanceof Error ? e2.message : String(e2),
      };
    }
  }
}

function buildProposalFromText(
  text: string,
  ocr_ok: boolean,
  error: string | undefined,
  specLabels: { label: string; carton_count?: number | null }[],
  dual_compare?: DualConvertCompare,
): CostShotProposal {
  const amounts = extractAmounts(text);
  const proposed_lines = specLabels.map((s, i) => ({
    label: s.label,
    unit_price: amounts[i] ?? null,
    carton_count: s.carton_count ?? null,
  }));

  if (!proposed_lines.length && amounts.length) {
    for (const a of amounts.slice(0, 12)) {
      proposed_lines.push({ label: "识别金额", unit_price: a, carton_count: null });
    }
  }

  let proposed_batch_total: number | null = null;
  if (proposed_lines.some((l) => l.unit_price != null && l.carton_count)) {
    proposed_batch_total = proposed_lines.reduce((s, l) => {
      if (l.unit_price == null) return s;
      const c = l.carton_count != null ? l.carton_count : 1;
      return s + l.unit_price * c;
    }, 0);
  } else if (amounts.length) {
    proposed_batch_total = Math.max(...amounts);
  }

  return {
    ocr_ok,
    ocr_text_preview: text.replace(/\s+/g, " ").trim().slice(0, 240),
    amounts,
    proposed_lines,
    proposed_batch_total,
    error,
    dual_compare,
  };
}

export async function recognizeCostShot(opts: {
  buf: Buffer;
  filename: string;
  specLabels?: { label: string; carton_count?: number | null }[];
}): Promise<CostShotProposal> {
  const specs = opts.specLabels || [];
  const ocr = await ocrImage(opts.buf);
  const primaryText = `${opts.filename}\n${ocr.text}`;

  const dual = await dualConvertCompare({
    primary: {
      engine: "local_tesseract",
      ok: ocr.ok,
      text: primaryText,
      ms: ocr.ms,
      error: ocr.error,
    },
    buf: opts.buf,
    filename: opts.filename,
    persist: true,
    tag: "cost_shot",
  });

  // 主路径始终用 local；若 disagree 且 LlamaParse 抽出更多金额，仅写入对照，不自动改提案
  return buildProposalFromText(primaryText, ocr.ok, ocr.error, specs, dual);
}
