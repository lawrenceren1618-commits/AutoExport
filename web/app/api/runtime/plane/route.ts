import { NextResponse } from "next/server";
import {
  detectExecutionPlane,
  getEffectivePlane,
  planeLabel,
  PLANE_COOKIE,
} from "@/lib/runtime/execution-plane";

/**
 * GET /api/runtime/plane
 * Optional ?set=local|cloud to set session cookie override.
 */
export async function GET(req: Request) {
  const url = new URL(req.url);
  const set = url.searchParams.get("set");
  const detected = detectExecutionPlane();
  let effective = getEffectivePlane(req);

  const res = NextResponse.json({
    ok: true,
    detected,
    effective,
    label: planeLabel(effective),
    env: process.env.EXECUTION_PLANE || "auto",
    vercel: Boolean(process.env.VERCEL),
    doc: "Templates/Local_Cloud_Execution_Plane.md",
  });

  if (set === "local" || set === "cloud") {
    effective = set;
    res.cookies.set(PLANE_COOKIE, set, {
      path: "/",
      sameSite: "lax",
      httpOnly: false,
      maxAge: 60 * 60 * 12,
    });
    return NextResponse.json(
      {
        ok: true,
        detected,
        effective: set,
        label: planeLabel(set),
        env: process.env.EXECUTION_PLANE || "auto",
        vercel: Boolean(process.env.VERCEL),
        overridden: true,
        doc: "Templates/Local_Cloud_Execution_Plane.md",
      },
      { headers: res.headers },
    );
  }

  if (set === "auto" || set === "clear") {
    res.cookies.set(PLANE_COOKIE, "", { path: "/", maxAge: 0 });
    return NextResponse.json(
      {
        ok: true,
        detected,
        effective: detected,
        label: planeLabel(detected),
        env: process.env.EXECUTION_PLANE || "auto",
        vercel: Boolean(process.env.VERCEL),
        overridden: false,
        doc: "Templates/Local_Cloud_Execution_Plane.md",
      },
      { headers: res.headers },
    );
  }

  return res;
}
