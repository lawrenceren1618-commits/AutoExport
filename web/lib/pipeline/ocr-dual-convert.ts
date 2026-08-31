/**
 * 外箱贴备用 OCR + 双引擎对照（LlamaParse 默认关闭）。
 * 外箱贴主路径是 PDF 文本层（fba-recognize）；Tesseract 仅主路径失败后调用。
 * 单价截图仍以 Tesseract 为主（cost-shot-recognize）。
 * LlamaParse 对照不替代主路径。见 Templates/Ocr_Dual_Convert_Compare.md。
 */

import fs from "fs";
import path from "path";

export type ConvertEngine = "local_tesseract" | "local_pdf_text" | "local_filename" | "llamaparse";

export type ConvertSide = {
  engine: ConvertEngine;
  ok: boolean;
  text: string;
  ms?: number;
  error?: string;
  skipped?: boolean;
};

export type DualCompareVerdict =
  | "agree"
  | "soft_agree"
  | "disagree"
  | "secondary_unavailable";

export type DualConvertCompare = {
  primary: ConvertSide;
  secondary: ConvertSide;
  verdict: DualCompareVerdict;
  overlap_ratio: number;
  primary_only_tokens: string[];
  secondary_only_tokens: string[];
  shared_tokens: string[];
  note: string;
};

const LLAMA_BASE = "https://api.cloud.llamaindex.ai";

function repoRoot(): string {
  const candidates = [
    path.join(process.cwd(), "Scripts"),
    path.join(process.cwd(), "..", "Scripts"),
  ];
  for (const c of candidates) {
    if (fs.existsSync(path.join(c, "order_code_seq.json"))) return path.dirname(c);
  }
  return path.join(process.cwd(), "..");
}

export function dualCompareEnabled(): boolean {
  // LlamaParse = 技术参考项；默认永不调用。仅显式 OCR_DUAL_COMPARE=on + Key 才开。
  const flag = (process.env.OCR_DUAL_COMPARE || "").trim().toLowerCase();
  if (flag !== "on" && flag !== "1" && flag !== "true") return false;
  return Boolean(process.env.LLAMA_CLOUD_API_KEY?.trim());
}

function normalizeTokens(text: string): string[] {
  const upper = text.toUpperCase();
  const out: string[] = [];
  const seen = new Set<string>();
  const push = (t: string) => {
    if (!t || seen.has(t)) return;
    seen.add(t);
    out.push(t);
  };
  for (const m of upper.matchAll(/\bFBA[0-9A-Z]{8,}\b/g)) push(m[0]);
  for (const m of upper.matchAll(/\bSTAR-[0-9A-Z]+\b/g)) push(m[0]);
  for (const m of upper.matchAll(/\b\d{1,7}(?:\.\d{1,2})?\b/g)) {
    const n = Number(m[0]);
    if (n > 0 && n < 1_000_000) push(n.toFixed(2));
  }
  // CJK chunks length>=2
  for (const m of text.matchAll(/[\u4e00-\u9fff]{2,8}/g)) push(m[0]);
  return out;
}

export function compareConvertTexts(
  primaryText: string,
  secondaryText: string,
): Pick<
  DualConvertCompare,
  | "verdict"
  | "overlap_ratio"
  | "primary_only_tokens"
  | "secondary_only_tokens"
  | "shared_tokens"
  | "note"
> {
  const a = new Set(normalizeTokens(primaryText));
  const b = new Set(normalizeTokens(secondaryText));
  if (a.size === 0 && b.size === 0) {
    const alike =
      primaryText.replace(/\s+/g, "").slice(0, 80) ===
      secondaryText.replace(/\s+/g, "").slice(0, 80);
    return {
      verdict: alike ? "soft_agree" : "disagree",
      overlap_ratio: alike ? 1 : 0,
      primary_only_tokens: [],
      secondary_only_tokens: [],
      shared_tokens: [],
      note: alike ? "双方几乎无结构化 token，原文前缀相近" : "双方几乎无结构化 token，原文差异大",
    };
  }
  const shared: string[] = [];
  const primaryOnly: string[] = [];
  const secondaryOnly: string[] = [];
  for (const t of a) {
    if (b.has(t)) shared.push(t);
    else primaryOnly.push(t);
  }
  for (const t of b) {
    if (!a.has(t)) secondaryOnly.push(t);
  }
  const denom = Math.max(a.size, b.size, 1);
  const overlap = shared.length / denom;
  let verdict: DualCompareVerdict;
  if (overlap >= 0.75 && primaryOnly.length <= 2 && secondaryOnly.length <= 2) {
    verdict = "agree";
  } else if (overlap >= 0.4) {
    verdict = "soft_agree";
  } else {
    verdict = "disagree";
  }
  return {
    verdict,
    overlap_ratio: Number(overlap.toFixed(3)),
    primary_only_tokens: primaryOnly.slice(0, 20),
    secondary_only_tokens: secondaryOnly.slice(0, 20),
    shared_tokens: shared.slice(0, 30),
    note:
      verdict === "agree"
        ? "双引擎关键 token 高度一致"
        : verdict === "soft_agree"
          ? "部分一致，请扫一眼"
          : "差异较大：默认仍用主路径，请你确认",
  };
}

