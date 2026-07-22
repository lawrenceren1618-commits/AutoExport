"use client";

import { useCallback, useEffect, useState } from "react";

type HeaderRow = {
  id?: string;
  order_code?: string | null;
  split_leg_id?: string | null;
  warehouse_code?: string | null;
  warehouse_address?: string | null;
  fba_shipment_id?: string | null;
  reference_id?: string | null;
  tracking_id?: string | null;
  carton_count?: number | null;
  strip_count?: number | null;
  source_filename?: string | null;
  recognize_notes?: string | null;
  status?: string | null;
  preview_data_url?: string;
};

export function FbaTrackPanel() {
  const [orderCode, setOrderCode] = useState("EF-C26079-C04-36460");
  const [splitLegId, setSplitLegId] = useState("C26079-A");
  const [files, setFiles] = useState<FileList | null>(null);
  const [preview, setPreview] = useState<HeaderRow[]>([]);
  const [saved, setSaved] = useState<HeaderRow[]>([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const loadSaved = useCallback(async () => {
    const q = new URLSearchParams();
    if (orderCode.trim()) q.set("order_code", orderCode.trim());
    if (splitLegId.trim()) q.set("split_leg_id", splitLegId.trim());
    const res = await fetch(`/api/fba-track?${q}`);
    const data = await res.json();
    if (!res.ok) {
      setError(data.error ?? "读取仓头失败");
      return;
    }
    setSaved(data.rows ?? []);
    setError("");
  }, [orderCode, splitLegId]);

  useEffect(() => {
    void loadSaved();
  }, [loadSaved]);

  async function recognize(e: FormEvent, save: boolean) {
    e.preventDefault();
    if (!files || files.length === 0) {
      setError("请选择外箱贴 PDF 或货件截图");
      return;
    }
    setLoading(true);
    setError("");
    setMessage("");
    try {
      const fd = new FormData();
      fd.set("order_code", orderCode.trim());
      fd.set("split_leg_id", splitLegId.trim());
      if (save) fd.set("save", "1");
      for (let i = 0; i < files.length; i++) {
        fd.append("files", files[i]);
      }
      const res = await fetch("/api/fba-track", { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok && !data.rows) {
        setError(data.error ?? "识别失败");
        return;
      }
      if (save) {
        setMessage(`已保存 ${data.saved ?? 0} 条仓头。请在下方表格填写追踪编码。`);
        if (data.error) setError(data.error);
        await loadSaved();
        setPreview([]);
      } else {
        setPreview(data.rows ?? []);
        setMessage(
          `识别 ${data.rowCount ?? 0} 个文件（未入库）。核对后点「保存仓头」，再填追踪编码。`
        );
        if (data.error) setError(data.error);
      }
    } catch {
      setError("网络错误");
    } finally {
      setLoading(false);
    }
  }

  async function saveTracking(row: HeaderRow) {
    if (!row.id) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/fba-track/update", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id: row.id,
          tracking_id: row.tracking_id ?? "",
          warehouse_code: row.warehouse_code ?? "",
          fba_shipment_id: row.fba_shipment_id ?? "",
          reference_id: row.reference_id ?? "",
          warehouse_address: row.warehouse_address ?? "",
          carton_count: row.carton_count,
          strip_count: row.strip_count,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "保存失败");
        return;
      }
      setMessage(`已更新追踪/仓头：${row.warehouse_code || row.fba_shipment_id || row.id}`);
      await loadSaved();
    } catch {
      setError("网络错误");
    } finally {
      setLoading(false);
    }
  }

  function patchSaved(id: string, patch: Partial<HeaderRow>) {
    setSaved((prev) => prev.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  }

  return (
    <div>
      <section className="card" style={{ marginBottom: "1rem" }}>
        <h2 style={{ marginTop: 0, fontSize: "1.1rem" }}>1. 本票 / 拆单腿</h2>
        <p className="muted">
          例：订单 <code>EF-C26079-C04-36460</code>，腿 <code>C26079-A</code>
          。识别用文件名 + PDF 文本流；截图不做 OCR，空项请手填。
        </p>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "0.75rem",
            maxWidth: 640,
          }}
        >
          <label>
            订单号
            <input
              type="text"
              value={orderCode}
              onChange={(e) => setOrderCode(e.target.value)}
            />
          </label>
          <label>
            拆单腿 ID
            <input
              type="text"
              value={splitLegId}
              onChange={(e) => setSplitLegId(e.target.value)}
            />
          </label>
        </div>
      </section>

      <section className="card" style={{ marginBottom: "1rem" }}>
        <h2 style={{ marginTop: 0, fontSize: "1.1rem" }}>2. 上传外箱贴 / 截图并识别</h2>
        <form
          onSubmit={(e) => recognize(e, false)}
          style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", alignItems: "end" }}
        >
          <label>
            文件（可多选）
            <br />
            <input
              type="file"
              multiple
              accept=".pdf,image/png,image/jpeg,image/webp,.png,.jpg,.jpeg"
              onChange={(e) => setFiles(e.target.files)}
            />
          </label>
          <button className="btn btn-secondary" type="submit" disabled={loading}>
            仅识别预览
          </button>
          <button
            className="btn"
            type="button"
            disabled={loading}
            onClick={(e) => recognize(e as unknown as FormEvent, true)}
          >
            识别并保存仓头
          </button>
        </form>
        {error ? <p className="status-blocked">{error}</p> : null}
        {message ? <p className="status-doing">{message}</p> : null}

        {preview.length > 0 ? (
          <div style={{ overflowX: "auto", marginTop: "1rem" }}>
            <p className="muted">预览（未入库）</p>
            <table className="data-table">
              <thead>
                <tr>
                  <th>文件</th>
                  <th>仓码</th>
                  <th>FBA 号</th>
                  <th>reference</th>
                  <th>箱数</th>
                  <th>备注</th>
                </tr>
              </thead>
              <tbody>
                {preview.map((r, i) => (
                  <tr key={`${r.source_filename}-${i}`}>
                    <td>
                      {r.preview_data_url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={r.preview_data_url}
                          alt=""
                          style={{ maxWidth: 80, maxHeight: 60, display: "block" }}
                        />
                      ) : null}
                      <small>{r.source_filename}</small>
                    </td>
                    <td>{r.warehouse_code || "—"}</td>
                    <td>{r.fba_shipment_id || "—"}</td>
                    <td>{r.reference_id || "—"}</td>
                    <td>{r.carton_count ?? "—"}</td>
                    <td>
                      <small>{r.recognize_notes}</small>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>

      <section className="card">
        <h2 style={{ marginTop: 0, fontSize: "1.1rem" }}>3. 填写追踪编码（识别后由你输入）</h2>
        <p className="muted">
          每仓一行：可改正仓码 / FBA / 地址；<strong>追踪编码必填后点保存</strong>
          。与 FBA 单号、仓库代码一一对应。
        </p>
        <button
          className="btn btn-secondary"
          type="button"
          onClick={() => void loadSaved()}
          disabled={loading}
        >
          刷新列表
        </button>
        {saved.length === 0 ? (
          <p className="muted" style={{ marginTop: "1rem" }}>
            尚无已保存仓头。请先上传识别并保存。
          </p>
        ) : (
          <div style={{ overflowX: "auto", marginTop: "1rem" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>仓码</th>
                  <th>FBA 号</th>
                  <th>reference</th>
                  <th>箱/条</th>
                  <th>仓址</th>
                  <th>追踪编码</th>
                  <th>状态</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {saved.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <input
                        type="text"
                        value={r.warehouse_code ?? ""}
                        onChange={(e) =>
                          patchSaved(r.id!, { warehouse_code: e.target.value })
                        }
                        style={{ maxWidth: 88 }}
                      />
                    </td>
                    <td>
                      <input
                        type="text"
                        value={r.fba_shipment_id ?? ""}
                        onChange={(e) =>
                          patchSaved(r.id!, { fba_shipment_id: e.target.value })
                        }
                        style={{ maxWidth: 140 }}
                      />
                    </td>
                    <td>
                      <input
                        type="text"
                        value={r.reference_id ?? ""}
                        onChange={(e) =>
                          patchSaved(r.id!, { reference_id: e.target.value })
                        }
                        style={{ maxWidth: 120 }}
                      />
                    </td>
                    <td>
                      <input
                        type="text"
                        value={r.carton_count ?? ""}
                        onChange={(e) =>
                          patchSaved(r.id!, {
                            carton_count: e.target.value
                              ? Number(e.target.value)
                              : null,
                          })
                        }
                        style={{ maxWidth: 48 }}
                        placeholder="箱"
                      />
                      /
                      <input
                        type="text"
                        value={r.strip_count ?? ""}
                        onChange={(e) =>
                          patchSaved(r.id!, {
                            strip_count: e.target.value
                              ? Number(e.target.value)
                              : null,
                          })
                        }
                        style={{ maxWidth: 56 }}
                        placeholder="条"
                      />
                    </td>
                    <td>
                      <input
                        type="text"
                        value={r.warehouse_address ?? ""}
                        onChange={(e) =>
                          patchSaved(r.id!, { warehouse_address: e.target.value })
                        }
                        style={{ maxWidth: 160 }}
                      />
                    </td>
                    <td>
                      <input
                        type="text"
                        value={r.tracking_id ?? ""}
                        onChange={(e) =>
                          patchSaved(r.id!, { tracking_id: e.target.value })
                        }
                        placeholder="手填追踪码"
                        style={{ maxWidth: 160, borderColor: "#1a4f8b" }}
                      />
                    </td>
                    <td>
                      <small>{r.status}</small>
                    </td>
                    <td>
                      <button
                        className="btn"
                        type="button"
                        disabled={loading}
                        onClick={() => void saveTracking(r)}
                      >
                        保存
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
