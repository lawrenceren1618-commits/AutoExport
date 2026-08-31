/** List autoexport tables accessibility. node Scripts/22_list_cloud_tables.mjs */
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(path.join(ROOT, "web", "package.json"));
const { createClient } = require("@supabase/supabase-js");

function loadEnv() {
  const out = {};
  for (const line of fs.readFileSync(path.join(ROOT, "web", ".env.local"), "utf8").split(/\r?\n/)) {
    const t = line.trim();
    if (!t || t.startsWith("#") || !t.includes("=")) continue;
    const i = t.indexOf("=");
    let v = t.slice(i + 1).trim();
    if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'")))
      v = v.slice(1, -1);
    out[t.slice(0, i).trim()] = v;
  }
  return out;
}

const env = loadEnv();
const sb = createClient(env.NEXT_PUBLIC_SUPABASE_URL, env.SUPABASE_SERVICE_ROLE_KEY, {
  auth: { persistSession: false },
  db: { schema: env.NEXT_PUBLIC_SUPABASE_SCHEMA || "autoexport" },
});

const tables = [
  "shipment_jobs",
  "job_artifacts",
  "job_handshake_log",
  "settled_products",
  "settled_packing",
  "settled_fnsku",
  "settled_config",
  "fba_warehouse_headers",
  "draft_documents",
  "cross_check_logs",
  "progress_nodes",
  "master_table_imports",
  "data_source_interfaces",
  "user_io_projects",
];

const out = [];
for (const t of tables) {
  const r = await sb.from(t).select("*", { count: "exact", head: true });
  out.push({ table: t, ok: !r.error, error: r.error?.message || null, count: r.count });
}
console.log(JSON.stringify(out, null, 2));
