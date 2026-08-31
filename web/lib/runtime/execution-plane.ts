/**
 * Execution plane: local vs cloud.
 * Auto: Vercel → cloud; else local. Override: EXECUTION_PLANE=local|cloud|auto
 * Session override: cookie / header `ae-plane`
 */

export type ExecutionPlane = "local" | "cloud";

export const PLANE_COOKIE = "ae-plane";
export const PLANE_HEADER = "x-ae-plane";

function envPlaneRaw(): string {
  return (process.env.EXECUTION_PLANE || "auto").trim().toLowerCase();
}

/** Detect from env only (no request override). */
export function detectExecutionPlane(): ExecutionPlane {
  const raw = envPlaneRaw();
  if (raw === "local" || raw === "cloud") return raw;
  // auto
  if (process.env.VERCEL === "1" || process.env.VERCEL === "true") return "cloud";
  return "local";
}

function parseOverride(v: string | null | undefined): ExecutionPlane | null {
  if (!v) return null;
  const t = v.trim().toLowerCase();
  if (t === "local" || t === "cloud") return t;
  return null;
}

/** Effective plane for an API request (header > cookie > detect). */
export function getEffectivePlane(req?: Request): ExecutionPlane {
  if (req) {
    const fromHeader = parseOverride(req.headers.get(PLANE_HEADER));
    if (fromHeader) return fromHeader;
    const cookie = req.headers.get("cookie") || "";
    const m = cookie.match(/(?:^|;\s*)ae-plane=(local|cloud)/i);
    if (m) return m[1].toLowerCase() as ExecutionPlane;
  }
  return detectExecutionPlane();
}

export function planeLabel(plane: ExecutionPlane): string {
  return plane === "local" ? "本机" : "云端";
}
