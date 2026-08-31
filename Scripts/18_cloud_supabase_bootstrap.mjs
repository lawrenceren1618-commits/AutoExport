/**
 * 18_cloud_supabase_bootstrap.mjs
 * 云端专用引导：migration 检查 / Storage 桶 / 元数据单向推送。
 * 硬约束：只写 Supabase；绝不写本机 settled / interfaces / Shipments。
 *
 * 用法（在仓库根）:
 *   node Scripts/18_cloud_supabase_bootstrap.mjs           # dry 检查
 *   node Scripts/18_cloud_supabase_bootstrap.mjs --apply   # 建桶 + 推元数据
 *
 * DDL：若表不存在，打印须在 Dashboard SQL Editor 执行的 migration 路径（本脚本不回写本地）。
 */
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..");
const require = createRequire(path.join(ROOT, "web", "package.json"));
const { createClient } = require("@supabase/supabase-js");
const APPLY = process.argv.includes("--apply");
const APPLY_DDL = process.argv.includes("--apply-ddl");

function loadEnvLocal() {
  const p = path.join(ROOT, "web", ".env.local");
  const out = {};
  if (!fs.existsSync(p)) return out;
  for (const line of fs.readFileSync(p, "utf8").split(/\r?\n/)) {
    const t = line.trim();
    if (!t || t.startsWith("#") || !t.includes("=")) continue;
    const i = t.indexOf("=");
    const k = t.slice(0, i).trim();
    let v = t.slice(i + 1).trim();
    if (
      (v.startsWith('"') && v.endsWith('"')) ||
      (v.startsWith("'") && v.endsWith("'"))
    ) {
      v = v.slice(1, -1);
    }
    out[k] = v;
  }
  return out;
}

function dbUrlFromEnv(env) {
  return (
    env.DATABASE_URL ||
    env.SUPABASE_DB_URL ||
    env.POSTGRES_URL ||
    env.DIRECT_URL ||
    env.SUPABASE_POSTGRES_URL ||
    ""
  );
}

async function applyDdlWithPg(dbUrl) {
  let Client;
  try {
    ({ Client } = require("pg"));
  } catch {
    console.error("FAIL: pg not found under web/node_modules; npm install pg in web/");
    return false;
  }
  const client = new Client({
    connectionString: dbUrl,
    ssl: { rejectUnauthorized: false },
  });
  await client.connect();
  console.log("pg connected (cloud DDL; local disk untouched)");
  for (const rel of MIGRATIONS) {
    const sql = fs.readFileSync(path.join(ROOT, rel), "utf8");
    console.log("DDL run", rel);
    await client.query(sql);
  }
  // Help PostgREST see schema grants (Exposed schemas still need Dashboard toggle)
  await client.query(`
    grant usage on schema autoexport to anon, authenticated, service_role;
    grant select on all tables in schema autoexport to anon, authenticated;
    grant all on all tables in schema autoexport to service_role;
    grant all on all sequences in schema autoexport to service_role;
    alter default privileges in schema autoexport grant select on tables to anon, authenticated;
    alter default privileges in schema autoexport grant all on tables to service_role;
  `);
  await client.end();
  console.log("DDL finished all migrations");
  return true;
}


function readJson(rel) {
  return JSON.parse(fs.readFileSync(path.join(ROOT, rel), "utf8"));
}

const BUCKETS = [
  { id: "job-uploads", public: false },
  { id: "job-outputs", public: false },
  { id: "label-source", public: false },
  { id: "templates", public: false },
];

const MIGRATIONS = [
  "supabase/migrations/20260720000000_init_ofce.sql",
  "supabase/migrations/20260722000000_fba_warehouse_headers.sql",
  "supabase/migrations/20260722010000_schema_autoexport.sql",
  "supabase/migrations/20260726000000_channel_ab_interfaces.sql",
  "supabase/migrations/20260726010000_shipment_jobs_cloud.sql",
];

