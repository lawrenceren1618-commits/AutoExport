import { createClient } from "@supabase/supabase-js";
import fs from "fs";
import path from "path";
import {
  allocateJobCodes,
  type PlanLine,
} from "./numbering";
import type { JobMeta, JobPhase } from "./stages";
import { getRepoRoot } from "./python-runner";

const SCHEMA = process.env.NEXT_PUBLIC_SUPABASE_SCHEMA || "autoexport";

// Schema name is env-driven (autoexport); loosen generic vs default "public"
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function adminSupabase(): any | null {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) return null;
  return createClient(url, key, {
    db: { schema: SCHEMA },
    auth: { persistSession: false, autoRefreshToken: false },
  });
}

export type JobRow = {
  id: string;
  project_code: string;
  entity_code: "C04" | "C07";
  ship_date: string | null;
  status: string;
  gate_final: "WAIT" | "CONFIRMED" | "REJECTED";
  meta: JobMeta;
  created_at: string;
  updated_at?: string;
};

/** In-memory + local file fallback when Supabase unavailable / insert fails */
const memJobs: JobRow[] = [];
let memHydrated = false;

function localStorePath(): string {
  return path.join(
    getRepoRoot(),
    "2_Processed_AI",
    "cloud_job_store",
    "shipment_jobs.json",
  );
}

function hydrateMemFromDisk(): void {
  if (memHydrated) return;
  memHydrated = true;
  try {
    const p = localStorePath();
    if (!fs.existsSync(p)) return;
    const raw = JSON.parse(fs.readFileSync(p, "utf8")) as { jobs?: JobRow[] };
    const jobs = Array.isArray(raw.jobs) ? raw.jobs : [];
    memJobs.length = 0;
    for (const j of jobs) memJobs.push(j);
  } catch {
    /* keep empty */
  }
}

function persistMemToDisk(): void {
  try {
    const p = localStorePath();
    fs.mkdirSync(path.dirname(p), { recursive: true });
    fs.writeFileSync(
      p,
      JSON.stringify(
        {
          updated_at: new Date().toISOString(),
          jobs: memJobs,
        },
        null,
        2,
      ),
      "utf8",
    );
  } catch {
    /* non-fatal */
  }
}

function upsertMem(row: JobRow): void {
  hydrateMemFromDisk();
  const idx = memJobs.findIndex((j) => j.id === row.id);
  if (idx >= 0) memJobs[idx] = row;
  else memJobs.unshift(row);
  persistMemToDisk();
}

function removeMem(id: string): void {
  hydrateMemFromDisk();
  const idx = memJobs.findIndex((j) => j.id === id);
  if (idx >= 0) {
    memJobs.splice(idx, 1);
    persistMemToDisk();
  }
}

export async function listJobs(): Promise<{
  jobs: JobRow[];
  source: "db" | "memory" | "db+local";
  db_error?: string;
}> {
  hydrateMemFromDisk();
  const local = [...memJobs];
  const sb = adminSupabase();
  if (!sb) {
    return { jobs: local, source: "memory", db_error: "no_supabase_env" };
  }
  const { data, error } = await sb
    .from("shipment_jobs")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(50);
  if (error) {
    return {
      jobs: local,
      source: "memory",
      db_error: error.message,
    };
  }
  const dbJobs = (data || []) as JobRow[];
  const seen = new Set(dbJobs.map((j) => j.id));
  const merged = [...dbJobs];
  for (const j of local) {
    if (!seen.has(j.id)) merged.push(j);
  }
  merged.sort((a, b) => {
    const ta = Date.parse(a.updated_at || a.created_at || "") || 0;
    const tb = Date.parse(b.updated_at || b.created_at || "") || 0;
    return tb - ta;
  });
  return {
    jobs: merged,
    source: local.length && dbJobs.length === 0 ? "db+local" : "db",
    db_error: undefined,
  };
}

