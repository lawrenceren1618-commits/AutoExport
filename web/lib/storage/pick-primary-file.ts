/**
 * Pick the user-facing deliverable from a section's storage_files list.
 * Draft/manifest JSON are sidecars — never preferred when a real workbook/PDF exists.
 */

export type NamedStoredFile = {
  name: string;
  storage_path: string;
  backend?: string;
  sha256?: string;
  byte_size?: number;
};

function isSidecarJson(name: string): boolean {
  const n = name.toLowerCase();
  if (!n.endsWith(".json")) return false;
  return (
    n.includes("draft") ||
    n.includes("manifest") ||
    n.includes("design_match") ||
    n.endsWith("__manifest.json") ||
    n.endsWith("_manifest.json")
  );
}

/** Prefer deliverable extensions; scan from newest (end) to oldest. */
export function pickPrimaryStoredFile(
  sectionId: string,
  files: NamedStoredFile[],
): NamedStoredFile | null {
  if (!files.length) return null;
  const fromNewest = [...files].reverse();

  if (sectionId === "order_xlsx") {
    return (
      fromNewest.find((f) => /\.xlsx$/i.test(f.name)) ||
      fromNewest.find((f) => /\.xls$/i.test(f.name) && !isSidecarJson(f.name)) ||
      fromNewest.find((f) => !isSidecarJson(f.name)) ||
      fromNewest[0]
    );
  }

  if (sectionId === "product_label_pack") {
    return (
      fromNewest.find((f) => /\.pdf$/i.test(f.name)) ||
      fromNewest.find((f) => /\.zip$/i.test(f.name)) ||
      fromNewest.find((f) => !isSidecarJson(f.name)) ||
      fromNewest[0]
    );
  }

  if (
    sectionId === "outbound_xlsx" ||
    sectionId === "freight_xlsx" ||
    sectionId === "customs_xlsx"
  ) {
    return (
      fromNewest.find((f) => /\.xlsx?$/i.test(f.name)) ||
      fromNewest.find((f) => !isSidecarJson(f.name)) ||
      fromNewest[0]
    );
  }

  return fromNewest.find((f) => !isSidecarJson(f.name)) || fromNewest[0];
}
