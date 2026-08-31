import { NextResponse } from "next/server";
import { getJob, updateJobMeta } from "@/lib/pipeline/jobs";
import { findInputSection, storagePath } from "@/lib/pipeline/schema";
import { extOf, isAllowedExt } from "@/lib/pipeline/wave-preflight";
import { recognizeFileBufferAsync } from "@/lib/fba-recognize";
import { getMeta } from "@/lib/pipeline/stages";
import {
  bucketForDirection,
  recordJobArtifact,
  uploadJobObject,
  contentTypeOf,
} from "@/lib/storage/artifacts";
import { getEffectivePlane } from "@/lib/runtime/execution-plane";

type Ctx = { params: Promise<{ id: string }> };

/**
 * Upload multipart → Storage by execution plane (single-write).
 *  - field "section": ship_plan | carton_and_tracking | freight_inbound
 *  - field "file": binary
 */
export async function POST(req: Request, ctx: Ctx) {
  const { id } = await ctx.params;
  const job = await getJob(id);
  if (!job) {
    return NextResponse.json({ ok: false, error: "job not found" }, { status: 404 });
  }

  const form = await req.formData().catch(() => null);
  if (!form) {
    return NextResponse.json({ ok: false, error: "multipart form required" }, { status: 400 });
  }
  const sectionRaw = String(form.get("section") || "");
  const file = form.get("file");
  const sec = findInputSection(sectionRaw);
  if (!sec) {
    return NextResponse.json(
      {
        ok: false,
        error: "invalid section",
        allowed: ["ship_plan", "carton_and_tracking", "freight_inbound", "order_plan"],
      },
      { status: 400 },
    );
  }

  const fileName =
    file && typeof file === "object" && "name" in file
      ? String((file as File).name)
      : "";
  if (!fileName) {
    return NextResponse.json({ ok: false, error: "file required" }, { status: 400 });
  }
  if (!isAllowedExt(sec.id, fileName)) {
    return NextResponse.json(
      {
        ok: false,
        error: `格式不符：${fileName}`,
        accept: sec.accept,
      },
      { status: 400 },
    );
  }

  const size =
    file && typeof file === "object" && "size" in file ? Number((file as File).size) : 0;
  const maxBytes = (sec.max_mb || 20) * 1024 * 1024;
  if (size > maxBytes) {
    return NextResponse.json(
      { ok: false, error: `超过大小限制 ${sec.max_mb}MB` },
      { status: 400 },
    );
  }

  if (!file || typeof file !== "object" || !("arrayBuffer" in file)) {
    return NextResponse.json({ ok: false, error: "file required" }, { status: 400 });
  }

  const buf = Buffer.from(await (file as File).arrayBuffer());
  const objectPath = `${storagePath(id, sec.storage_prefix)}${fileName}`;
  const uploadKey = sec.id as "ship_plan" | "carton_and_tracking" | "freight_inbound";
  const plane = getEffectivePlane(req);

  const stored = await uploadJobObject({
    bucket: bucketForDirection("in"),
    storagePath: objectPath,
    body: buf,
    contentType: contentTypeOf(fileName),
    plane,
  });
  if (!stored.ok) {
    return NextResponse.json(
      { ok: false, error: stored.error || "upload_failed", plane },
      { status: 502 },
    );
  }

  await recordJobArtifact({
    job_id: id,
    section_id: sec.id,
    direction: "in",
    file_name: fileName,
    storage_path: objectPath,
    save_mode: "upload_raw",
    byte_size: stored.byte_size,
    sha256: stored.sha256,
    meta: { backend: stored.backend },
  });

  const meta = getMeta(job);
  const upload_files = { ...(meta.upload_files || {}) };
  const list = [...(upload_files[uploadKey] || [])];
  list.push({
    name: fileName,
    size: stored.byte_size,
    ext: extOf(fileName),
    at: new Date().toISOString(),
  });
  upload_files[uploadKey] = list;

  const storage_files = { ...(meta.storage_files || {}) };
  const sList = [...(storage_files[uploadKey] || [])];
  sList.push({
    name: fileName,
    storage_path: objectPath,
    backend: stored.backend,
    sha256: stored.sha256,
    byte_size: stored.byte_size,
  });
  storage_files[uploadKey] = sList;

  const patch: Parameters<typeof updateJobMeta>[1] = {
    uploads: { [uploadKey]: true },
    upload_files,
    storage_files,
  };

  let recognition: Awaited<ReturnType<typeof recognizeFileBufferAsync>> | null =
    null;
  if (uploadKey === "carton_and_tracking") {
    try {
      const newRows = await recognizeFileBufferAsync(buf, fileName);
      const prev = meta.carton_recognition?.rows || [];
      const normalized = newRows.map((row) => ({
        ...row,
        tracking_id: row.tracking_id || "",
      }));
      patch.carton_recognition = {
        rows: [...prev, ...normalized],
        tracking_id:
          normalized.find((r) => r.tracking_id)?.tracking_id ||
          meta.carton_recognition?.tracking_id ||
          "",
        user_confirmed: false,
      };
      recognition = normalized;
    } catch {
      patch.carton_recognition = {
        rows: [
          ...(meta.carton_recognition?.rows || []),
          {
            warehouse_code: "",
            fba_shipment_id: "",
            reference_id: "",
            carton_count: null,
            strip_count: null,
            source_filename: fileName,
            recognize_notes: "识别失败，请手填后确认",
            tracking_id: "",
          },
        ],
        tracking_id: meta.carton_recognition?.tracking_id || "",
        user_confirmed: false,
      };
    }
  }

  await updateJobMeta(id, patch);

  return NextResponse.json({
    ok: true,
    mode: stored.backend === "supabase" ? "stored" : "stored_local_fallback",
    job_id: id,
    section: sec.id,
    label: sec.label,
    accept: sec.accept,
    max_mb: sec.max_mb,
    storage_path: objectPath,
    storage_backend: stored.backend,
    sha256: stored.sha256,
    byte_size: stored.byte_size,
    save_mode: "upload_raw",
    recognition,
    warning: stored.error,
    note:
      uploadKey === "carton_and_tracking"
        ? "仅 PDF 文本层归类（无 OCR）。有则填、无则空置手补；请核对后点「确认识别结果」。"
        : undefined,
  });
}
