"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

export default function OpsLoginPage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/admin/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "登录失败");
        return;
      }
      router.push("/ops/fba-track");
      router.refresh();
    } catch {
      setError("网络错误");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <div className="card">
        <h1>库务登录</h1>
        <p className="muted">
          用于总表入库、仓头追踪与进度树。口令见 <code>web/.env.local</code> 的{" "}
          <code>OFCE_ADMIN_PASSWORD</code>。未配置时仅开发模式可直接进入。
        </p>
        <form onSubmit={onSubmit}>
          <p>
            <label htmlFor="password">口令</label>
            <br />
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </p>
          {error ? <p className="status-blocked">{error}</p> : null}
          <button className="btn" type="submit" disabled={loading}>
            {loading ? "…" : "登录"}
          </button>
        </form>
        <p className="muted" style={{ marginTop: "1rem" }}>
          <Link href="/workspace">返回作业</Link>
        </p>
      </div>
    </main>
  );
}
