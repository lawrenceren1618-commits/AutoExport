/**
 * 发货存档索引（仅索引视图，不建 YYYY/MM/DD 物理夹）
 * 权威：Templates/Ship_Stats_Correspondence.md · Templates/Shipment_Archive_Index.md
 * UI：/ops/archives
 */

import fs from "fs";
import path from "path";
import type { JobRow } from "./jobs";
import { getMeta, type JobMeta } from "./stages";
import type { PlanLine } from "./numbering";
import { orderShortFromCode } from "./archive-display";

export type ArchiveSpecLine = {
  size?: string;
  color?: string;
  strips_per_pack?: number;
  gram_weight?: number;
  carton_count: number;
  fnsku?: string;
  label?: string;
};

export type ArchiveCostPendingLine = {
  label: string;
  unit_price: number | null;
  carton_count?: number | null;
};

export type ArchiveCostState = {
  status: "none" | "awaiting_confirm" | "confirmed";
  /** 云端仅汇总 */
  batch_total_cost?: number | null;
  screenshot?: {
    name: string;
    storage_path: string;
    backend: string;
    at: string;
  };
  pending?: {
    ocr_text_preview?: string;
    proposed_lines: ArchiveCostPendingLine[];
    proposed_batch_total: number | null;
    dual_compare?: {
      verdict: string;
      overlap_ratio: number;
      note: string;
      secondary_preview?: string;
      primary_only_tokens?: string[];
      secondary_only_tokens?: string[];
    };
  };
  confirmed_at?: string;
};

/** YYYY-MM-DD；非法则 null */
export function normalizeYmd(raw: string | null | undefined): string | null {
  if (!raw) return null;
  const s = String(raw).trim().slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) return null;
  return s;
}

/**
 * 存档树日期（A1）：
 * 1) 实际交货日 actual_delivery_date（最高优先）
 * 2) 若无实际交货日 → 与订单交货日相同（order_delivery_date / job.ship_date）
 * 禁止用 created_at / 做任务时间。
 */
export function resolveArchiveShipDate(job: JobRow): string | null {
  const meta = getMeta(job);
  const orderDelivery =
    normalizeYmd(meta.order_delivery_date) || normalizeYmd(job.ship_date);
  const actual = normalizeYmd(meta.actual_delivery_date) || orderDelivery;
  return actual;
}

export type ArchiveEntry = {
  id: string;
  ship_date: string; // YYYY-MM-DD — 经 resolveArchiveShipDate
  order_code: string;
  /** 展示用短码（一屏） */
  order_short?: string;
  project_code: string;
  entity_code: "C04" | "C07";
  batch_label: string;
  carton_count: number | null;
  total_strips?: number | null;
  /** 规格明细（详细项） */
  spec_details?: ArchiveSpecLine[];
  freight_forwarder_name?: string;
  fba_shipment_ids?: string[];
  cost?: ArchiveCostState;
  job_id?: string;
  archived_at: string;
  source: "job_archive" | "manual";
};

export type ArchiveYearNode = {
  year: string;
  months: ArchiveMonthNode[];
  ticket_count: number;
  carton_sum: number;
};

export type ArchiveMonthNode = {
  month: string;
  days: ArchiveDayNode[];
  ticket_count: number;
  carton_sum: number;
};

export type ArchiveDayNode = {
  day: string;
  date: string;
  entries: ArchiveEntry[];
  ticket_count: number;
  carton_sum: number;
};

type IndexFile = {
  version: string;
  confirmed_at?: string;
  doc?: string;
  rules?: Record<string, unknown>;
  entries: ArchiveEntry[];
};

function repoRoot(): string {
  const candidates = [
    path.join(process.cwd(), "Scripts"),
    path.join(process.cwd(), "..", "Scripts"),
  ];
  for (const c of candidates) {
    if (fs.existsSync(path.join(c, "shipment_archive_index.json"))) {
      return path.dirname(c);
    }
    if (fs.existsSync(path.join(c, "order_code_seq.json"))) {
      return path.dirname(c);
    }
  }
  return path.join(process.cwd(), "..");
}

