/**
 * DEMO E2E: create job → upload → waves → gate → archive
 * Usage: node Scripts/23_demo_ticket_e2e.mjs
 * Marks job in Scripts/demo_jobs_registry.json for later delete/keep.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(path.join(ROOT, "web", "package.json"));
const BASE = process.env.DEMO_BASE_URL || "http://127.0.0.1:3000";

function loadEnv() {
  const out = {};
  const p = path.join(ROOT, "web", ".env.local");
  if (!fs.existsSync(p)) return out;
  for (const line of fs.readFileSync(p, "utf8").split(/\r?\n/)) {
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

async function jfetch(url, opts = {}) {
  const res = await fetch(url, opts);
  const text = await res.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    data = { raw: text.slice(0, 500) };
  }
  return { status: res.status, ok: res.ok, data };
}

function tinyPng() {
  // 1x1 PNG
  return Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
    "base64",
  );
}

async function upload(jobId, section, fileName, body, contentType) {
  const fd = new FormData();
  fd.append("section", section);
  fd.append("file", new Blob([body], { type: contentType }), fileName);
  return jfetch(`${BASE}/api/jobs/${jobId}/upload`, { method: "POST", body: fd });
}

async function main() {
  const log = [];
  const push = (step, info) => {
    log.push({ step, ...info, at: new Date().toISOString() });
    console.log(JSON.stringify({ step, ...info }));
  };

  const ping = await jfetch(`${BASE}/api/jobs`);
  if (!ping.ok) {
    push("abort", { error: `dev server not reachable at ${BASE}`, status: ping.status });
    process.exit(1);
  }

  const lines = [
    {
      size: "60X102inch",
      color: "米白",
      qty_strips: 120,
      qty_cartons: 20,
      strips_per_pack: 6,
      packs_per_carton: 1,
      strips_per_carton: 6,
      fnsku: "X004W20FM1",
      gram_weight: "90G",
      product_name_zh: "单面磨毛纤维桌布",
    },
  ];

  const created = await jfetch(`${BASE}/api/jobs`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      entity_code: "C04",
      ship_date: "2026-07-31",
      order_date: "2026-07-29",
      total_strips: 120,
      lines,
    }),
  });
  if (!created.ok || !created.data.job?.id) {
    push("create_job", { ok: false, data: created.data });
    process.exit(1);
  }
  const job = created.data.job;
  const jobId = job.id;
  push("create_job", {
    ok: true,
    job_id: jobId,
    order_code: job.meta?.order_code,
    outbound_short: job.meta?.outbound_short,
    project_code: job.project_code,
    source: created.data.source,
  });

  const planJson = Buffer.from(
    JSON.stringify(
      {
        demo: true,
        demo_tag: "DEMO-TICKET",
        note: "AutoExport flow demo — delete or keep as case after review",
        entity_code: "C04",
        ship_date: "2026-07-31",
        lines,
      },
      null,
      2,
    ),
    "utf8",
  );
  const upPlan = await upload(
    jobId,
    "ship_plan",
    "DEMO_ship_plan.json",
    planJson,
    "application/json",
  );
  push("upload_plan", {
    ok: upPlan.ok,
    mode: upPlan.data.mode,
    backend: upPlan.data.storage_backend,
    path: upPlan.data.storage_path,
  });

  const upCarton = await upload(
    jobId,
    "carton_and_tracking",
    "DEMO_carton.png",
    tinyPng(),
    "image/png",
  );
  push("upload_carton", {
    ok: upCarton.ok,
    mode: upCarton.data.mode,
    backend: upCarton.data.storage_backend,
  });

  const confirm = await jfetch(`${BASE}/api/jobs/${jobId}/recognize`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      confirm: true,
      rows: [
        {
          warehouse_code: "AVP1",
          fba_shipment_id: "FBA15DEMO0001",
          reference_id: "DEMO-REF-1",
          tracking_id: "TBA000DEMO1",
          carton_count: 20,
          source_filename: "DEMO_carton.png",
          recognize_notes: "demo injected",
        },
      ],
    }),
  });
  push("confirm_recognition", { ok: confirm.ok, confirmed: confirm.data.confirmed });

  const wave1 = await jfetch(`${BASE}/api/jobs/${jobId}/run`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ wave: "after_plan" }),
  });
  push("wave_after_plan", {
    ok: wave1.ok,
    status: wave1.status,
    results: wave1.data.results,
    issues: wave1.data.issues,
    error: wave1.data.error,
  });

  const wave2 = await jfetch(`${BASE}/api/jobs/${jobId}/run`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ wave: "trio_after_carton" }),
  });
  push("wave_trio", {
    ok: wave2.ok,
    status: wave2.status,
    results: wave2.data.results,
    issues: wave2.data.issues,
    error: wave2.data.error,
  });

  // inbound stub for pack wave
  const upIn = await upload(
    jobId,
    "freight_inbound",
    "DEMO_inbound.pdf",
    Buffer.from("%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"),
    "application/pdf",
  );
  push("upload_inbound", { ok: upIn.ok, mode: upIn.data.mode });

  const wave3 = await jfetch(`${BASE}/api/jobs/${jobId}/run`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ wave: "after_inbound", confirm_gate: true }),
  });
  push("wave_after_inbound", {
    ok: wave3.ok,
    status: wave3.status,
    results: wave3.data.results,
    issues: wave3.data.issues,
    error: wave3.data.error,
  });

  const gate = await jfetch(`${BASE}/api/jobs/${jobId}/gate`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ confirm: true, checks_ok: true }),
  });
  push("gate_confirm", { ok: gate.ok, status: gate.status, data_keys: Object.keys(gate.data || {}) });

  // ensure gate_final confirmed then archive
  const arch = await jfetch(`${BASE}/api/jobs/${jobId}/run`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ step: "archive", confirm_gate: true }),
  });
  push("archive", {
    ok: arch.ok,
    status: arch.status,
    results: arch.data.results,
    error: arch.data.error,
  });

  const detail = await jfetch(`${BASE}/api/jobs/${jobId}`);
  const meta = detail.data?.job?.meta || detail.data?.meta || {};
  push("final_snapshot", {
    ok: detail.ok,
    gate_final: detail.data?.job?.gate_final || detail.data?.gate_final,
    artifacts: meta.artifacts,
    storage_sections: Object.keys(meta.storage_files || {}),
  });

  const registryPath = path.join(ROOT, "Scripts", "demo_jobs_registry.json");
  let reg = { entries: [] };
  if (fs.existsSync(registryPath)) {
    reg = JSON.parse(fs.readFileSync(registryPath, "utf8"));
  }
  reg.entries = reg.entries || [];
  reg.entries.push({
    job_id: jobId,
    order_code: job.meta?.order_code,
    project_code: job.project_code,
    created_at: new Date().toISOString(),
    tag: "DEMO-TICKET",
    disposition: "pending_user_keep_or_delete",
    log_file: "2_Processed_AI/drafts/DEMO_e2e_last.json",
  });
  reg.updated_at = new Date().toISOString();
  fs.writeFileSync(registryPath, JSON.stringify(reg, null, 2) + "\n", "utf8");

  const outPath = path.join(ROOT, "2_Processed_AI", "drafts", "DEMO_e2e_last.json");
  fs.writeFileSync(outPath, JSON.stringify({ base: BASE, log }, null, 2) + "\n", "utf8");
  push("done", { registry: registryPath, log: outPath });

  const failed = log.filter(
    (x) =>
      x.ok === false ||
      (typeof x.status === "number" && x.status >= 400 && x.step !== "gate_confirm"),
  );
  process.exit(failed.length ? 2 : 0);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
