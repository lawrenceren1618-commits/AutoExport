"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type HeaderRow = {
  id?: string;
  local_key?: string;
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
};

function newLocalKey(): string {
  return `draft_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function emptyDraft(note?: string): HeaderRow {
  return {
    local_key: newLocalKey(),
    status: "draft",
    warehouse_code: "",
    fba_shipment_id: "",
    tracking_id: "",
    carton_count: null,
    strip_count: null,
    source_filename: "",
    recognize_notes: note || "空行：请手填后确认保存参考",
  };
}

export function FbaTrackPanel() {
  const [orderCode, setOrderCode] = useState("");
  const [splitLegId, setSplitLegId] = useState("");
  const [queued, setQueued] = useState<File[]>([]);
  const [drafts, setDrafts] = useState<HeaderRow[]>([]);
  const [saved, setSaved] = useState<HeaderRow[]>([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

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

  async function parsePdfs(files: File[]) {
    const pdfs = files.filter(
      (f) =>
        f.name.toLowerCase().endsWith(".pdf") || f.type === "application/pdf",
    );
    if (!pdfs.length) {
      setError("仅接受 PDF（已停用截图与 OCR）");
      return;
    }
    setLoading(true);
    setError("");
    setMessage("正在从 PDF 文本层归类…");
    try {
      const fd = new FormData();
      fd.set("order_code", orderCode.trim());
      fd.set("split_leg_id", splitLegId.trim());
      for (const f of pdfs) fd.append("files", f);
      const res = await fetch("/api/fba-track", { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok && !data.rows) {
        setError(data.error ?? "解析失败");
        setMessage("");
        return;
      }
      const rows = (data.rows || []) as HeaderRow[];
      const next = rows.map((r) => ({
        ...r,
        local_key: newLocalKey(),
        status: "draft",
        strip_count: null,
        tracking_id: r.tracking_id || "",
        warehouse_code: r.warehouse_code || "",
        fba_shipment_id: r.fba_shipment_id || "",
        carton_count: r.carton_count ?? null,
      }));
      setDrafts((prev) => [...prev, ...next]);
      setQueued((prev) => [...prev, ...pdfs]);
      setMessage(
        data.note ||
          `已解析 ${next.length} 行（PDF 文本层）。有值则填入，空着请手补，再「确认保存参考」。`,
      );
      if (data.error) setError(data.error);
    } catch {
      setError("网络错误");
      setMessage("");
    } finally {
      setLoading(false);
    }
  }

  async function commitDrafts() {
    if (!drafts.length) {
      setError("没有可保存的草稿行");
      return;
    }
    setLoading(true);
    setError("");
    setMessage("保存参考中…");
    try {
      const res = await fetch("/api/fba-track", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          order_code: orderCode.trim(),
          split_leg_id: splitLegId.trim(),
          rows: drafts.map((r) => ({
            warehouse_code: r.warehouse_code,
            fba_shipment_id: r.fba_shipment_id,
            reference_id: r.reference_id || null,
            carton_count: r.carton_count,
            strip_count: null,
            source_filename: r.source_filename,
            recognize_notes: r.recognize_notes,
            tracking_id: (r.tracking_id || "").trim() || null,
            warehouse_address: r.warehouse_address || null,
          })),
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "保存失败");
        setMessage("");
        return;
      }
      setMessage(
        `已确认保存 ${data.saved ?? drafts.length} 条，作临时参考（供货代等调用）。`,
      );
      setDrafts([]);
      setQueued([]);
      await loadSaved();
    } catch {
      setError("网络错误");
      setMessage("");
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
          strip_count: null,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "保存失败");
        return;
      }
      setMessage(`已更新参考：${row.warehouse_code || row.fba_shipment_id || row.id}`);
      await loadSaved();
    } catch {
      setError("网络错误");
    } finally {
      setLoading(false);
    }
  }

  function patchDraft(key: string, patch: Partial<HeaderRow>) {
    setDrafts((prev) =>
      prev.map((r) => (r.local_key === key ? { ...r, ...patch } : r)),
    );
  }

  function patchSaved(id: string, patch: Partial<HeaderRow>) {
    setSaved((prev) => prev.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  }

  function removeDraft(key: string) {
    setDrafts((prev) => prev.filter((r) => r.local_key !== key));
  }

  function renderEditableRow(r: HeaderRow, mode: "draft" | "saved") {
    const key = mode === "draft" ? r.local_key! : r.id!;
    const patch = (p: Partial<HeaderRow>) =>
      mode === "draft" ? patchDraft(key, p) : patchSaved(key, p);

    return (
      <tr key={key}>
        <td>
          <small>{r.source_filename || "（手填）"}</small>
          {r.recognize_notes ? (
            <div>
              <small className="muted">{r.recognize_notes}</small>
            </div>
          ) : null}
        </td>
        <td>
          <input
            type="text"
            className="fba-input-wh"
            value={r.warehouse_code ?? ""}
            onChange={(e) => patch({ warehouse_code: e.target.value })}
            title={r.warehouse_code || ""}
            placeholder="可空"
          />
        </td>
        <td>
          <input
            type="text"
            className="fba-input-fba"
            value={r.fba_shipment_id ?? ""}
            onChange={(e) => patch({ fba_shipment_id: e.target.value })}
            title={r.fba_shipment_id || ""}
            placeholder="可空"
          />
        </td>
        <td>
          <input
            type="text"
            className="fba-input-carton"
            value={r.carton_count ?? ""}
            onChange={(e) =>
              patch({
                carton_count: e.target.value ? Number(e.target.value) : null,
              })
            }
            placeholder="本仓箱数"
          />
        </td>
        <td>
          <input
            type="text"
            className="fba-input-track"
            value={r.tracking_id ?? ""}
            onChange={(e) => patch({ tracking_id: e.target.value })}
            placeholder="PDF 有则填，无则补"
            title={r.tracking_id || ""}
          />
        </td>
        <td>
          {mode === "draft" ? (
            <button
              type="button"
              className="btn btn-secondary"
              disabled={loading}
              onClick={() => removeDraft(key)}
            >
              移除
            </button>
          ) : (
            <button
              className="btn"
              type="button"
              disabled={loading}
              onClick={() => void saveTracking(r)}
            >
              更新参考
            </button>
          )}
        </td>
      </tr>
    );
  }

  return (
    <div>
      <section className="card" style={{ marginBottom: "1rem" }}>
        <h2 style={{ marginTop: 0, fontSize: "1.1rem" }}>1. 本票 / 拆单腿（可后补）</h2>
        <p className="muted">
          例：<code>EF-C26079-C04-36460</code> / <code>C26079-A</code>
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
              placeholder="可空"
            />
          </label>
          <label>
            拆单腿 ID
            <input
              type="text"
              value={splitLegId}
              onChange={(e) => setSplitLegId(e.target.value)}
              placeholder="可空"
            />
          </label>
        </div>
      </section>

      <section className="card" style={{ marginBottom: "1rem" }}>
        <h2 style={{ marginTop: 0, fontSize: "1.1rem" }}>2. 上传 PDF（仅文本层，无 OCR）</h2>
        <p className="muted" style={{ marginTop: 0 }}>
          只接受 <strong>PDF</strong>。能从文本层抽到的仓码 / FBA / 本仓箱数 / 追踪会填入；
          抽不到则<strong>空置</strong>，由你补充。已去掉截图与 OCR，避免卡顿。
        </p>
        <div className="paste-file-actions">
          <button
            type="button"
            className="btn btn-secondary"
            disabled={loading}
            onClick={() => inputRef.current?.click()}
          >
            选择 PDF
          </button>
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,application/pdf"
            multiple
            hidden
            disabled={loading}
            onChange={(e) => {
              const list = e.target.files ? Array.from(e.target.files) : [];
              e.target.value = "";
              if (list.length) void parsePdfs(list);
            }}
          />
          <button
            type="button"
            className="btn btn-secondary"
            disabled={loading}
            onClick={() => setDrafts((prev) => [...prev, emptyDraft()])}
          >
            加空行手填
          </button>
          <button
            className="btn"
            type="button"
            disabled={loading || drafts.length === 0}
            onClick={() => void commitDrafts()}
          >
            确认保存参考（{drafts.length} 条）
          </button>
        </div>
        {queued.length > 0 ? (
          <p className="muted" style={{ marginTop: "0.65rem" }}>
            本会话已解析 PDF {queued.length} 个
          </p>
        ) : null}
        {error ? <p className="status-blocked">{error}</p> : null}
        {message ? <p className="status-doing">{message}</p> : null}
      </section>

      <section className="card">
        <h2 style={{ marginTop: 0, fontSize: "1.1rem" }}>3. 结果 → 确认保存参考</h2>
        <p className="muted">
          箱数 = <strong>每仓箱数</strong>。追踪：PDF 有则填，无则空着补。
          「确认保存参考」= 临时存储供货代等调用。
        </p>
        <button
          className="btn btn-secondary"
          type="button"
          onClick={() => void loadSaved()}
          disabled={loading}
        >
          刷新已存参考
        </button>

        {drafts.length === 0 && saved.length === 0 ? (
          <p className="muted" style={{ marginTop: "1rem" }}>
            尚无行。请上传 PDF，或点「加空行手填」。
          </p>
        ) : (
          <div style={{ overflowX: "auto", marginTop: "1rem" }}>
            <table className="data-table fba-track-table">
              <thead>
                <tr>
                  <th>来源</th>
                  <th>仓码</th>
                  <th>FBA 号</th>
                  <th>本仓箱数</th>
                  <th>追踪编码</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {drafts.map((r) => renderEditableRow(r, "draft"))}
                {saved.map((r) => renderEditableRow(r, "saved"))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
