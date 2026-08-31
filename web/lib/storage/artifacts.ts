/**
 * Job artifact storage — single-write by execution plane.
 * Buckets: job-uploads (in), job-outputs (out/archive)
 * Local: 2_Processed_AI/cloud_job_blobs/{bucket}/{storage_path}
 * Cloud: Supabase only (no mid-job dual-write)
 * Sync after complete: POST /api/jobs/[id]/sync
 */

import { createHash } from "crypto";
import fs from "fs";
import path from "path";
import { adminSupabase } from "@/lib/pipeline/jobs";
import type { SaveMode, SectionDirection } from "@/lib/pipeline/schema";
import {
  detectExecutionPlane,
  type ExecutionPlane,
} from "@/lib/runtime/execution-plane";

export type StorageBucket = "job-uploads" | "job-outputs";

export type UploadResult = {
  ok: boolean;
  backend: "supabase" | "local";
  bucket: StorageBucket;
  storage_path: string;
  sha256: string;
  byte_size: number;
  error?: string;
};

export type SignedUrlResult = {
  ok: boolean;
  backend: "supabase" | "local";
  url?: string;
  local_path?: string;
  error?: string;
};

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

export function localBlobRoot(): string {
  return path.join(repoRoot(), "2_Processed_AI", "cloud_job_blobs");
}

