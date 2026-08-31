import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import { getJob, updateJobMeta } from "@/lib/pipeline/jobs";
import { getMeta } from "@/lib/pipeline/stages";
import {
  localBlobAbsolute,
  pushLocalObjectToSupabase,
  pullSupabaseObjectToLocal,
  type StorageBucket,
} from "@/lib/storage/artifacts";
import { getEffectivePlane, planeLabel } from "@/lib/runtime/execution-plane";
import { getRepoRoot } from "@/lib/pipeline/python-runner";
import { ARCHIVE_SECTION, INPUT_SECTIONS, OUTPUT_SECTIONS } from "@/lib/pipeline/schema";

type Ctx = { params: Promise<{ id: string }> };

type StoredFile = {
  name: string;
  storage_path: string;
  backend: string;
  sha256: string;
  byte_size: number;
};

function allSections(): string[] {
  return [
    ...INPUT_SECTIONS.map((s) => s.id),
    ...OUTPUT_SECTIONS.map((s) => s.id),
    ARCHIVE_SECTION.id,
  ];
}

function bucketForSection(sectionId: string): StorageBucket {
  if (INPUT_SECTIONS.some((s) => s.id === sectionId)) return "job-uploads";
  return "job-outputs";
}

function collectFiles(
  storage: Record<string, StoredFile[]> | undefined,
): { section: string; file: StoredFile }[] {
  const out: { section: string; file: StoredFile }[] = [];
  for (const sec of allSections()) {
    for (const f of storage?.[sec] || []) {
      out.push({ section: sec, file: f });
    }
  }
  return out;
}

function settleCandidatesFromMeta(meta: ReturnType<typeof getMeta>) {
  const lines = (meta.lines || []) as Record<string, unknown>[];
  return lines
    .filter((ln) => ln && (ln.fnsku || ln.strips_per_pack))
    .map((ln) => ({
      entity_hint: meta.order_code,
      size: ln.size,
      color: ln.color,
      strips_per_pack: ln.strips_per_pack,
      packs_per_carton: ln.packs_per_carton,
      strips_per_carton: ln.strips_per_carton,
      gram_weight: ln.gram_weight,
      fnsku: ln.fnsku,
      amazon_sku: ln.amazon_sku,
      note: "待 H01 确认后入库；sync 仅排队",
    }));
}

function mirrorPulledToShipments(
  project: string,
  orderCode: string | undefined,
  section: string,
  absLocal: string,
  fileName: string,
): string | null {
  if (!project) return null;
  const root = path.join(getRepoRoot(), "1_Input_Raw", "Shipments", project);
  try {
    if (section === "order_xlsx") {
      const destDir = path.join(root, "订单表");
      fs.mkdirSync(destDir, { recursive: true });
      const dest = path.join(destDir, fileName);
      fs.copyFileSync(absLocal, dest);
      return dest;
    }
    if (section === "product_label_pack" && orderCode && /\.pdf$/i.test(fileName)) {
      // Flat blob name: {EF}标签__10条装__60x102__102白-10条.pdf
      const m = fileName.match(
        new RegExp(
          `^${orderCode.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}标签__(.+?)__(.+?)__(.+)$`,
        ),
      );
      if (m) {
        const dest = path.join(root, "产品标签", `${orderCode}标签`, m[1], m[2], m[3]);
        fs.mkdirSync(path.dirname(dest), { recursive: true });
        fs.copyFileSync(absLocal, dest);
        return dest;
      }
      const destDir = path.join(root, "产品标签", `${orderCode}标签`);
      fs.mkdirSync(destDir, { recursive: true });
      const dest = path.join(destDir, fileName);
      fs.copyFileSync(absLocal, dest);
      return dest;
    }
  } catch {
    return null;
  }
  return null;
}

/**
 * POST { action: "status" | "push" | "pull" }
 */
