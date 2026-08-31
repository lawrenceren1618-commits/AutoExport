import pipeline from "./cloud_workspace_pipeline.json";

export type SectionDirection = "in" | "out" | "archive";
export type SaveMode = "upload_raw" | "draft" | "pre_final" | "final" | "archive";
export type EntityCode = "C04" | "C07";

export type InputSection = (typeof pipeline.sections.input)[number];
export type OutputSection = (typeof pipeline.sections.output)[number];

export const cloudPipeline = pipeline;

export const INPUT_SECTIONS = pipeline.sections.input;
export const OUTPUT_SECTIONS = pipeline.sections.output;
export const ARCHIVE_SECTION = pipeline.sections.archive;

export const HANDSHAKES = pipeline.handshake;
export const SAVE_MODES = pipeline.save_modes;
export const EXPORT_RULES = pipeline.export_rules;
export const JOB_APIS = pipeline.apis;
export const FLOW_DEFAULTS = pipeline.flow_defaults;
export const UI_META = pipeline.ui;

export function brandForEntity(entity: EntityCode): "WIGENIUS" | "Dressmaker" {
  return entity === "C04" ? "WIGENIUS" : "Dressmaker";
}

export function storagePath(jobId: string, prefixTemplate: string): string {
  return prefixTemplate.replace("{job_id}", jobId);
}

/** Resolve section by id or legacy alias (order_plan → ship_plan). */
export function findInputSection(idOrAlias: string): InputSection | undefined {
  return INPUT_SECTIONS.find(
    (s) =>
      s.id === idOrAlias ||
      ("aliases" in s &&
        Array.isArray((s as { aliases?: string[] }).aliases) &&
        (s as { aliases?: string[] }).aliases!.includes(idOrAlias)),
  );
}