export function localBlobAbsolute(bucket: StorageBucket, storagePath: string): string {
  return path.join(localBlobRoot(), bucket, storagePath.replace(/\//g, path.sep));
}

export function bucketForDirection(dir: SectionDirection): StorageBucket {
  return dir === "in" ? "job-uploads" : "job-outputs";
}

export function sha256Of(buf: Buffer): string {
  return createHash("sha256").update(buf).digest("hex");
}

function contentTypeOf(fileName: string): string {
  const ext = path.extname(fileName).toLowerCase();
  const map: Record<string, string> = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".csv": "text/csv",
    ".json": "application/json",
    ".zip": "application/zip",
  };
  return map[ext] || "application/octet-stream";
}

export function writeLocal(bucket: StorageBucket, storagePath: string, body: Buffer): void {
  const abs = localBlobAbsolute(bucket, storagePath);
  fs.mkdirSync(path.dirname(abs), { recursive: true });
  fs.writeFileSync(abs, body);
}

/**
 * Mid-job upload: write ONLY the current execution plane.
 * Use sync push/pull for cross-plane transfer after work completes.
 */
export async function uploadJobObject(opts: {
  bucket: StorageBucket;
  storagePath: string;
  body: Buffer;
  contentType?: string;
  upsert?: boolean;
  plane?: ExecutionPlane;
}): Promise<UploadResult> {
  const sha256 = sha256Of(opts.body);
  const contentType = opts.contentType || contentTypeOf(opts.storagePath);
  const plane = opts.plane || detectExecutionPlane();

  if (plane === "local") {
    writeLocal(opts.bucket, opts.storagePath, opts.body);
    return {
      ok: true,
      backend: "local",
      bucket: opts.bucket,
      storage_path: opts.storagePath,
      sha256,
      byte_size: opts.body.length,
    };
  }

  // cloud plane — Supabase only
  const sb = adminSupabase();
  if (!sb) {
    return {
      ok: false,
      backend: "supabase",
      bucket: opts.bucket,
      storage_path: opts.storagePath,
      sha256,
      byte_size: opts.body.length,
      error: "cloud_plane_requires_supabase",
    };
  }
  const { error } = await sb.storage.from(opts.bucket).upload(opts.storagePath, opts.body, {
    contentType,
    upsert: opts.upsert !== false,
  });
  if (error) {
    return {
      ok: false,
      backend: "supabase",
      bucket: opts.bucket,
      storage_path: opts.storagePath,
      sha256,
      byte_size: opts.body.length,
      error: `supabase_upload_failed: ${error.message}`,
    };
  }
  return {
    ok: true,
    backend: "supabase",
    bucket: opts.bucket,
    storage_path: opts.storagePath,
    sha256,
    byte_size: opts.body.length,
  };
}

/** Explicit push: local blob → Supabase (completion sync). */
export async function pushLocalObjectToSupabase(opts: {
  bucket: StorageBucket;
  storagePath: string;
  body?: Buffer;
  upsert?: boolean;
}): Promise<UploadResult> {
  const body =
    opts.body ||
    (fs.existsSync(localBlobAbsolute(opts.bucket, opts.storagePath))
      ? fs.readFileSync(localBlobAbsolute(opts.bucket, opts.storagePath))
      : null);
  if (!body) {
    return {
      ok: false,
      backend: "local",
      bucket: opts.bucket,
      storage_path: opts.storagePath,
      sha256: "",
      byte_size: 0,
      error: "local_object_missing",
    };
  }
  const sha256 = sha256Of(body);
  const sb = adminSupabase();
  if (!sb) {
    return {
      ok: false,
      backend: "supabase",
      bucket: opts.bucket,
      storage_path: opts.storagePath,
      sha256,
      byte_size: body.length,
      error: "supabase_unavailable",
    };
  }
  const { error } = await sb.storage.from(opts.bucket).upload(opts.storagePath, body, {
    contentType: contentTypeOf(opts.storagePath),
    upsert: opts.upsert !== false,
  });
  if (error) {
    return {
      ok: false,
      backend: "supabase",
      bucket: opts.bucket,
      storage_path: opts.storagePath,
      sha256,
      byte_size: body.length,
      error: error.message,
    };
  }
  return {
    ok: true,
    backend: "supabase",
    bucket: opts.bucket,
    storage_path: opts.storagePath,
    sha256,
    byte_size: body.length,
  };
}

/** Explicit pull: Supabase → local blob. */
export async function pullSupabaseObjectToLocal(opts: {
  bucket: StorageBucket;
  storagePath: string;
}): Promise<UploadResult> {
  const sb = adminSupabase();
  if (!sb) {
    return {
      ok: false,
      backend: "supabase",
      bucket: opts.bucket,
      storage_path: opts.storagePath,
      sha256: "",
      byte_size: 0,
      error: "supabase_unavailable",
    };
  }
  const { data, error } = await sb.storage.from(opts.bucket).download(opts.storagePath);
  if (error || !data) {
    return {
      ok: false,
      backend: "supabase",
      bucket: opts.bucket,
      storage_path: opts.storagePath,
      sha256: "",
      byte_size: 0,
      error: error?.message || "download_failed",
    };
  }
  const body = Buffer.from(await data.arrayBuffer());
  writeLocal(opts.bucket, opts.storagePath, body);
  return {
    ok: true,
    backend: "local",
    bucket: opts.bucket,
    storage_path: opts.storagePath,
    sha256: sha256Of(body),
    byte_size: body.length,
  };
}

function localSignedResult(
  bucket: StorageBucket,
  storagePath: string,
): SignedUrlResult | null {
  const abs = localBlobAbsolute(bucket, storagePath);
  if (!fs.existsSync(abs)) return null;
  return {
    ok: true,
    backend: "local",
    local_path: abs,
    url: `/api/jobs/local-blob?bucket=${encodeURIComponent(bucket)}&path=${encodeURIComponent(storagePath)}`,
  };
}

export async function createSignedDownloadUrl(
  bucket: StorageBucket,
  storagePath: string,
  expiresSec = 3600,
  preferredBackend?: "supabase" | "local" | string,
): Promise<SignedUrlResult> {
  const plane = detectExecutionPlane();

  if (preferredBackend === "local" || (plane === "local" && preferredBackend !== "supabase")) {
    const local = localSignedResult(bucket, storagePath);
    if (local) return local;
    if (preferredBackend === "local") {
      return { ok: false, backend: "local", error: "local object not found" };
    }
  }

  if (preferredBackend === "supabase" || plane === "cloud") {
    const sb = adminSupabase();
    if (sb) {
      const { data, error } = await sb.storage
        .from(bucket)
        .createSignedUrl(storagePath, expiresSec);
      if (!error && data?.signedUrl) {
        return { ok: true, backend: "supabase", url: data.signedUrl };
      }
      return {
        ok: false,
        backend: "supabase",
        error: error?.message || "sign failed",
      };
    }
    return { ok: false, backend: "supabase", error: "supabase_unavailable" };
  }

  // local plane, no preferred: try local then (only if explicitly needed) stop
  const local = localSignedResult(bucket, storagePath);
  if (local) return local;
  return { ok: false, backend: "local", error: "object not found on local plane" };
}

export async function readJobObject(
  bucket: StorageBucket,
  storagePath: string,
  preferredBackend?: "supabase" | "local",
): Promise<{ ok: boolean; body?: Buffer; error?: string; backend?: "supabase" | "local" }> {
  const plane = detectExecutionPlane();
  const order: ("local" | "supabase")[] =
    preferredBackend === "supabase"
      ? ["supabase", "local"]
      : preferredBackend === "local"
        ? ["local"]
        : plane === "cloud"
          ? ["supabase"]
          : ["local"];

  for (const b of order) {
    if (b === "local") {
      const abs = localBlobAbsolute(bucket, storagePath);
      if (fs.existsSync(abs)) {
        return { ok: true, body: fs.readFileSync(abs), backend: "local" };
      }
    } else {
      const sb = adminSupabase();
      if (sb) {
        const { data, error } = await sb.storage.from(bucket).download(storagePath);
        if (!error && data) {
          const ab = await data.arrayBuffer();
          return { ok: true, body: Buffer.from(ab), backend: "supabase" };
        }
      }
    }
  }
  return { ok: false, error: "not found" };
}

export async function recordJobArtifact(row: {
  job_id: string;
  section_id: string;
  direction: SectionDirection;
  file_name: string;
  storage_path: string;
  save_mode: SaveMode;
  content_type?: string;
  byte_size?: number;
  sha256?: string;
  meta?: Record<string, unknown>;
}): Promise<{ ok: boolean; source: "db" | "skipped"; error?: string }> {
  const sb = adminSupabase();
  if (!sb) return { ok: true, source: "skipped", error: "no supabase; artifact only in job.meta" };
  const { error } = await sb.from("job_artifacts").insert({
    job_id: row.job_id,
    section_id: row.section_id,
    direction: row.direction,
    file_name: row.file_name,
    content_type: row.content_type || contentTypeOf(row.file_name),
    byte_size: row.byte_size ?? null,
    sha256: row.sha256 ?? null,
    storage_path: row.storage_path,
    save_mode: row.save_mode,
    meta: row.meta || {},
  });
  if (error) return { ok: false, source: "db", error: error.message };
  return { ok: true, source: "db" };
}

export { contentTypeOf, repoRoot };
