/**
 * Storage round-trip smoke (service role). No secrets printed.
 * node Scripts/21_storage_roundtrip_smoke.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..");
const require = createRequire(path.join(ROOT, "web", "package.json"));
const { createClient } = require("@supabase/supabase-js");

function loadEnv() {
  const p = path.join(ROOT, "web", ".env.local");
  const out = {};
  for (const line of fs.readFileSync(p, "utf8").split(/\r?\n/)) {
    const t = line.trim();
    if (!t || t.startsWith("#") || !t.includes("=")) continue;
    const i = t.indexOf("=");
    let v = t.slice(i + 1).trim();
    if (
      (v.startsWith('"') && v.endsWith('"')) ||
      (v.startsWith("'") && v.endsWith("'"))
    )
      v = v.slice(1, -1);
    out[t.slice(0, i).trim()] = v;
  }
  return out;
}

const env = loadEnv();
const url = env.NEXT_PUBLIC_SUPABASE_URL;
const key = env.SUPABASE_SERVICE_ROLE_KEY;
const schema = env.NEXT_PUBLIC_SUPABASE_SCHEMA || "autoexport";
const sb = createClient(url, key, {
  auth: { persistSession: false },
  db: { schema },
});

const body = Buffer.from(`autoexport-smoke ${new Date().toISOString()}\n`, "utf8");
const sha = createHash("sha256").update(body).digest("hex");
const objectPath = `jobs/smoke-health/${Date.now()}_ping.txt`;

const up = await sb.storage.from("job-uploads").upload(objectPath, body, {
  contentType: "text/plain",
  upsert: true,
});
if (up.error) {
  console.log(JSON.stringify({ ok: false, stage: "upload", error: up.error.message }, null, 2));
  process.exit(1);
}

const signed = await sb.storage.from("job-uploads").createSignedUrl(objectPath, 120);
const dl = await sb.storage.from("job-uploads").download(objectPath);
let dl_ok = false;
let dl_sha = null;
if (!dl.error && dl.data) {
  const ab = Buffer.from(await dl.data.arrayBuffer());
  dl_sha = createHash("sha256").update(ab).digest("hex");
  dl_ok = dl_sha === sha;
}

await sb.storage.from("job-uploads").remove([objectPath]);

console.log(
  JSON.stringify(
    {
      ok: dl_ok && !signed.error,
      upload: "ok",
      signed_url: Boolean(signed.data?.signedUrl),
      download_sha_match: dl_ok,
      object_path: objectPath,
      cleaned: true,
    },
    null,
    2,
  ),
);
process.exit(dl_ok && !signed.error ? 0 : 1);