function indexPath(): string {
  return path.join(repoRoot(), "Scripts", "shipment_archive_index.json");
}

export function localUnitPricesDir(): string {
  return path.join(
    repoRoot(),
    "1_Input_Raw",
    "00_Master_Reference",
    "发货统计",
    "local_unit_prices",
  );
}

export function readArchiveIndexFile(): IndexFile {
  try {
    const raw = fs.readFileSync(indexPath(), "utf8");
    const data = JSON.parse(raw) as IndexFile;
    return {
      ...data,
      entries: Array.isArray(data.entries) ? data.entries : [],
    };
  } catch {
    return {
      version: "1.1",
      confirmed_at: "2026-07-29",
      doc: "Templates/Ship_Stats_Correspondence.md",
      entries: [],
    };
  }
}

function defaultRules(): Record<string, unknown> {
  return {
    group_by: "archive_ship_date YYYY/MM/DD",
    ship_date_priority:
      "actual_delivery_date (else = order_delivery_date); never created_at",
    leaf: "ticket_summary_plus_spec_detail",
    leaf_display: "order_short · batch · carton_count",
    leaf_authority_code: "order_code EF long",
    detail_expand: "spec_details carton per size/color",
    physical_folders: "none_index_only",
    ui_route: "/ops/archives",
    not_on_workspace_main_path: true,
    register_after: "gate_confirmed_and_archive_step",
    cost: "cloud_batch_total_only; local_unit_prices; screenshot_confirm_gate",
    doc: "Templates/Ship_Stats_Correspondence.md",
  };
}

export function writeArchiveIndexFile(data: IndexFile): boolean {
  try {
    const payload: IndexFile = {
      ...data,
      version: data.version || "1.1",
      rules: { ...defaultRules(), ...(data.rules || {}) },
    };
    fs.writeFileSync(indexPath(), JSON.stringify(payload, null, 2) + "\n", "utf8");
    return true;
  } catch {
    return false;
  }
}

export function cartonCountFromJob(job: JobRow): number | null {
  const meta = getMeta(job);
  const rows = meta.carton_recognition?.rows;
  if (rows?.length) {
    let sum = 0;
    let any = false;
    for (const r of rows) {
      if (typeof r.carton_count === "number" && Number.isFinite(r.carton_count)) {
        sum += r.carton_count;
        any = true;
      }
    }
    if (any) return sum;
  }
  const lines = (meta.lines || []) as PlanLine[];
  if (lines.length) {
    let sum = 0;
    let any = false;
    for (const line of lines) {
      if (typeof line.qty_cartons === "number" && Number.isFinite(line.qty_cartons)) {
        sum += line.qty_cartons;
        any = true;
      }
    }
    if (any) return sum;
  }
  return null;
}

export function specDetailsFromJob(job: JobRow): ArchiveSpecLine[] {
  const meta = getMeta(job);
  const lines = (meta.lines || []) as PlanLine[];
  const out: ArchiveSpecLine[] = [];
  for (const line of lines) {
    if (typeof line.qty_cartons !== "number" || !Number.isFinite(line.qty_cartons)) {
      continue;
    }
    const labelParts = [
      line.size,
      line.color,
      line.strips_per_pack != null ? `${line.strips_per_pack}条装` : null,
    ].filter(Boolean);
    out.push({
      size: line.size,
      color: line.color,
      strips_per_pack: line.strips_per_pack,
      carton_count: line.qty_cartons,
      fnsku: line.fnsku,
      label: labelParts.join(" ") || undefined,
    });
  }
  return out;
}

export function fbaIdsFromJob(job: JobRow): string[] {
  const meta = getMeta(job);
  const ids: string[] = [];
  const seen = new Set<string>();
  for (const r of meta.carton_recognition?.rows || []) {
    const id = (r.fba_shipment_id || "").trim().toUpperCase();
    if (id && !seen.has(id)) {
      seen.add(id);
      ids.push(id);
    }
  }
  return ids;
}

