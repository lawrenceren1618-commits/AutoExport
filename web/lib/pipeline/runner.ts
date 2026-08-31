import type { JobRow } from "./jobs";
import { updateJobMeta } from "./jobs";
import {
  batchLabelFromMeta,
  cartonCountFromJob,
  fbaIdsFromJob,
  resolveArchiveShipDate,
  specDetailsFromJob,
  upsertArchiveEntry,
} from "./archive-index";
import { runPythonGenerateStep } from "./generate-bridge";
import { getMeta, type JobPhase, type RunStepId } from "./stages";

type RunResult = {
  ok: boolean;
  step: RunStepId;
  message: string;
  job: JobRow;
  mock?: boolean;
  issues?: { code: string; message: string }[];
};

async function setArtifacts(
  job: JobRow,
  ids: string[],
  note: string,
  phase?: JobPhase,
): Promise<JobRow> {
  const artifacts = { ...(getMeta(job).artifacts || {}) };
  for (const id of ids) {
    artifacts[id] = { status: "draft", note };
  }
  const updated = await updateJobMeta(job.id, {
    artifacts,
    ...(phase ? { phase } : {}),
  });
  return updated || job;
}

/** Stage runner — generators still Python; cloud records draft contracts + phase locks. */
export async function runJobStep(
  job: JobRow,
  step: RunStepId,
  opts?: { confirm_gate?: boolean },
): Promise<RunResult> {
  const meta = getMeta(job);
  const uploads = meta.uploads || {};

  switch (step) {
    case "extract_plan": {
      if (!uploads.ship_plan && !(meta.lines && meta.lines.length)) {
        return {
          ok: false,
          step,
          message: "预检不足：请先上传发货计划或在创建时提供计划行",
          job,
        };
      }
      const updated = await updateJobMeta(job.id, {
        extracts: {
          ...(meta.extracts || {}),
          plan_keys: {
            entity: job.entity_code,
            lines: meta.lines?.length || "from_upload",
            total_strips: meta.total_strips,
          },
        },
        phase: "await_plan",
      });
      return {
        ok: true,
        step,
        message: "已提取规格键（契约）",
        job: updated || job,
        mock: true,
      };
    }
    case "enrich_master": {
      const updated = await updateJobMeta(job.id, {
        extracts: {
          ...(meta.extracts || {}),
          enrich: { status: "joined_settled_or_master", note: "冲突须确认" },
        },
      });
      return {
        ok: true,
        step,
        message: "总表补齐契约已记录",
        job: updated || job,
        mock: true,
      };
    }
    case "gen_order": {
      const bridged = await runPythonGenerateStep(job, "gen_order");
      return {
        ok: bridged.ok,
        step,
        message: bridged.message,
        job: bridged.job,
        mock: bridged.mock,
        issues: bridged.issues,
      };
    }
    case "gen_product_labels": {
      const bridged = await runPythonGenerateStep(job, "gen_product_labels");
      // Keep phase await_carton even on partial success
      if (bridged.ok) {
        const updated = await updateJobMeta(bridged.job.id, { phase: "await_carton" });
        return {
          ok: true,
          step,
          message: bridged.message,
          job: updated || bridged.job,
          mock: bridged.mock,
          issues: bridged.issues,
        };
      }
      return {
        ok: false,
        step,
        message: bridged.message,
        job: bridged.job,
        mock: bridged.mock,
        issues: bridged.issues,
      };
    }
    case "extract_warehouse": {
      if (!uploads.carton_and_tracking) {
        return {
          ok: false,
          step,
          message: "预检不足：请先上传外箱贴与追踪截图",
          job,
        };
      }
      const updated = await updateJobMeta(job.id, {
        extracts: {
          ...(meta.extracts || {}),
          warehouse: { status: "pending_parser", note: "仓×规格×箱" },
        },
      });
      return {
        ok: true,
        step,
        message: "仓规格提取契约已记录",
        job: updated || job,
        mock: true,
      };
    }
    case "decide_batch": {
      const updated = await updateJobMeta(job.id, {
        batch: {
          mode: "once",
          legs: [`${meta.order_short || "Cxxxxx"}-A`],
        },
      });
      return {
        ok: true,
        step,
        message: "分批判定默认一次发完（-A）；有剩余时再开 B/C",
        job: updated || job,
        mock: true,
      };
    }
    case "gen_trio": {
      if (!uploads.carton_and_tracking) {
        return {
          ok: false,
          step,
          message: "预检不足：缺外箱贴与追踪",
          job,
        };
      }
      const bridged = await runPythonGenerateStep(job, "gen_trio");
      if (bridged.ok) {
        const updated = await updateJobMeta(bridged.job.id, { phase: "await_inbound" });
        return {
          ok: true,
          step,
          message: bridged.message,
          job: updated || bridged.job,
          mock: bridged.mock,
          issues: bridged.issues,
        };
      }
      return {
        ok: bridged.ok,
        step,
        message: bridged.message,
        job: bridged.job,
        mock: bridged.mock,
        issues: bridged.issues,
      };
    }
    case "pack_shipment_labels": {
      if (!uploads.freight_inbound) {
        return {
          ok: false,
          step,
          message: "预检不足：请先上传货代入库贴",
          job,
        };
      }
      const updated = await setArtifacts(
        job,
        ["shipment_label_pack"],
        "发货贴标包 zip 契约",
        "pack_gate",
      );
      return {
        ok: true,
        step,
        message: "发货贴标包打包契约已登记",
        job: updated,
        mock: true,
      };
    }
    case "gate": {
      const checks = [
        "entity_brand_lock",
        "order_vs_outbound_codes",
        "carton_vs_plan_qty",
        "trio_internal_consistency",
      ];
      const ok = opts?.confirm_gate === true;
      const updated = await updateJobMeta(job.id, {
        gate_report: {
          ok,
          checks,
          at: new Date().toISOString(),
        },
        gate_final: ok ? "CONFIRMED" : "WAIT",
        phase: ok ? "pack_gate" : "pack_gate",
      });
      return {
        ok,
        step,
        message: ok
          ? "Gate 用户确认通过，可 Final / 存档"
          : "交叉验证报告已生成；请确认无误后带 confirm_gate=true 再跑",
        job: updated || job,
        mock: true,
      };
    }
    case "archive": {
      if (job.gate_final !== "CONFIRMED" && getMeta(job).gate_report?.ok !== true) {
        const fresh = await getJobFresh(job.id);
        if (!fresh || fresh.gate_final !== "CONFIRMED") {
          return {
            ok: false,
            step,
            message: "Gate 未确认，阻断存档",
            job: fresh || job,
          };
        }
      }
      const current = (await getJobFresh(job.id)) || job;
      if (current.gate_final !== "CONFIRMED") {
        return { ok: false, step, message: "Gate 未确认，阻断存档", job: current };
      }
      const prevMeta = getMeta(current);
      const artifacts = {
        ...(prevMeta.artifacts || {}),
        audit_archive: { status: "done", note: "汇总存档凭证" },
      };
      const updated =
        (await updateJobMeta(current.id, {
          artifacts,
          phase: "done",
        })) || current;
      const meta = getMeta(updated);
      const shipDate = resolveArchiveShipDate(updated);
      if (shipDate && (meta.order_code || updated.project_code)) {
        upsertArchiveEntry({
          id: updated.id,
          ship_date: shipDate,
          order_code: meta.order_code || updated.project_code,
          order_short: meta.order_short,
          project_code: updated.project_code,
          entity_code: updated.entity_code,
          batch_label: batchLabelFromMeta(meta),
          carton_count: cartonCountFromJob(updated),
          total_strips: meta.total_strips ?? null,
          spec_details: specDetailsFromJob(updated),
          freight_forwarder_name: "物易通",
          fba_shipment_ids: fbaIdsFromJob(updated),
          cost: { status: "none" },
          job_id: updated.id,
          archived_at: new Date().toISOString(),
          source: "job_archive",
        });
      }
      return {
        ok: true,
        step,
        message: "存档凭证已登记（索引按实际交货日优先，否则订单交货日）",
        job: updated,
        mock: true,
      };
    }
    default:
      return { ok: false, step, message: "unknown step", job };
  }
}

async function getJobFresh(id: string): Promise<JobRow | null> {
  const { getJob } = await import("./jobs");
  return getJob(id);
}
