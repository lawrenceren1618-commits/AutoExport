import { INPUT_SECTIONS, findInputSection } from "./schema";
import type { JobRow } from "./jobs";
import { getMeta } from "./stages";

export type WaveId = "after_plan" | "trio_after_carton" | "after_inbound" | "finalize";

export type PreflightIssue = {
  code: string;
  section?: string;
  message: string;
};

export type WavePreflightResult = {
  ok: boolean;
  wave: WaveId;
  issues: PreflightIssue[];
  checklist: { item: string; ok: boolean }[];
};

const EXT_MAP: Record<string, string[]> = {
  ship_plan: [".xls", ".xlsx", ".csv", ".json"],
  carton_and_tracking: [".pdf", ".png", ".jpg", ".jpeg", ".zip", ".webp"],
  freight_inbound: [".pdf", ".zip"],
};

export function extOf(name: string): string {
  const i = name.lastIndexOf(".");
  return i >= 0 ? name.slice(i).toLowerCase() : "";
}

export function isAllowedExt(sectionId: string, filename: string): boolean {
  const sec = findInputSection(sectionId);
  const id = sec?.id || sectionId;
  const allowed = EXT_MAP[id] || (sec?.accept as string[]) || [];
  const e = extOf(filename);
  return allowed.includes(e);
}

