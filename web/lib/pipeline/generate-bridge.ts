/**
 * Publish Python step outputs into Storage + job.meta.artifacts
 */

import fs from "fs";
import os from "os";
import path from "path";
import type { JobRow } from "./jobs";
import { updateJobMeta } from "./jobs";
import {
  parsePythonResultJson,
  runPythonScript,
  getRepoRoot,
} from "./python-runner";
import { getMeta, type JobPhase, type RunStepId } from "./stages";
import {
  bucketForDirection,
  recordJobArtifact,
  uploadJobObject,
} from "@/lib/storage/artifacts";
import { detectExecutionPlane } from "@/lib/runtime/execution-plane";
import { OUTPUT_SECTIONS, storagePath } from "./schema";

export type GenerateBridgeResult = {
  ok: boolean;
  mock: boolean;
  message: string;
  job: JobRow;
  issues?: { code: string; message: string }[];
  backend?: string;
};

function workDirFor(jobId: string): string {
  return path.join(os.tmpdir(), "autoexport-jobs", jobId);
}

function prefixForSection(sectionId: string): string | null {
  const sec = OUTPUT_SECTIONS.find((s) => s.id === sectionId);
  if (sec) return sec.storage_prefix;
  if (sectionId === "audit_archive") return "jobs/{job_id}/archive/";
  return null;
}

async function publishFiles(
  job: JobRow,
  files: { section_id: string; path: string; file_name: string }[],
  phase?: JobPhase,
): Promise<JobRow> {
  const artifacts = { ...(getMeta(job).artifacts || {}) };
  const storage_files = {
    ...((getMeta(job).storage_files as Record<string, unknown>) || {}),
  } as Record<
    string,
    {
      name: string;
      storage_path: string;
      backend: string;
      sha256: string;
      byte_size: number;
    }[]
  >;

  const notesBySection: Record<string, string> = {};
  const plane = detectExecutionPlane();

  for (const f of files) {
    if (!fs.existsSync(f.path)) continue;
    const body = fs.readFileSync(f.path);
    const prefix = prefixForSection(f.section_id);
    if (!prefix) continue;
    const key = `${storagePath(job.id, prefix)}${f.file_name}`;
    const up = await uploadJobObject({
      bucket: bucketForDirection("out"),
      storagePath: key,
      body,
      plane,
    });
    if (!up.ok) {
      artifacts[f.section_id] = {
        status: "error",
        note: up.error || "upload_failed",
      };
      continue;
    }
    await recordJobArtifact({
      job_id: job.id,
      section_id: f.section_id,
      direction: "out",
      file_name: f.file_name,
      storage_path: key,
      save_mode: "draft",
      byte_size: up.byte_size,
      sha256: up.sha256,
      meta: { backend: up.backend },
    });
    const list = storage_files[f.section_id] || [];
    list.push({
      name: f.file_name,
      storage_path: key,
      backend: up.backend,
      sha256: up.sha256,
      byte_size: up.byte_size,
    });
    storage_files[f.section_id] = list;

    const isSidecar =
      /\.json$/i.test(f.file_name) &&
      (/draft/i.test(f.file_name) || /manifest/i.test(f.file_name));
    if (!isSidecar || !notesBySection[f.section_id]) {
      notesBySection[f.section_id] = `${f.file_name} @ ${up.backend}:${key}`;
    }
  }

  for (const [sectionId, note] of Object.entries(notesBySection)) {
    artifacts[sectionId] = { status: "draft", note };
  }

  const prevSync = getMeta(job).sync || {};
  const updated = await updateJobMeta(job.id, {
    artifacts,
    storage_files,
    ...(phase ? { phase } : {}),
    ...(plane === "cloud"
      ? {
          sync: {
            ...prevSync,
            cloud_ready: true,
          },
        }
      : {}),
  });
  return updated || job;
}

/** Canonical: Shipments/{project}/订单表/{order workbook} */
function mirrorOrderToShipments(job: JobRow, work: string, fileName: string): string | null {
  const project = job.project_code;
  if (!project || !fileName) return null;
  const src = path.join(work, "out", "order", fileName);
  if (!fs.existsSync(src)) return null;
  const destDir = path.join(
    getRepoRoot(),
    "1_Input_Raw",
    "Shipments",
    project,
    "订单表",
  );
  fs.mkdirSync(destDir, { recursive: true });
  const dest = path.join(destDir, fileName);
  fs.copyFileSync(src, dest);
  return dest;
}

