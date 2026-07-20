import { cookies } from "next/headers";

const COOKIE = "ofce_admin";

export async function isAdminAuthenticated(): Promise<boolean> {
  const jar = await cookies();
  const token = jar.get(COOKIE)?.value;
  const expected = process.env.OFCE_ADMIN_PASSWORD;
  if (!expected) {
    // Dev without password: allow admin UI locally only when OFCE_ENV unset or office
    return process.env.NODE_ENV === "development";
  }
  return token === expected;
}

export { COOKIE as ADMIN_COOKIE_NAME };
