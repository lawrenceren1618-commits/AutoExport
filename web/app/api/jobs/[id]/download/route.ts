import { NextResponse } from "next/server";
import { getJob } from "@/lib/pipeline/jobs";
import { getMeta } from "@/lib/pipeline/stages";
import {
  bucketForDirection,
  createSignedDownloadUrl,
} from "@/lib/storage/artifacts";
import { pickPrimaryStoredFile } from "@/lib/storage/pick-primary-file";
import type { SectionDirection } from "@/lib/pipeline/schema";
import { ARCHIVE_SECTION, INPUT_SECTIONS, OUTPUT_SECTIONS } from "@/lib/pipeline/schema";

type Ctx = { params: Promise<{ id: string }> };

function directionOf(sectionId: string): SectionDirection {
  if (INPUT_SECTIONS.some((s) => s.id === sectionId)) return "in";
  if (sectionId === ARCHIVE_SECTION.id) return "archive";
  return "out";
}

/**
 * GET ?section=order_xlsx&file=optionalName
 * Returns signed URL (Supabase) or local-blob proxy URL.
 */
export async function GET(req: Request, ctx: Ctx) {
  const { id } = await ctx.params;
  const job = await getJob(id);
  if (!job) {
    return NextResponse.json({ ok: false, error: "job not found" }, { status: 404 });
  }

  const url = new URL(req.url);
  const section = url.searchParams.get("section") || "";
  const fileName = url.searchParams.get("file") || "";

  const known =
    INPUT_SECTIONS.some((s) => s.id === section) ||
    OUTPUT_SECTIONS.some((s) => s.id === section) ||
    section === ARCHIVE_SECTION.id;
  if (!known) {
    return NextResponse.json(
      {
        ok: false,
        error: "invalid section",
        allowed: [
          ...INPUT_SECTIONS.map((s) => s.id),
          ...OUTPUT_SECTIONS.map((s) => s.id),
          ARCHIVE_SECTION.id,
        ],
      },
      { status: 400 },
    );
  }

  const meta = getMeta(job);
  const files = meta.storage_files?.[section] || [];
  if (!files.length) {
    return NextResponse.json(
      { ok: false, error: "no stored files for section", section },
      { status: 404 },
    );
  }

  const primary = pickPrimaryStoredFile(section, files);
  const hit = fileName
    ? files.find((f) => f.name === fileName) || primary || files[files.length - 1]
    : primary || files[files.length - 1];

  const dir = directionOf(section);
  const signed = await createSignedDownloadUrl(
    bucketForDirection(dir),
    hit.storage_path,
    3600,
    hit.backend,
  );

  if (!signed.ok) {
    return NextResponse.json(
      { ok: false, error: signed.error || "sign failed", storage_path: hit.storage_path },
      { status: 404 },
    );
  }

  return NextResponse.json({
    ok: true,
    job_id: id,
    section,
    file_name: hit.name,
    storage_path: hit.storage_path,
    backend: signed.backend,
    url: signed.url,
    local_path: signed.local_path,
    expires_hint_sec: signed.backend === "supabase" ? 3600 : null,
  });
}