/** Canonical business path: Shipments/{project}/产品标签/… (in addition to job blobs). */
function mirrorLabelsToShipments(job: JobRow, work: string): string | null {
  const meta = getMeta(job);
  const project = job.project_code;
  const orderCode = meta.order_code;
  if (!project || !orderCode) return null;
  const bundleSrc = path.join(work, "out", "product_labels", `${orderCode}标签`);
  if (!fs.existsSync(bundleSrc)) return null;
  const destRoot = path.join(
    getRepoRoot(),
    "1_Input_Raw",
    "Shipments",
    project,
    "产品标签",
    `${orderCode}标签`,
  );
  fs.mkdirSync(path.dirname(destRoot), { recursive: true });
  fs.cpSync(bundleSrc, destRoot, { recursive: true });
  return destRoot;
}

export async function runPythonGenerateStep(
  job: JobRow,
  step: Extract<RunStepId, "gen_order" | "gen_product_labels" | "gen_trio">,
): Promise<GenerateBridgeResult> {
  const work = workDirFor(job.id);
  fs.mkdirSync(work, { recursive: true });
  const jobJson = path.join(work, "job.json");
  fs.writeFileSync(
    jobJson,
    JSON.stringify(
      {
        id: job.id,
        project_code: job.project_code,
        entity_code: job.entity_code,
        ship_date: job.ship_date,
        gate_final: job.gate_final,
        meta: job.meta,
      },
      null,
      2,
    ),
    "utf8",
  );

  const py = await runPythonScript({
    scriptRel: "Scripts/19_cloud_job_step.py",
    args: ["--step", step, "--job-json", jobJson, "--work-dir", work],
    timeoutMs: 180_000,
  });

  if (py.skipped) {
    return {
      ok: false,
      mock: true,
      message: py.reason || "Python runner skipped",
      job,
      issues: [{ code: "python_runner_skipped", message: py.reason || "skipped" }],
    };
  }

  const parsed = parsePythonResultJson(py.stdout);
  const files = (parsed?.files as { section_id: string; path: string; file_name: string }[]) || [];
  const issues = (parsed?.issues as { code: string; message: string }[]) || [];

  if (files.length) {
    const phase =
      step === "gen_order"
        ? ("order_labels" as JobPhase)
        : step === "gen_product_labels"
          ? ("await_carton" as JobPhase)
          : ("await_inbound" as JobPhase);
    const updated = await publishFiles(job, files, step === "gen_trio" ? undefined : phase);
    let shipNote = "";
    if (parsed?.ok && step === "gen_order") {
      const xlsx = files.find((f) => /\.xlsx$/i.test(f.file_name));
      try {
        const p = xlsx ? mirrorOrderToShipments(updated, work, xlsx.file_name) : null;
        if (p) shipNote = `；业务落盘 ${p}`;
      } catch {
        /* non-fatal */
      }
    }
    if (step === "gen_product_labels" && parsed?.ok) {
      try {
        const p = mirrorLabelsToShipments(updated, work);
        if (p) shipNote = `；业务落盘 ${p}`;
      } catch {
        /* non-fatal */
      }
    }
    if (parsed?.ok) {
      return {
        ok: true,
        mock: false,
        message:
          step === "gen_order"
            ? `订单已生成并入库 Storage（${files.length} 个文件；下载优先 xlsx）${shipNote}`
            : step === "gen_product_labels"
              ? `产品标签包已从源库只读复制（${files.length} 个文件；下载优先 PDF）${shipNote}`
              : `三表已生成（出货+货代+报关，${files.length} 个文件）`,
        job: updated,
        backend: "python+storage",
      };
    }
    return {
      ok: false,
      mock: false,
      message: String(parsed?.error || py.stderr || "生成失败"),
      job: updated,
      issues:
        issues.length > 0
          ? issues
          : [{ code: "generate_failed", message: String(parsed?.error || py.stderr) }],
    };
  }

  return {
    ok: false,
    mock: Boolean(py.skipped),
    message: parsed
      ? String(parsed.error || "generate failed")
      : py.timedOut
        ? "Python 超时"
        : `Python 失败 exit=${py.exitCode}: ${py.stderr.slice(0, 400)}`,
    job,
    issues: issues.length
      ? issues
      : [{ code: "python_failed", message: py.stderr.slice(0, 500) || py.stdout.slice(0, 500) }],
  };
}

export function ensureRepoVisible(): string {
  return getRepoRoot();
}