export function batchLabelFromMeta(meta: JobMeta): string {
  if (meta.batch?.mode === "split") return "分批";
  return "一次";
}

export function entryFromJob(job: JobRow): ArchiveEntry | null {
  const ship_date = resolveArchiveShipDate(job);
  if (!ship_date) return null;
  const meta = getMeta(job);
  if (!meta.artifacts?.audit_archive) return null;
  const order_code = meta.order_code || job.project_code;
  if (!order_code) return null;
  if (job.gate_final !== "CONFIRMED") return null;

  const prevCost = undefined; // fresh from job; merge keeps prior cost in upsert caller

  return {
    id: job.id,
    ship_date,
    order_code,
    order_short: meta.order_short || orderShortFromCode(order_code),
    project_code: job.project_code,
    entity_code: job.entity_code,
    batch_label: batchLabelFromMeta(meta),
    carton_count: cartonCountFromJob(job),
    total_strips: meta.total_strips ?? null,
    spec_details: specDetailsFromJob(job),
    freight_forwarder_name: "物易通",
    fba_shipment_ids: fbaIdsFromJob(job),
    cost: prevCost,
    job_id: job.id,
    archived_at: new Date().toISOString(),
    source: "job_archive",
  };
}

/** Gate 确认并 archive 后写入索引（同 job 覆盖；保留已确认成本） */
export function upsertArchiveEntry(entry: ArchiveEntry): {
  ok: boolean;
  persisted: boolean;
  entries: ArchiveEntry[];
} {
  const file = readArchiveIndexFile();
  const prev = file.entries.find(
    (e) => e.id === entry.id || (entry.job_id && e.job_id === entry.job_id),
  );
  const merged: ArchiveEntry = {
    ...entry,
    order_short: entry.order_short || orderShortFromCode(entry.order_code),
    cost: entry.cost?.status === "confirmed" || entry.cost?.status === "awaiting_confirm"
      ? entry.cost
      : prev?.cost?.status === "confirmed" || prev?.cost?.status === "awaiting_confirm"
        ? prev.cost
        : entry.cost || prev?.cost || { status: "none" },
  };
  const next = file.entries.filter(
    (e) => e.id !== entry.id && !(entry.job_id && e.job_id === entry.job_id),
  );
  next.push(merged);
  next.sort((a, b) => {
    const d = b.ship_date.localeCompare(a.ship_date);
    if (d !== 0) return d;
    return a.order_code.localeCompare(b.order_code);
  });
  const data: IndexFile = {
    ...file,
    confirmed_at: "2026-07-29",
    doc: "Templates/Ship_Stats_Correspondence.md",
    entries: next,
  };
  const persisted = writeArchiveIndexFile(data);
  return { ok: true, persisted, entries: next };
}

export function patchArchiveEntry(
  entryId: string,
  patch: Partial<ArchiveEntry>,
): { ok: boolean; entry?: ArchiveEntry; error?: string } {
  const file = readArchiveIndexFile();
  const idx = file.entries.findIndex((e) => e.id === entryId || e.job_id === entryId);
  if (idx < 0) return { ok: false, error: "entry_not_found" };
  const entry = { ...file.entries[idx], ...patch };
  file.entries[idx] = entry;
  const persisted = writeArchiveIndexFile(file);
  if (!persisted) return { ok: false, error: "persist_failed", entry };
  return { ok: true, entry };
}

export function writeLocalUnitPrices(opts: {
  entry_id: string;
  order_code: string;
  batch_total_cost: number;
  lines: {
    label: string;
    unit_price: number;
    carton_count?: number | null;
    size?: string;
    color?: string;
    strips_per_pack?: number;
  }[];
  screenshot_name?: string;
}): { ok: boolean; path?: string; error?: string } {
  try {
    const dir = localUnitPricesDir();
    fs.mkdirSync(dir, { recursive: true });
    const abs = path.join(dir, `${opts.entry_id}.json`);
    const payload = {
      entry_id: opts.entry_id,
      order_code: opts.order_code,
      confirmed_at: new Date().toISOString(),
      batch_total_cost: opts.batch_total_cost,
      screenshot_name: opts.screenshot_name,
      lines: opts.lines,
      note: "本地规格单价；云端仅保留批次总成本。见 Ship_Stats_Correspondence.md",
    };
    fs.writeFileSync(abs, JSON.stringify(payload, null, 2) + "\n", "utf8");
    return { ok: true, path: abs };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : String(e) };
  }
}

