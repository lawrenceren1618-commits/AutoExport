import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import {
  localBlobAbsolute,
  contentTypeOf,
  type StorageBucket,
} from "@/lib/storage/artifacts";

/**
 * Dev/local fallback download for objects stored under 2_Processed_AI/cloud_job_blobs.
 * Not for production public exposure without auth — office local runner only.
 */
export async function GET(req: Request) {
  if (process.env.VERCEL) {
    return NextResponse.json(
      { ok: false, error: "local-blob disabled on Vercel" },
      { status: 403 },
    );
  }

  const url = new URL(req.url);
  const bucket = url.searchParams.get("bucket") as StorageBucket | null;
  const objectPath = url.searchParams.get("path") || "";
  if (!bucket || !["job-uploads", "job-outputs"].includes(bucket) || !objectPath) {
    return NextResponse.json({ ok: false, error: "bucket+path required" }, { status: 400 });
  }
  if (objectPath.includes("..") || path.isAbsolute(objectPath)) {
    return NextResponse.json({ ok: false, error: "invalid path" }, { status: 400 });
  }

  const abs = localBlobAbsolute(bucket, objectPath);
  if (!fs.existsSync(abs)) {
    return NextResponse.json({ ok: false, error: "not found" }, { status: 404 });
  }

  const body = fs.readFileSync(abs);
  const fileName = path.basename(objectPath);
  const ascii = fileName.replace(/[^\x20-\x7E]/g, "_");
  const star = encodeURIComponent(fileName);
  return new NextResponse(body, {
    status: 200,
    headers: {
      "content-type": contentTypeOf(fileName),
      "content-disposition": `attachment; filename="${ascii}"; filename*=UTF-8''${star}`,
      "cache-control": "private, max-age=60",
    },
  });
}