export async function createJob(input: {
  entity_code: "C04" | "C07";
  ship_date: string;
  order_date?: string;
  /** 实际交货日；缺省则存档树用 ship_date（订单交货日） */
  actual_delivery_date?: string;
  total_strips?: number;
  lines?: PlanLine[];
}): Promise<{ job: JobRow; source: "db" | "memory"; error?: string }> {
  const codes = allocateJobCodes({
    entity_code: input.entity_code,
    ship_date: input.ship_date,
    order_date: input.order_date,
    total_strips: input.total_strips || 0,
    lines: input.lines,
  });

  const orderDelivery = input.ship_date.slice(0, 10);
  const actualDelivery = (
    input.actual_delivery_date || input.ship_date
  ).slice(0, 10);

  const meta: JobMeta = {
    order_code: codes.order_code,
    order_short: codes.order_short,
    outbound_short: codes.outbound_short,
    order_delivery_date: orderDelivery,
    /** 无单独实际交货日时 = 订单交货日 */
    actual_delivery_date: actualDelivery,
    total_strips: codes.total_strips,
    lines: input.lines || [],
    phase: "await_plan" as JobPhase,
    uploads: {},
    artifacts: {},
  };
  if (input.order_date) meta.order_date = input.order_date;

  const row: JobRow = {
    id: crypto.randomUUID(),
    project_code: codes.project_code,
    entity_code: input.entity_code,
    ship_date: input.ship_date,
    status: "open",
    gate_final: "WAIT",
    meta,
    created_at: new Date().toISOString(),
  };

  const sb = adminSupabase();
  if (!sb) {
    upsertMem(row);
    return { job: row, source: "memory", error: "no_supabase_env" };
  }
  const { data, error } = await sb
    .from("shipment_jobs")
    .insert({
      project_code: row.project_code,
      entity_code: row.entity_code,
      ship_date: row.ship_date,
      status: row.status,
      gate_final: row.gate_final,
      meta: row.meta,
    })
    .select("*")
    .single();
  if (error) {
    upsertMem(row);
    return { job: row, source: "memory", error: error.message };
  }
  upsertMem(data as JobRow);
  return { job: data as JobRow, source: "db" };
}

export async function getJob(id: string): Promise<JobRow | null> {
  hydrateMemFromDisk();
  const sb = adminSupabase();
  if (!sb) return memJobs.find((j) => j.id === id) || null;
  const { data, error } = await sb
    .from("shipment_jobs")
    .select("*")
    .eq("id", id)
    .maybeSingle();
  if (error || !data) return memJobs.find((j) => j.id === id) || null;
  return data as JobRow;
}

export async function updateJobMeta(
  id: string,
  patch: Partial<JobMeta> & { gate_final?: JobRow["gate_final"]; status?: string },
): Promise<JobRow | null> {
  const current = await getJob(id);
  if (!current) return null;
  const nextMeta: JobMeta = {
    ...current.meta,
    ...patch,
    uploads: { ...(current.meta?.uploads || {}), ...(patch.uploads || {}) },
    upload_files: patch.upload_files
      ? { ...(current.meta?.upload_files || {}), ...patch.upload_files }
      : current.meta?.upload_files,
    artifacts: { ...(current.meta?.artifacts || {}), ...(patch.artifacts || {}) },
    storage_files: patch.storage_files
      ? { ...(current.meta?.storage_files || {}), ...patch.storage_files }
      : current.meta?.storage_files,
    extracts: { ...(current.meta?.extracts || {}), ...(patch.extracts || {}) },
  };
  const gate_final = patch.gate_final ?? current.gate_final;
  const status = patch.status ?? current.status;
  delete (nextMeta as { gate_final?: unknown }).gate_final;
  delete (nextMeta as { status?: unknown }).status;

  const updated: JobRow = {
    ...current,
    meta: nextMeta,
    gate_final,
    status,
    updated_at: new Date().toISOString(),
  };

  upsertMem(updated);

  const sb = adminSupabase();
  if (sb) {
    await sb
      .from("shipment_jobs")
      .update({
        meta: nextMeta,
        gate_final,
        status,
        updated_at: updated.updated_at,
      })
      .eq("id", id);
  }
  return updated;
}

export async function deleteJob(id: string): Promise<boolean> {
  removeMem(id);

  const sb = adminSupabase();
  if (sb) {
    const { error } = await sb.from("shipment_jobs").delete().eq("id", id);
    if (error) return false;
  }
  return true;
}
