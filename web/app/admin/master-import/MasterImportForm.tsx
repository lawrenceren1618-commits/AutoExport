"use client";

import { FormEvent, useState } from "react";

type PreviewRow = Record<string, string | number | boolean | null>;

export function MasterImportForm() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<PreviewRow[]>([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function parseOnly(e: FormEvent) {
    e.preventDefault();
    if (!file) {
      setError("请选择总表文件");
      return;
    }
    setLoading(true);
    setError("");
    setMessage("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("mode", "preview");
      const res = await fetch("/api/master-import", { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "解析失败");
        return;
      }
      setPreview(data.rows ?? []);
      setMessage(`预览 ${data.rowCount} 行（未入库）。确认无误后勾选并提交入库。`);
    } catch {
      setError("网络错误");
    } finally {
      setLoading(false);
    }
  }

  async function confirmIngest(e: FormEvent) {
    e.preventDefault();
    if (!file) {
      setError("请选择总表文件");
      return;
    }
    setLoading(true);
    setError("");
    setMessage("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("mode", "confirm");
      fd.append("confirmed", "true");
      const res = await fetch("/api/master-import", { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "入库失败");
        return;
      }
      setMessage(
        `握手 H01 完成：已确认入库 products=${data.insertedProducts} packing=${data.insertedPacking} fnsku=${data.insertedFnsku}`
      );
    } catch {
      setError("网络错误");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <form onSubmit={parseOnly}>
        <p>
          <label htmlFor="file">总表（.xlsx / .xls / .csv）</label>
          <br />
          <input
            id="file"
            type="file"
            accept=".xlsx,.xls,.csv"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </p>
        <button className="btn btn-secondary" type="submit" disabled={loading}>
          仅预览（不入库）
        </button>
      </form>
      <form onSubmit={confirmIngest} style={{ marginTop: "1rem" }}>
        <p className="muted">
          握手 H01：必须显式确认后才写入沉淀表。未配置 Supabase 时预览可用，确认入库会返回配置提示。
        </p>
        <button className="btn" type="submit" disabled={loading || !file}>
          我已确认，写入沉淀库
        </button>
      </form>
      {error ? <p className="status-blocked">{error}</p> : null}
      {message ? <p className="status-doing">{message}</p> : null}
      {preview.length > 0 ? (
        <div style={{ overflowX: "auto", marginTop: "1rem" }}>
          <table
            style={{
              borderCollapse: "collapse",
              width: "100%",
              fontSize: "0.85rem",
            }}
          >
            <thead>
              <tr>
                {Object.keys(preview[0]).map((k) => (
                  <th
                    key={k}
                    style={{
                      border: "1px solid #d8dde6",
                      padding: "0.35rem",
                      textAlign: "left",
                    }}
                  >
                    {k}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {preview.slice(0, 30).map((row, i) => (
                <tr key={i}>
                  {Object.keys(preview[0]).map((k) => (
                    <td
                      key={k}
                      style={{ border: "1px solid #d8dde6", padding: "0.35rem" }}
                    >
                      {row[k] == null ? "" : String(row[k])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {preview.length > 30 ? (
            <p className="muted">仅显示前 30 行预览</p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