async function main() {
  console.log("=== AutoExport cloud bootstrap (local files READ-ONLY) ===");
  console.log("isolation: Templates/Cloud_Local_Isolation.md");
  console.log("apply=", APPLY);

  const env = loadEnvLocal();
  const url = env.SUPABASE_URL || env.NEXT_PUBLIC_SUPABASE_URL;
  const key = env.SUPABASE_SERVICE_ROLE_KEY;
  const dbUrl = dbUrlFromEnv(env);
  console.log("env.url_set=", Boolean(url && !String(url).includes("YOUR_PROJECT")));
  console.log("env.service_role_set=", Boolean(key && key.length > 20));
  console.log("env.db_url_set=", Boolean(dbUrl));

  if (!url || !key) {
    console.error("FAIL: missing URL or SERVICE_ROLE in web/.env.local");
    process.exit(2);
  }

  if (APPLY_DDL) {
    if (!dbUrl) {
      console.error(
        "FAIL: --apply-ddl needs DATABASE_URL (or SUPABASE_DB_URL/POSTGRES_URL/DIRECT_URL) in web/.env.local",
      );
      console.error(
        "Get it from Supabase → Project Settings → Database → Connection string (URI).",
      );
      process.exit(2);
    }
    const ok = await applyDdlWithPg(dbUrl);
    if (!ok) process.exit(2);
  }

  const sb = createClient(url, key, {
    db: { schema: "autoexport" },
    auth: { persistSession: false, autoRefreshToken: false },
  });

  // Probe tables (cloud only)
  const probes = [
    "shipment_jobs",
    "job_artifacts",
    "data_source_interfaces",
    "settled_config",
    "user_io_projects",
  ];
  const missing = [];
  for (const t of probes) {
    const { error } = await sb.from(t).select("*").limit(1);
    if (error) {
      missing.push(`${t}: ${error.message}`);
      console.log("probe FAIL", t, error.code || "", error.message);
    } else {
      console.log("probe OK", t);
    }
  }

  if (missing.length) {
    console.log("---");
    console.log("DDL required in Supabase Dashboard → SQL Editor (run in order):");
    for (const m of MIGRATIONS) console.log(" ", m);
    console.log(
      "Also: Settings → API → Exposed schemas → add autoexport",
    );
    if (!APPLY) {
      console.log("Re-run with --apply after DDL to create buckets + push metadata.");
      process.exit(1);
    }
    console.log("WARN: --apply continuing for buckets/metadata; table upserts may fail until DDL done.");
  }

  // Storage buckets (cloud only)
  if (APPLY) {
    for (const b of BUCKETS) {
      const { data: existing, error: listErr } = await sb.storage.listBuckets();
      if (listErr) {
        console.log("storage list FAIL", listErr.message);
        break;
      }
      const found = (existing || []).some((x) => x.name === b.id || x.id === b.id);
      if (found) {
        console.log("bucket OK exists", b.id);
        continue;
      }
      const { error } = await sb.storage.createBucket(b.id, {
        public: b.public,
      });
      if (error) console.log("bucket FAIL", b.id, error.message);
      else console.log("bucket CREATED", b.id);
    }
  } else {
    console.log("dry-run: skip bucket create");
  }

  // One-way metadata push (cloud only; never write local)
  if (APPLY && missing.length === 0) {
    const interfaces = readJson("Scripts/data_source_interfaces.json");
    const settled = readJson("Scripts/settled_knowledge_db.json");
    let ifaceN = 0;
    for (const item of interfaces.interfaces || []) {
      const row = {
        id: item.id,
        task: item.task || null,
        needs: item.needs || null,
        channel: item.channel || null,
        module: item.module || null,
        obtain: item.obtain || {},
        cloud: item.cloud || { status: "pending_cloud" },
      };
      const { error } = await sb.from("data_source_interfaces").upsert(row);
      if (error) console.log("upsert iface FAIL", item.id, error.message);
      else ifaceN++;
    }
    let cfgN = 0;
    for (const [k, v] of Object.entries(settled.confirmed_defaults || {})) {
      const payload = {
        key: `confirmed_defaults.${k}`,
        value: typeof v === "object" && v !== null ? v : { _: v },
        confirmed_at:
          typeof v === "object" && v && v.confirmed_at ? v.confirmed_at : null,
        source_file: "Scripts/settled_knowledge_db.json",
      };
      const { error } = await sb.from("settled_config").upsert(payload);
      if (error) console.log("upsert cfg FAIL", k, error.message);
      else cfgN++;
    }
    for (const [code, ent] of Object.entries(settled.entities || {})) {
      const { error } = await sb.from("settled_config").upsert({
        key: `entities.${code}`,
        value: ent,
        source_file: "Scripts/settled_knowledge_db.json",
      });
      if (error) console.log("upsert entity FAIL", code, error.message);
      else cfgN++;
    }
    // cloud-only isolation marker row
    await sb.from("settled_config").upsert({
      key: "cloud_runtime.isolation",
      value: {
        local_authority: true,
        cloud_does_not_write_local: true,
        doc: "Templates/Cloud_Local_Isolation.md",
        synced_at: new Date().toISOString(),
      },
      source_file: "cloud_bootstrap_only",
    });
    console.log("metadata push OK iface=", ifaceN, "cfg≈", cfgN);
  } else if (APPLY) {
    console.log("skip metadata push until probes OK");
  }

  console.log("=== done; local settled/interfaces/Shipments untouched ===");
  process.exit(missing.length && !APPLY ? 1 : 0);
}

main().catch((e) => {
  console.error("FATAL", e?.message || e);
  process.exit(1);
});