export function wavePreflight(job: JobRow, wave: WaveId): WavePreflightResult {
  const meta = getMeta(job);
  const uploads = meta.uploads || {};
  const files = (meta.upload_files || {}) as Record<
    string,
    { name: string; size: number; ext: string }[]
  >;
  const recog = meta.carton_recognition as
    | {
        user_confirmed?: boolean;
        rows?: { warehouse_code?: string; fba_shipment_id?: string }[];
        tracking_id?: string;
      }
    | undefined;
  const artifacts = meta.artifacts || {};
  const issues: PreflightIssue[] = [];
  const checklist: { item: string; ok: boolean }[] = [];

  const hasPlan =
    Boolean(uploads.ship_plan) ||
    Boolean(meta.lines && meta.lines.length) ||
    (typeof meta.total_strips === "number" && meta.total_strips > 0);
  const hasCarton = Boolean(uploads.carton_and_tracking);
  const hasInbound = Boolean(uploads.freight_inbound);

  const planFiles = files.ship_plan || [];
  const cartonFiles = files.carton_and_tracking || [];
  const inboundFiles = files.freight_inbound || [];

  if (wave === "after_plan") {
    checklist.push({ item: "发货计划或总条数/计划行已提供", ok: hasPlan });
    if (!hasPlan) {
      issues.push({
        code: "missing_ship_plan",
        section: "ship_plan",
        message: "缺少发货计划：请上传计划表，或在创建时填写总条数",
      });
    }
    for (const f of planFiles) {
      const ok = isAllowedExt("ship_plan", f.name);
      checklist.push({ item: `计划格式 ${f.name}`, ok });
      if (!ok) {
        issues.push({
          code: "bad_ext",
          section: "ship_plan",
          message: `发货计划格式不符：${f.name}（允许 ${EXT_MAP.ship_plan.join(" ")}）`,
        });
      }
    }
    if (uploads.ship_plan && planFiles.length === 0) {
      checklist.push({ item: "计划文件已登记文件名", ok: false });
      issues.push({
        code: "plan_no_filename",
        section: "ship_plan",
        message: "已点上传但无有效文件名记录，请重新选择文件",
      });
    }
  }

  if (wave === "trio_after_carton") {
    checklist.push({ item: "已上传外箱贴/追踪截图", ok: hasCarton });
    if (!hasCarton) {
      issues.push({
        code: "missing_carton",
        section: "carton_and_tracking",
        message: "缺少亚马逊外箱贴与追踪截图",
      });
    }
    for (const f of cartonFiles) {
      const ok = isAllowedExt("carton_and_tracking", f.name);
      checklist.push({ item: `外箱贴格式 ${f.name}`, ok });
      if (!ok) {
        issues.push({
          code: "bad_ext",
          section: "carton_and_tracking",
          message: `外箱贴/截图格式不符：${f.name}`,
        });
      }
    }
    const rows = recog?.rows || [];
    const confirmed = Boolean(recog?.user_confirmed);
    const allHaveWhFba =
      rows.length > 0 &&
      rows.every((r) => Boolean(r?.warehouse_code) && Boolean(r?.fba_shipment_id));
    checklist.push({
      item: `外箱贴识别行数（${rows.length || 0}，不限上限）`,
      ok: rows.length > 0,
    });
    checklist.push({ item: "每行已具备仓库代码与货件号", ok: allHaveWhFba });
    checklist.push({ item: "识别结果已人工确认", ok: confirmed });
    if (rows.length === 0) {
      issues.push({
        code: "need_recog_rows",
        section: "carton_and_tracking",
        message: "尚无仓库识别行：请上传/粘贴外箱贴或截图，或手动添加仓库行",
      });
    }
    rows.forEach((r, i) => {
      if (!r?.warehouse_code) {
        issues.push({
          code: "need_warehouse",
          section: "carton_and_tracking",
          message: `第${i + 1}行未确认仓库代码`,
        });
      }
      if (!r?.fba_shipment_id) {
        issues.push({
          code: "need_fba",
          section: "carton_and_tracking",
          message: `第${i + 1}行未确认货件号`,
        });
      }
    });
    if (!confirmed) {
      issues.push({
        code: "recog_unconfirmed",
        section: "carton_and_tracking",
        message: "外箱贴/截图识别结果尚未确认，不得生成出货/货代/报关",
      });
    }
    const hasOrder = Boolean(artifacts.order_xlsx);
    checklist.push({ item: "已生成订单草稿（建议）", ok: hasOrder });
    if (!hasOrder) {
      issues.push({
        code: "order_before_trio",
        message: "建议先完成「生成订单与产品标签包」；当前阻断三表以免缺订单号口径",
      });
    }
  }

  if (wave === "after_inbound") {
    checklist.push({ item: "已上传货代入库贴", ok: hasInbound });
    if (!hasInbound) {
      issues.push({
        code: "missing_inbound",
        section: "freight_inbound",
        message: "缺少货代入库贴",
      });
    }
    for (const f of inboundFiles) {
      const ok = isAllowedExt("freight_inbound", f.name);
      checklist.push({ item: `入库贴格式 ${f.name}`, ok });
      if (!ok) {
        issues.push({
          code: "bad_ext",
          section: "freight_inbound",
          message: `入库贴格式不符：${f.name}`,
        });
      }
    }
    const hasTrio =
      Boolean(artifacts.outbound_xlsx) &&
      Boolean(artifacts.freight_xlsx) &&
      Boolean(artifacts.customs_xlsx);
    checklist.push({ item: "出货/货代/报关草稿已齐", ok: hasTrio });
    if (!hasTrio) {
      issues.push({
        code: "trio_missing",
        message: "请先生成出货表、货代下单表、报关单证",
      });
    }
  }

  if (wave === "finalize") {
    const gateOk = job.gate_final === "CONFIRMED" || meta.gate_report?.ok === true;
    checklist.push({ item: "Gate 已确认", ok: gateOk });
    if (!gateOk) {
      issues.push({ code: "gate_wait", message: "Gate 未确认，阻断存档" });
    }
  }

  // Always list input section presence summary for transparency
  for (const sec of INPUT_SECTIONS) {
    const present =
      sec.id === "ship_plan"
        ? hasPlan
        : sec.id === "carton_and_tracking"
          ? hasCarton
          : hasInbound;
    if (wave === "after_plan" && sec.id !== "ship_plan") continue;
    if (wave === "trio_after_carton" && sec.id === "freight_inbound") continue;
  }

  return { ok: issues.length === 0, wave, issues, checklist };
}
