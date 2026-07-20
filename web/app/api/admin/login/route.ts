import { NextRequest, NextResponse } from "next/server";
import { ADMIN_COOKIE_NAME } from "@/lib/admin-auth";

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const password = String(body.password ?? "");
  const expected = process.env.OFCE_ADMIN_PASSWORD;

  if (!expected) {
    if (process.env.NODE_ENV === "development") {
      const res = NextResponse.json({ ok: true, mode: "dev-open" });
      res.cookies.set(ADMIN_COOKIE_NAME, "dev", {
        httpOnly: true,
        sameSite: "lax",
        path: "/",
      });
      return res;
    }
    return NextResponse.json(
      { error: "未配置 OFCE_ADMIN_PASSWORD" },
      { status: 500 }
    );
  }

  if (password !== expected) {
    return NextResponse.json({ error: "口令错误" }, { status: 401 });
  }

  const res = NextResponse.json({ ok: true });
  res.cookies.set(ADMIN_COOKIE_NAME, expected, {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    secure: process.env.NODE_ENV === "production",
    maxAge: 60 * 60 * 24 * 7,
  });
  return res;
}
