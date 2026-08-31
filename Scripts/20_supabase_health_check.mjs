/**
 * One-shot Supabase health check — prints metadata only (no secrets).
 * Run: node Scripts/20_supabase_health_check.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..");
const require = createRequire(path.join(ROOT, "web", "package.json"));
const { createClient } = require("@supabase/supabase-js");

function loadEnv() {
  const p = path.join(ROOT, "web", ".env.local");
  const out = {};
  if (!fs.existsSync(p)) return out;
  for (const line of fs.readFileSync(p, "utf8").split(/\r?\n/)) {
    const t = line.trim();
    if (!t || t.startsWith("#") || !t.includes("=")) continue;
    const i = t.indexOf("=");
    let v = t.slice(i + 1).trim();
    if (
      (v.startsWith('"') && v.endsWith('"')) ||
      (v.startsWith("'") && v.endsWith("'"))
    ) {
      v = v.slice(1, -1);
    }
    out[t.slice(0, i).trim()] = v;
  }
  return out;
}

const env = loadEnv();
const url = env.NEXT_PUBLIC_SUPABASE_URL || env.SUPABASE_URL || "";
const key = env.SUPABASE_SERVICE_ROLE_KEY || "";
const schema = env.NEXT_PUBLIC_SUPABASE_SCHEMA || "autoexport";
const host = (url.match(/https?:\/\/([^/]+)/) || [])[1] || null;

const base = {
  url_host: host,
  url_set: Boolean(url && !String(url).includes("YOUR_")),
  service_role_len: key.length,
  service_role_looks_jwt: key.split(".").length === 3,
  schema,
};

if (!base.url_set || !base.service_role_looks_jwt || key.length < 100) {
  console.log(
    JSON.stringify(
      {
        ...base,
        verdict: "config_incomplete",
        detail:
          "NEXT_PUBLIC_SUPABASE_URL missing/placeholder, or SUPABASE_SERVICE_ROLE_KEY not a full JWT",
      },
      null,
      2,
    ),
  );
  process.exit(0);
}

const sb = createClient(url, key, {
  auth: { persistSession: false },
  db: { schema },
});

const expected = ["job-uploads", "job-outputs", "label-source", "templates"];
const buckets = await sb.storage.listBuckets();
const jobs = await sb.from("shipment_jobs").select("id").limit(1);
const arts = await sb.from("job_artifacts").select("id").limit(1);

const ids = (buckets.data || []).map((b) => b.id);
const missing = expected.filter((b) => !ids.includes(b));

let uploadProbe = null;
if (!buckets.error && ids.includes("job-uploads")) {
  const probePath = `healthcheck/${Date.now()}.txt`;
  const up = await sb.storage
    .from("job-uploads")
    .upload(probePath, Buffer.from("ok"), { contentType: "text/plain", upsert: true });
  if (!up.error) {
    await sb.storage.from("job-uploads").remove([probePath]);
    uploadProbe = "ok";
  } else {
    uploadProbe = up.error.message;
  }
}

const verdict =
  !buckets.error &&
  !jobs.error &&
  missing.length === 0 &&
  uploadProbe === "ok"
    ? "supabase_ready"
    : !buckets.error && !jobs.error
      ? "supabase_partial"
      : "supabase_fail";

console.log(
  JSON.stringify(
    {
      ...base,
      storage_list_ok: !buckets.error,
      storage_error: buckets.error?.message || null,
      bucket_ids: ids,
      expected_buckets: expected,
      missing_buckets: missing,
      upload_probe: uploadProbe,
      jobs_select_ok: !jobs.error,
      jobs_error: jobs.error?.message || null,
      artifacts_select_ok: !arts.error,
      artifacts_error: arts.error?.message || null,
      verdict,
    },
    null,
    2,
  ),
);