export async function POST(req: Request, ctx: Ctx) {
  const { id } = await ctx.params;
  const job = await getJob(id);
  if (!job) {
    return NextResponse.json({ ok: false, error: "job not found" }, { status: 404 });
  }

  const body = (await req.json().catch(() => ({}))) as { action?: string };
  const action = (body.action || "status").toLowerCase();
  const plane = getEffectivePlane(req);
  const meta = getMeta(job);
  const files = collectFiles(meta.storage_files as Record<string, StoredFile[]> | undefined);

  if (action === "status") {
    const byBackend = { local: 0, supabase: 0, other: 0 };
    for (const { file } of files) {
      if (file.backend === "local") byBackend.local += 1;
      else if (file.backend === "supabase") byBackend.supabase += 1;
      else byBackend.other += 1;
    }
    return NextResponse.json({
      ok: true,
      job_id: id,
      plane,
      plane_label: planeLabel(plane),
      file_count: files.length,
      by_backend: byBackend,
      sync: meta.sync || {},
      settle_candidates_count: (meta.settle_candidates || []).length,
      needs_push: plane === "local" && byBackend.local > 0,
      needs_pull: byBackend.supabase > 0 && plane === "local",
      cloud_ready: Boolean(meta.sync?.cloud_ready),
    });
  }

  if (action === "push") {
    if (plane === "cloud") {
      return NextResponse.json(
        {
          ok: false,
          error: "push_only_on_local_plane",
          hint: "云端面请在本机打开后拉取/或本机生成后再上传",
        },
        { status: 400 },
      );
    }
    const results: { name: string; ok: boolean; error?: string }[] = [];
    const updatedFiles: Record<string, StoredFile[]> = {
      ...((meta.storage_files as Record<string, StoredFile[]>) || {}),
    };

    for (const { section, file } of files) {
      if (file.backend !== "local") {
        results.push({ name: file.name, ok: true, error: "skip_non_local" });
        continue;
      }
      const bucket = bucketForSection(section);
      const up = await pushLocalObjectToSupabase({
        bucket,
        storagePath: file.storage_path,
      });
      results.push({
        name: file.name,
        ok: up.ok,
        error: up.error,
      });
      if (up.ok) {
        const list = [...(updatedFiles[section] || [])];
        const idx = list.findIndex(
          (x) => x.storage_path === file.storage_path && x.sha256 === file.sha256,
        );
        const next: StoredFile = {
          ...file,
          backend: "supabase",
          sha256: up.sha256 || file.sha256,
          byte_size: up.byte_size || file.byte_size,
        };
        // Keep local entry and append cloud copy record (same path, dual availability after push)
        if (idx >= 0) {
          list[idx] = { ...file, backend: "local" };
        }
        list.push(next);
        updatedFiles[section] = list;
      }
    }

    const candidates = settleCandidatesFromMeta(meta);
    const pushed = results.filter((r) => r.ok && r.error !== "skip_non_local").length;
    const failed = results.filter((r) => !r.ok).length;
    const updated = await updateJobMeta(id, {
      storage_files: updatedFiles,
      sync: {
        ...(meta.sync || {}),
        pushed_at: new Date().toISOString(),
        cloud_ready: failed === 0 && pushed > 0,
        last_error: failed ? `${failed} file(s) failed` : undefined,
      },
      settle_candidates: candidates,
    });

    return NextResponse.json({
      ok: failed === 0,
      action: "push",
      plane,
      pushed,
      failed,
      results,
      settle_candidates: candidates,
      settle_note: "须你确认（H01）后才写入沉淀库；本次仅排队",
      job: updated,
    });
  }

  if (action === "pull") {
    if (plane !== "local") {
      return NextResponse.json(
        {
          ok: false,
          error: "pull_only_on_local_plane",
          hint: "从云端拉取须在本机执行面",
        },
        { status: 400 },
      );
    }
    const results: { name: string; ok: boolean; error?: string; ship?: string | null }[] =
      [];
    const updatedFiles: Record<string, StoredFile[]> = {
      ...((meta.storage_files as Record<string, StoredFile[]>) || {}),
    };

    // Prefer unique storage_paths that exist on supabase (or any listed)
    const seen = new Set<string>();
    for (const { section, file } of files) {
      const key = `${section}|${file.storage_path}`;
      if (seen.has(key)) continue;
      seen.add(key);

      const bucket = bucketForSection(section);
      const down = await pullSupabaseObjectToLocal({
        bucket,
        storagePath: file.storage_path,
      });
      let ship: string | null = null;
      if (down.ok) {
        const abs = localBlobAbsolute(bucket, file.storage_path);
        ship = mirrorPulledToShipments(
          job.project_code,
          meta.order_code,
          section,
          abs,
          file.name,
        );
        const list = [...(updatedFiles[section] || [])];
        const hasLocal = list.some(
          (x) => x.storage_path === file.storage_path && x.backend === "local",
        );
        if (!hasLocal) {
          list.push({
            name: file.name,
            storage_path: file.storage_path,
            backend: "local",
            sha256: down.sha256,
            byte_size: down.byte_size,
          });
          updatedFiles[section] = list;
        }
      }
      results.push({
        name: file.name,
        ok: down.ok,
        error: down.error,
        ship,
      });
    }

    const pulled = results.filter((r) => r.ok).length;
    const failed = results.filter((r) => !r.ok).length;
    const updated = await updateJobMeta(id, {
      storage_files: updatedFiles,
      sync: {
        ...(meta.sync || {}),
        pulled_at: new Date().toISOString(),
        last_error: failed ? `${failed} file(s) failed` : undefined,
      },
    });

    return NextResponse.json({
      ok: failed === 0,
      action: "pull",
      plane,
      pulled,
      failed,
      results,
      job: updated,
    });
  }

  return NextResponse.json(
    { ok: false, error: "invalid action", allowed: ["status", "push", "pull"] },
    { status: 400 },
  );
}
