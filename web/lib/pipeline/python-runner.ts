/**
 * Local Python generator bridge (office / npm run dev).
 * Vercel: set PYTHON_RUNNER=off|http — spawn disabled by default on Vercel.
 */

import { spawn } from "child_process";
import fs from "fs";
import path from "path";

export type PythonRunResult = {
  ok: boolean;
  exitCode: number | null;
  stdout: string;
  stderr: string;
  timedOut?: boolean;
  skipped?: boolean;
  reason?: string;
};

function repoRoot(): string {
  const candidates = [
    path.join(process.cwd(), "Scripts"),
    path.join(process.cwd(), "..", "Scripts"),
  ];
  for (const c of candidates) {
    if (fs.existsSync(path.join(c, "order_code_seq.json"))) return path.dirname(c);
  }
  return path.join(process.cwd(), "..");
}

export function getRepoRoot(): string {
  return repoRoot();
}

export function pythonRunnerMode(): "local" | "off" | "http" {
  const m = (process.env.PYTHON_RUNNER || "").toLowerCase();
  if (m === "off" || m === "http" || m === "local") return m;
  // Vercel / serverless: do not spawn
  if (process.env.VERCEL || process.env.AWS_LAMBDA_FUNCTION_NAME) return "off";
  return "local";
}

function pythonBin(): string {
  return process.env.PYTHON_BIN || (process.platform === "win32" ? "python" : "python3");
}

export async function runPythonScript(opts: {
  scriptRel: string;
  args?: string[];
  timeoutMs?: number;
  env?: Record<string, string>;
}): Promise<PythonRunResult> {
  const mode = pythonRunnerMode();
  if (mode === "off") {
    return {
      ok: false,
      exitCode: null,
      stdout: "",
      stderr: "",
      skipped: true,
      reason: "PYTHON_RUNNER=off (or serverless); use local office runner or HTTP worker",
    };
  }
  if (mode === "http") {
    const url = process.env.PYTHON_WORKER_URL;
    if (!url) {
      return {
        ok: false,
        exitCode: null,
        stdout: "",
        stderr: "",
        skipped: true,
        reason: "PYTHON_RUNNER=http but PYTHON_WORKER_URL unset",
      };
    }
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          ...(process.env.PYTHON_WORKER_SECRET
            ? { authorization: `Bearer ${process.env.PYTHON_WORKER_SECRET}` }
            : {}),
        },
        body: JSON.stringify({
          script: opts.scriptRel,
          args: opts.args || [],
        }),
      });
      const data = (await res.json().catch(() => ({}))) as {
        ok?: boolean;
        exitCode?: number;
        stdout?: string;
        stderr?: string;
      };
      return {
        ok: Boolean(data.ok ?? res.ok),
        exitCode: data.exitCode ?? (res.ok ? 0 : 1),
        stdout: data.stdout || "",
        stderr: data.stderr || "",
      };
    } catch (e) {
      return {
        ok: false,
        exitCode: null,
        stdout: "",
        stderr: e instanceof Error ? e.message : String(e),
        reason: "http_worker_failed",
      };
    }
  }

  const root = repoRoot();
  const scriptAbs = path.join(root, opts.scriptRel);
  if (!fs.existsSync(scriptAbs)) {
    return {
      ok: false,
      exitCode: null,
      stdout: "",
      stderr: `script not found: ${scriptAbs}`,
    };
  }

  const timeoutMs = opts.timeoutMs ?? 120_000;
  return new Promise((resolve) => {
    const child = spawn(pythonBin(), [scriptAbs, ...(opts.args || [])], {
      cwd: root,
      env: { ...process.env, ...opts.env, PYTHONIOENCODING: "utf-8" },
      windowsHide: true,
    });
    let stdout = "";
    let stderr = "";
    let settled = false;
    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      child.kill();
      resolve({
        ok: false,
        exitCode: null,
        stdout,
        stderr,
        timedOut: true,
        reason: `timeout ${timeoutMs}ms`,
      });
    }, timeoutMs);

    child.stdout.on("data", (d) => {
      stdout += String(d);
    });
    child.stderr.on("data", (d) => {
      stderr += String(d);
    });
    child.on("error", (err) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve({
        ok: false,
        exitCode: null,
        stdout,
        stderr: stderr + String(err.message),
        reason: "spawn_error",
      });
    });
    child.on("close", (code) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve({
        ok: code === 0,
        exitCode: code,
        stdout,
        stderr,
      });
    });
  });
}

/** Parse last RESULT={json} line from Python stdout */
export function parsePythonResultJson(stdout: string): Record<string, unknown> | null {
  const lines = stdout.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  for (let i = lines.length - 1; i >= 0; i--) {
    const line = lines[i];
    if (line.startsWith("RESULT=")) {
      try {
        return JSON.parse(line.slice("RESULT=".length)) as Record<string, unknown>;
      } catch {
        return null;
      }
    }
  }
  return null;
}