export function mergeArchiveEntries(
  fileEntries: ArchiveEntry[],
  jobs: JobRow[],
): ArchiveEntry[] {
  const map = new Map<string, ArchiveEntry>();
  for (const e of fileEntries) {
    map.set(e.job_id || e.id, {
      ...e,
      order_short: e.order_short || orderShortFromCode(e.order_code),
    });
  }
  for (const job of jobs) {
    const fromJob = entryFromJob(job);
    if (!fromJob) continue;
    const key = fromJob.job_id || fromJob.id;
    const prev = map.get(key);
    if (!prev || fromJob.archived_at >= prev.archived_at) {
      map.set(key, {
        ...fromJob,
        cost: prev?.cost?.status && prev.cost.status !== "none" ? prev.cost : fromJob.cost,
      });
    } else if (prev && (!prev.spec_details || prev.spec_details.length === 0)) {
      map.set(key, {
        ...prev,
        spec_details: fromJob.spec_details,
        fba_shipment_ids: prev.fba_shipment_ids?.length
          ? prev.fba_shipment_ids
          : fromJob.fba_shipment_ids,
        order_short: prev.order_short || fromJob.order_short,
      });
    }
  }
  return Array.from(map.values()).sort((a, b) => {
    const d = b.ship_date.localeCompare(a.ship_date);
    if (d !== 0) return d;
    return a.order_code.localeCompare(b.order_code);
  });
}

export function buildArchiveTree(entries: ArchiveEntry[]): ArchiveYearNode[] {
  const years = new Map<string, Map<string, Map<string, ArchiveEntry[]>>>();

  for (const e of entries) {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(e.ship_date);
    if (!m) continue;
    const [, y, mo, d] = m;
    if (!years.has(y)) years.set(y, new Map());
    const months = years.get(y)!;
    if (!months.has(mo)) months.set(mo, new Map());
    const days = months.get(mo)!;
    if (!days.has(d)) days.set(d, []);
    days.get(d)!.push(e);
  }

  const yearNodes: ArchiveYearNode[] = [];
  for (const y of Array.from(years.keys()).sort((a, b) => b.localeCompare(a))) {
    const months = years.get(y)!;
    const monthNodes: ArchiveMonthNode[] = [];
    let yTickets = 0;
    let yCartons = 0;
    for (const mo of Array.from(months.keys()).sort((a, b) => b.localeCompare(a))) {
      const days = months.get(mo)!;
      const dayNodes: ArchiveDayNode[] = [];
      let mTickets = 0;
      let mCartons = 0;
      for (const d of Array.from(days.keys()).sort((a, b) => b.localeCompare(a))) {
        const list = days.get(d)!.slice().sort((a, b) => a.order_code.localeCompare(b.order_code));
        const carton_sum = list.reduce((s, e) => s + (e.carton_count ?? 0), 0);
        dayNodes.push({
          day: d,
          date: `${y}-${mo}-${d}`,
          entries: list,
          ticket_count: list.length,
          carton_sum,
        });
        mTickets += list.length;
        mCartons += carton_sum;
      }
      monthNodes.push({
        month: mo,
        days: dayNodes,
        ticket_count: mTickets,
        carton_sum: mCartons,
      });
      yTickets += mTickets;
      yCartons += mCartons;
    }
    yearNodes.push({
      year: y,
      months: monthNodes,
      ticket_count: yTickets,
      carton_sum: yCartons,
    });
  }
  return yearNodes;
}

export { formatLeafLabel, orderShortFromCode } from "./archive-display";
