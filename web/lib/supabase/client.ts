import { createClient, SupabaseClient } from "@supabase/supabase-js";

function supabaseDbSchema(): string {
  return (
    process.env.NEXT_PUBLIC_SUPABASE_SCHEMA ||
    process.env.SUPABASE_DB_SCHEMA ||
    "autoexport"
  );
}

export function assertOfficeEnv(): void {
  const env = process.env.OFCE_ENV;
  if (env && env !== "office") {
    throw new Error(
      `OFCE_ENV must be "office" for this deployment (got "${env}"). Refusing to continue — home/office isolation.`
    );
  }
}

export function getSupabaseAnon(): SupabaseClient | null {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key || url.includes("YOUR_PROJECT")) return null;
  const schema = supabaseDbSchema();
  return createClient(url, key, {
    db: { schema },
  });
}

/** Server-only client for writes (master import H01). */
export function getSupabaseService(): SupabaseClient | null {
  assertOfficeEnv();
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key || url.includes("YOUR_PROJECT")) return null;
  const schema = supabaseDbSchema();
  return createClient(url, key, {
    db: { schema },
    auth: { persistSession: false, autoRefreshToken: false },
  });
}

export function isSupabaseConfigured(): boolean {
  return getSupabaseAnon() !== null;
}