async function sleep(ms: number) {
  await new Promise((r) => setTimeout(r, ms));
}

/** 备用：仅主路径失败后调用。不删除、不作为默认。 */
export async function convertWithTesseractBackup(buf: Buffer): Promise<ConvertSide> {
  const t0 = Date.now();
  try {
    const { createWorker } = await import("tesseract.js");
    const worker = await createWorker("eng+chi_sim");
    try {
      const ret = await worker.recognize(buf);
      const text = ret.data.text || "";
      return {
        engine: "local_tesseract",
        ok: Boolean(text.trim()),
        text,
        ms: Date.now() - t0,
      };
    } finally {
      await worker.terminate();
    }
  } catch (e) {
    try {
      const { createWorker } = await import("tesseract.js");
      const worker = await createWorker("eng");
      try {
        const ret = await worker.recognize(buf);
        const text = ret.data.text || "";
        return {
          engine: "local_tesseract",
          ok: Boolean(text.trim()),
          text,
          ms: Date.now() - t0,
          error: e instanceof Error ? e.message : String(e),
        };
      } finally {
        await worker.terminate();
      }
    } catch (e2) {
      return {
        engine: "local_tesseract",
        ok: false,
        text: "",
        ms: Date.now() - t0,
        error: e2 instanceof Error ? e2.message : String(e2),
      };
    }
  }
}

/** LlamaParse v1 upload + poll text（无密钥则 skip；默认不调用） */
export async function convertWithLlamaParse(opts: {
  buf: Buffer;
  filename: string;
  timeoutMs?: number;
}): Promise<ConvertSide> {
  const key = process.env.LLAMA_CLOUD_API_KEY?.trim();
  if (!key) {
    return {
      engine: "llamaparse",
      ok: false,
      text: "",
      skipped: true,
      error: "LLAMA_CLOUD_API_KEY missing",
    };
  }
  const t0 = Date.now();
  try {
    const form = new FormData();
    const blob = new Blob([new Uint8Array(opts.buf)]);
    form.append("file", blob, opts.filename || "upload.bin");

    const up = await fetch(`${LLAMA_BASE}/api/v1/parsing/upload`, {
      method: "POST",
      headers: { Authorization: `Bearer ${key}` },
      body: form,
    });
    if (!up.ok) {
      const body = await up.text().catch(() => "");
      return {
        engine: "llamaparse",
        ok: false,
        text: "",
        ms: Date.now() - t0,
        error: `upload_http_${up.status}: ${body.slice(0, 200)}`,
      };
    }
    const upJson = (await up.json()) as { id?: string };
    const jobId = upJson.id;
    if (!jobId) {
      return {
        engine: "llamaparse",
        ok: false,
        text: "",
        ms: Date.now() - t0,
        error: "upload_no_job_id",
      };
    }

    const deadline = Date.now() + (opts.timeoutMs ?? 90_000);
    let status = "PENDING";
    while (Date.now() < deadline) {
      const st = await fetch(`${LLAMA_BASE}/api/v1/parsing/job/${jobId}`, {
        headers: { Authorization: `Bearer ${key}` },
      });
      if (!st.ok) {
        return {
          engine: "llamaparse",
          ok: false,
          text: "",
          ms: Date.now() - t0,
          error: `status_http_${st.status}`,
        };
      }
      const sj = (await st.json()) as { status?: string; error?: string };
      status = (sj.status || "").toUpperCase();
      if (status === "SUCCESS" || status === "COMPLETED") break;
      if (status === "ERROR" || status === "FAILED") {
        return {
          engine: "llamaparse",
          ok: false,
          text: "",
          ms: Date.now() - t0,
          error: sj.error || "llamaparse_failed",
        };
      }
      await sleep(1500);
    }
    if (status !== "SUCCESS" && status !== "COMPLETED") {
      return {
        engine: "llamaparse",
        ok: false,
        text: "",
        ms: Date.now() - t0,
        error: `timeout_status_${status}`,
      };
    }

    const res = await fetch(`${LLAMA_BASE}/api/v1/parsing/job/${jobId}/result/text`, {
      headers: { Authorization: `Bearer ${key}` },
    });
    if (!res.ok) {
      // fallback markdown
      const md = await fetch(`${LLAMA_BASE}/api/v1/parsing/job/${jobId}/result/markdown`, {
        headers: { Authorization: `Bearer ${key}` },
      });
      if (!md.ok) {
        return {
          engine: "llamaparse",
          ok: false,
          text: "",
          ms: Date.now() - t0,
          error: `result_http_${res.status}`,
        };
      }
      const mdJson = (await md.json()) as { markdown?: string; text?: string };
      const text = mdJson.markdown || mdJson.text || "";
      return {
        engine: "llamaparse",
        ok: Boolean(text),
        text,
        ms: Date.now() - t0,
      };
    }
    const tj = (await res.json()) as { text?: string; markdown?: string };
    const text = tj.text || tj.markdown || "";
    return {
      engine: "llamaparse",
      ok: Boolean(text),
      text,
      ms: Date.now() - t0,
    };
  } catch (e) {
    return {
      engine: "llamaparse",
      ok: false,
      text: "",
      ms: Date.now() - t0,
      error: e instanceof Error ? e.message : String(e),
    };
  }
}

