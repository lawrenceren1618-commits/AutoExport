import type { JobRow } from "./jobs";
import { cloudPipeline } from "./schema";

export type JobStage = "input" | "extract" | "process" | "output";

export type JobPhase =
  | "await_plan"
  | "order_labels"
  | "await_carton"
  | "trio"
  | "await_inbound"
  | "pack_gate"
  | "done";

export type JobMeta = {
  order_code?: string;
  order_short?: string;
  outbound_short?: string;
  order_date?: string;
  /** 订单交货日（计划发货；非创建作业时刻） */
  order_delivery_date?: string;
  /** 实际交货/实发日；存档树日期优先用此 */
  actual_delivery_date?: string;
  total_strips?: number;
  lines?: unknown[];
  phase?: JobPhase;
  uploads?: {
    ship_plan?: boolean;
    carton_and_tracking?: boolean;
    freight_inbound?: boolean;
  };
  upload_files?: Record<
    string,
    { name: string; size: number; ext: string; at?: string }[]
  >;
  carton_recognition?: {
    rows: {
      warehouse_code: string;
      fba_shipment_id: string;
      reference_id: string;
      carton_count: number | null;
      strip_count: number | null;
      source_filename: string;
      recognize_notes: string;
      tracking_id?: string;
    }[];
    tracking_id?: string;
    user_confirmed?: boolean;
    confirmed_at?: string;
  };
  extracts?: Record<string, unknown>;
  artifacts?: Record<string, { status: string; note?: string }>;
  /** Published Storage / local-blob object index */
  storage_files?: Record<
    string,
    {
      name: string;
      storage_path: string;
      backend: string;
      sha256: string;
      byte_size: number;
    }[]
  >;
  gate_report?: { ok: boolean; checks: string[]; at?: string };
  batch?: { mode: "once" | "split"; legs?: string[] };
  /** ship_plan upload | manual_lines 手补 */
  plan_mode?: string;
  /** Local↔cloud completion sync (see Local_Cloud_Execution_Plane.md) */
  sync?: {
    pushed_at?: string;
    pulled_at?: string;
    cloud_ready?: boolean;
    last_error?: string;
  };
  /** Pending H01 settle rows — listed on push; not auto-ingested */
  settle_candidates?: Record<string, unknown>[];
};

export function getMeta(job: JobRow): JobMeta {
  return (job.meta || {}) as JobMeta;
}

export function phaseOf(job: JobRow): JobPhase {
  return getMeta(job).phase || "await_plan";
}

export function stageFocus(phase: JobPhase): JobStage {
  switch (phase) {
    case "await_plan":
    case "await_carton":
    case "await_inbound":
      return "input";
    case "order_labels":
    case "trio":
      return "extract";
    case "pack_gate":
      return "process";
    case "done":
      return "output";
    default:
      return "input";
  }
}

export const PIPELINE_STEPS = cloudPipeline.pipeline_steps;

export type RunStepId =
  | "extract_plan"
  | "enrich_master"
  | "gen_order"
  | "gen_product_labels"
  | "extract_warehouse"
  | "decide_batch"
  | "gen_trio"
  | "pack_shipment_labels"
  | "gate"
  | "archive";

export function nextStepsForPhase(phase: JobPhase): RunStepId[] {
  switch (phase) {
    case "await_plan":
      return ["extract_plan", "enrich_master", "gen_order", "gen_product_labels"];
    case "order_labels":
      return [];
    case "await_carton":
      return ["extract_warehouse", "decide_batch", "gen_trio"];
    case "trio":
      return [];
    case "await_inbound":
      return ["pack_shipment_labels", "gate"];
    case "pack_gate":
      return ["archive"];
    default:
      return [];
  }
}
