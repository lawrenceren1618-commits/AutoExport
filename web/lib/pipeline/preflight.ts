import {
  ARCHIVE_SECTION,
  INPUT_SECTIONS,
  OUTPUT_SECTIONS,
  type SaveMode,
} from "./schema";

export type PreflightItem = {
  sectionId: string;
  label: string;
  ok: boolean;
  missing: string[];
};

/** Document field preflight for cloud job — enough → run; else SKIP section */
export function preflightJob(state: {
  hasShipPlan: boolean;
  hasCartonTracking: boolean;
  hasFreightInbound: boolean;
  wantOutputs: string[];
}): PreflightItem[] {
  const items: PreflightItem[] = [];

  for (const sec of INPUT_SECTIONS) {
    const present =
      sec.id === "ship_plan"
        ? state.hasShipPlan
        : sec.id === "carton_and_tracking"
          ? state.hasCartonTracking
          : state.hasFreightInbound;
    items.push({
      sectionId: sec.id,
      label: sec.label,
      ok: present,
      missing: present ? [] : ["未上传"],
    });
  }

  for (const out of OUTPUT_SECTIONS) {
    if (!state.wantOutputs.includes(out.id)) continue;
    const missing: string[] = [];
    if (!state.hasShipPlan) missing.push("发货计划");
    if (
      (out.id === "freight_xlsx" ||
        out.id === "customs_xlsx" ||
        out.id === "outbound_xlsx" ||
        out.id === "shipment_label_pack") &&
      !state.hasCartonTracking
    ) {
      missing.push("外箱贴与追踪");
    }
    if (out.id === "shipment_label_pack" && !state.hasFreightInbound) {
      missing.push("货代入库贴");
    }
    items.push({
      sectionId: out.id,
      label: out.label,
      ok: missing.length === 0,
      missing,
    });
  }

  items.push({
    sectionId: ARCHIVE_SECTION.id,
    label: ARCHIVE_SECTION.label,
    ok: true,
    missing: [],
  });

  return items;
}

export function canEnterSaveMode(
  mode: SaveMode,
  gate: "WAIT" | "CONFIRMED" | "REJECTED",
): boolean {
  if (mode === "final" || mode === "archive") return gate === "CONFIRMED";
  return true;
}