export async function dualConvertCompare(opts: {
  primary: ConvertSide;
  buf: Buffer;
  filename: string;
  persist?: boolean;
  tag?: string;
}): Promise<DualConvertCompare> {
  let secondary: ConvertSide;
  if (!dualCompareEnabled()) {
    secondary = {
      engine: "llamaparse",
      ok: false,
      text: "",
      skipped: true,
      error: "dual_compare_disabled_or_no_key",
    };
  } else {
    secondary = await convertWithLlamaParse({
      buf: opts.buf,
      filename: opts.filename,
    });
  }

  if (secondary.skipped || !secondary.ok) {
    const report: DualConvertCompare = {
      primary: opts.primary,
      secondary,
      verdict: "secondary_unavailable",
      overlap_ratio: 0,
      primary_only_tokens: [],
      secondary_only_tokens: [],
      shared_tokens: [],
      note: secondary.error || "LlamaParse 未运行；主路径照常",
    };
    if (opts.persist) persistCompare(report, opts.tag);
    return report;
  }

  const cmp = compareConvertTexts(opts.primary.text || "", secondary.text || "");
  const report: DualConvertCompare = {
    primary: opts.primary,
    secondary,
    ...cmp,
  };
  if (opts.persist) persistCompare(report, opts.tag);
  return report;
}

function persistCompare(report: DualConvertCompare, tag?: string) {
  try {
    const dir = path.join(repoRoot(), "2_Processed_AI", "ocr_dual_compare");
    fs.mkdirSync(dir, { recursive: true });
    const name = `${new Date().toISOString().replace(/[:.]/g, "-")}_${tag || "cmp"}.json`;
    const slim = {
      at: new Date().toISOString(),
      verdict: report.verdict,
      overlap_ratio: report.overlap_ratio,
      note: report.note,
      primary: {
        engine: report.primary.engine,
        ok: report.primary.ok,
        ms: report.primary.ms,
        text_preview: (report.primary.text || "").slice(0, 400),
      },
      secondary: {
        engine: report.secondary.engine,
        ok: report.secondary.ok,
        skipped: report.secondary.skipped,
        ms: report.secondary.ms,
        error: report.secondary.error,
        text_preview: (report.secondary.text || "").slice(0, 400),
      },
      shared_tokens: report.shared_tokens,
      primary_only_tokens: report.primary_only_tokens,
      secondary_only_tokens: report.secondary_only_tokens,
    };
    fs.writeFileSync(path.join(dir, name), JSON.stringify(slim, null, 2), "utf8");
  } catch {
    // non-fatal
  }
}
