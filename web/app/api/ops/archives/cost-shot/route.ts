import { NextResponse } from "next/server";
import { isAdminAuthenticated } from "@/lib/admin-auth";
import {
  patchArchiveEntry,
  readArchiveIndexFile,
} from "@/lib/pipeline/archive-index";
import { recognizeCostShot } from "@/lib/pipeline/cost-shot-recognize";
import { uploadJobObject } from "@/lib/storage/artifacts";

export const runtime = "nodejs";

/** 上传单价截图 → OCR → 待确认（不落单价到云端） */
export async function POST(req: Request) {
  if (!(await isAdminAuthenticated())) {
    return NextResponse.json({ ok: false, error: "unauthorized" }, { status: 401 });
  }

  const form = await req.formData();
  const entryId = String(form.get("entry_id") || "");
  const file = form.get("file");
  if (!entryId || !(file instanceof File)) {
    return NextResponse.json(
      { ok: false, error: "entry_id and file required" },
      { status: 400 },
    );
  }

  const fileEntries = readArchiveIndexFile().entries;
  const entry = fileEntries.find((e) => e.id === entryId || e.job_id === entryId);
  if (!entry) {
    return NextResponse.json({ ok: false, error: "entry_not_found" }, { status: 404 });
  }

  const buf = Buffer.from(await file.arrayBuffer());
  const safeName = file.name.replace(/[^\w.\u4e00-\u9fff-]+/g, "_").slice(0, 120);
  const storagePath = `ship-stats/${entry.id}/cost_shot/${Date.now()}_${safeName}`;

  const stored = await uploadJobObject({
    bucket: "job-uploads",
    storagePath,
    body: buf,
    upsert: true,
  });

  const specLabels = (entry.spec_details || []).map((s) => ({
    label: s.label || [s.size, s.color, s.strips_per_pack != null ? `${s.strips_per_pack}条` : ""]
      .filter(Boolean)
      .join(" ") || "规格",
    carton_count: s.carton_count,
  }));

  const proposal = await recognizeCostShot({
    buf,
    filename: file.name,
    specLabels,
  });

  const patched = patchArchiveEntry(entry.id, {
    cost: {
      status: "awaiting_confirm",
      batch_total_cost: entry.cost?.batch_total_cost ?? null,
      screenshot: {
        name: file.name,
        storage_path: stored.storage_path,
        backend: stored.backend,
        at: new Date().toISOString(),
      },
      pending: {
        ocr_text_preview: proposal.ocr_text_preview,
        proposed_lines: proposal.proposed_lines,
        proposed_batch_total: proposal.proposed_batch_total,
        dual_compare: proposal.dual_compare
          ? {
              verdict: proposal.dual_compare.verdict,
              overlap_ratio: proposal.dual_compare.overlap_ratio,
              note: proposal.dual_compare.note,
              secondary_preview: (proposal.dual_compare.secondary.text || "").slice(0, 240),
              primary_only_tokens: proposal.dual_compare.primary_only_tokens,
              secondary_only_tokens: proposal.dual_compare.secondary_only_tokens,
            }
          : undefined,
      },
    },
  });

  if (!patched.ok) {
    return NextResponse.json(
      { ok: false, error: patched.error || "patch_failed" },
      { status: 500 },
    );
  }

  return NextResponse.json({
    ok: true,
    entry: patched.entry,
    proposal,
    storage: {
      backend: stored.backend,
      path: stored.storage_path,
      warn: stored.error,
    },
    message: "识别完成，请核对后确认。确认前云端不写规格单价。",
  });
}
