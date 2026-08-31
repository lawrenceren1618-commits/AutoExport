"use client";

import { useCallback, useEffect, useRef, useState, type ClipboardEvent } from "react";
import {
  ARCHIVE_SECTION,
  INPUT_SECTIONS,
  OUTPUT_SECTIONS,
  brandForEntity,
} from "@/lib/pipeline/schema";
import { pickPrimaryStoredFile } from "@/lib/storage/pick-primary-file";

type RecogRow = {
  warehouse_code: string;
  fba_shipment_id: string;
  reference_id: string;
  carton_count: number | null;
  source_filename: string;
  recognize_notes: string;
  tracking_id?: string;
};

type StoredFile = {
  name: string;
  storage_path: string;
  backend?: string;
  sha256?: string;
  byte_size?: number;
};

type Job = {
  id: string;
  project_code: string;
  entity_code: "C04" | "C07";
  ship_date: string | null;
  status: string;
  gate_final: string;
  meta?: {
    order_code?: string;
    outbound_short?: string;
    total_strips?: number;
    phase?: string;
    uploads?: Record<string, boolean>;
    artifacts?: Record<string, { status: string; note?: string }>;
    storage_files?: Record<string, StoredFile[]>;
    batch?: { mode: string; legs?: string[] };
    carton_recognition?: {
      rows?: RecogRow[];
      tracking_id?: string;
      user_confirmed?: boolean;
    };
  };
};

type ViewId = "input" | "output";
type WaveId = "after_plan" | "trio_after_carton" | "after_inbound" | "finalize";
type PreflightIssue = { code: string; message: string; section?: string };

type EditRow = {
  warehouse_code: string;
  fba_shipment_id: string;
  reference_id: string;
  tracking_id: string;
  source_filename: string;
  recognize_notes: string;
};

type PlanLineEdit = {
  size: string;
  color: string;
  strips_per_pack: string;
  packs_per_carton: string;
  qty_cartons: string;
  fnsku: string;
  amazon_sku: string;
};

function emptyPlanLine(): PlanLineEdit {
  return {
    size: "60X102",
    color: "白色",
    strips_per_pack: "10",
    packs_per_carton: "4",
    qty_cartons: "",
    fnsku: "",
    amazon_sku: "",
  };
}

function emptyRow(): EditRow {
  return {
    warehouse_code: "",
    fba_shipment_id: "",
    reference_id: "",
    tracking_id: "",
    source_filename: "",
    recognize_notes: "",
  };
}

function isLocalTestJob(j: Job): boolean {
  const code = `${j.project_code} ${j.meta?.order_code || ""}`.toUpperCase();
  return code.includes("LOCAL-TEST");
}

export function WorkspaceClient() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [source, setSource] = useState("");
  const [dbError, setDbError] = useState("");
  const [entity, setEntity] = useState<"C04" | "C07">("C07");
  const [orderDate, setOrderDate] = useState("");
  const [shipDate, setShipDate] = useState("");
  const [actualDeliveryDate, setActualDeliveryDate] = useState("");
  const [totalStrips, setTotalStrips] = useState("");
  const [planHint, setPlanHint] = useState("");
  const [activeId, setActiveId] = useState<string | null>(null);
  const [view, setView] = useState<ViewId>("input");
  const [msg, setMsg] = useState("");
  const [issues, setIssues] = useState<PreflightIssue[]>([]);
  const [busy, setBusy] = useState(false);
  const [pasteHint, setPasteHint] = useState(
    "外箱贴仅收 PDF（已停用截图粘贴，防卡顿）",
  );
  const pasteRef = useRef<HTMLDivElement>(null);
  const [rows, setRows] = useState<EditRow[]>([emptyRow()]);
  const [planLines, setPlanLines] = useState<PlanLineEdit[]>([emptyPlanLine()]);
  const cleanedRef = useRef(false);
  const [plane, setPlane] = useState<"local" | "cloud">("local");
  const [planeLabel, setPlaneLabel] = useState("本机");
  const [syncHint, setSyncHint] = useState("");

  const refreshPlane = useCallback(async () => {
    try {
      const res = await fetch("/api/runtime/plane");
      const data = await res.json();
      if (data.ok) {
        setPlane(data.effective === "cloud" ? "cloud" : "local");
        setPlaneLabel(data.label || (data.effective === "cloud" ? "云端" : "本机"));
      }
    } catch {
      /* ignore */
    }
  }, []);

  async function setPlaneOverride(next: "local" | "cloud" | "auto") {
    setBusy(true);
    try {
      const res = await fetch(`/api/runtime/plane?set=${next}`);
      const data = await res.json();
      if (data.ok) {
        setPlane(data.effective === "cloud" ? "cloud" : "local");
        setPlaneLabel(data.label || "");
        setMsg(`执行面：${data.label}（作业中只写该面；完成后再同步）`);
      }
    } finally {
      setBusy(false);
    }
  }

  async function syncJob(action: "push" | "pull" | "status") {
    if (!activeId) {
      if (action !== "status") setMsg("请先选择作业");
      return;
    }
    if (action !== "status") setBusy(true);
    try {
      const res = await fetch(`/api/jobs/${activeId}/sync`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      const data = await res.json();
      if (action === "status") {
        setSyncHint(
          data.ok
            ? `本机文件 ${data.by_backend?.local || 0} · 云端 ${data.by_backend?.supabase || 0}` +
                (data.needs_push ? " · 可上传" : "") +
                (data.needs_pull ? " · 可拉取" : "")
            : "",
        );
        return;
      }
      if (!data.ok) {
        setMsg(data.error || data.hint || "同步失败");
        return;
      }
      if (action === "push") {
        setMsg(
          `已上传云端 ${data.pushed} 个文件` +
            (data.settle_candidates?.length
              ? `；沉淀候选 ${data.settle_candidates.length} 条（须确认入库）`
              : ""),
        );
      } else {
        setMsg(`已从云端拉取 ${data.pulled} 个文件到本机`);
      }
      await refresh();
      const st = await fetch(`/api/jobs/${activeId}/sync`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "status" }),
      });
      const sd = await st.json();
      if (sd.ok) {
        setSyncHint(
          `本机文件 ${sd.by_backend?.local || 0} · 云端 ${sd.by_backend?.supabase || 0}` +
            (sd.needs_push ? " · 可上传" : "") +
            (sd.needs_pull ? " · 可拉取" : ""),
        );
      }
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "同步失败");
    } finally {
      if (action !== "status") setBusy(false);
    }
  }

  const selectJob = useCallback((id: string | null) => {
    setActiveId(id);
    try {
      if (id) localStorage.setItem("ae_active_job_id", id);
      else localStorage.removeItem("ae_active_job_id");
    } catch {
      /* ignore */
    }
  }, []);

  const refresh = useCallback(async () => {
    const res = await fetch("/api/jobs");
    const data = await res.json();
    let list: Job[] = data.jobs || [];
    setSource(data.source || "");
    setDbError(typeof data.db_error === "string" ? data.db_error : "");

    // 一次性清掉早期本地仿真 LOCAL-TEST（不影响正式票）
    if (!cleanedRef.current) {
      const tests = list.filter(isLocalTestJob);
      if (tests.length) {
        await Promise.all(
          tests.map((j) => fetch(`/api/jobs/${j.id}`, { method: "DELETE" })),
        );
        cleanedRef.current = true;
        const res2 = await fetch("/api/jobs");
        const data2 = await res2.json();
        list = data2.jobs || [];
        setSource(data2.source || "");
        setDbError(typeof data2.db_error === "string" ? data2.db_error : "");
      } else {
        cleanedRef.current = true;
      }
    }

    const visible = list.filter((j) => !isLocalTestJob(j));
    setJobs(visible);
    setActiveId((prev) => {
      if (prev && visible.some((j) => j.id === prev)) return prev;
      let stored: string | null = null;
      try {
        stored = localStorage.getItem("ae_active_job_id");
      } catch {
        stored = null;
      }
      if (stored && visible.some((j) => j.id === stored)) return stored;
      const first = visible[0]?.id || null;
      if (first) {
        try {
          localStorage.setItem("ae_active_job_id", first);
        } catch {
          /* ignore */
        }
      }
      return first;
    });
  }, []);

  useEffect(() => {
    void refresh();
    void refreshPlane();
  }, [refresh, refreshPlane]);

  useEffect(() => {
    if (activeId) void syncJob("status");
    // eslint-disable-next-line react-hooks/exhaustive-deps -- status only when job changes
  }, [activeId]);

  const active = jobs.find((j) => j.id === activeId) || null;

  useEffect(() => {
    const src = active?.meta?.carton_recognition?.rows;
    if (!src || src.length === 0) {
      setRows([emptyRow()]);
      return;
    }
    setRows(
      src.map((r) => ({
        warehouse_code: r.warehouse_code || "",
        fba_shipment_id: r.fba_shipment_id || "",
        reference_id: r.reference_id || "",
        tracking_id: r.tracking_id || "",
        source_filename: r.source_filename || "",
        recognize_notes: r.recognize_notes || "",
      })),
    );
  }, [active?.id, active?.meta?.carton_recognition]);

  function updateRow(i: number, patch: Partial<EditRow>) {
    setRows((prev) => prev.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  }

  function addRow() {
    setRows((prev) => [...prev, emptyRow()]);
  }

  function removeRow(i: number) {
    setRows((prev) => (prev.length <= 1 ? [emptyRow()] : prev.filter((_, idx) => idx !== i)));
  }

  function updatePlanLine(i: number, patch: Partial<PlanLineEdit>) {
    setPlanLines((prev) => prev.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  }

  function addPlanLine() {
    setPlanLines((prev) => [...prev, emptyPlanLine()]);
  }

  function removePlanLine(i: number) {
    setPlanLines((prev) =>
      prev.length <= 1 ? [emptyPlanLine()] : prev.filter((_, idx) => idx !== i),
    );
  }

  async function saveManualPlan() {
    if (!activeId) {
      setMsg("请先选择或创建作业");
      return;
    }
    setBusy(true);
    setIssues([]);
    try {
      const lines = planLines.map((ln) => {
        const spp = Number(ln.strips_per_pack);
        const ppc = Number(ln.packs_per_carton);
        const cartons = Number(ln.qty_cartons);
        const spc = spp && ppc ? spp * ppc : undefined;
        return {
          size: ln.size.trim(),
          color: ln.color.trim(),
          strips_per_pack: spp || undefined,
          packs_per_carton: ppc || undefined,
          strips_per_carton: spc,
          qty_cartons: cartons || undefined,
          qty_strips: spc && cartons ? spc * cartons : undefined,
          fnsku: ln.fnsku.trim() || undefined,
          amazon_sku: ln.amazon_sku.trim() || undefined,
        };
      });
      const missing = lines.flatMap((ln, i) => {
        const errs: string[] = [];
        if (!ln.size) errs.push(`第${i + 1}行缺尺寸`);
        if (!ln.color) errs.push(`第${i + 1}行缺颜色`);
        if (!ln.strips_per_pack) errs.push(`第${i + 1}行缺条/包`);
        if (!ln.packs_per_carton) errs.push(`第${i + 1}行缺包/箱`);
        if (!ln.qty_cartons) errs.push(`第${i + 1}行缺箱数`);
        if (!ln.fnsku) errs.push(`第${i + 1}行缺 FNSKU（生成订单必填）`);
        return errs;
      });
      if (missing.length) {
        setIssues(missing.map((message) => ({ code: "manual_plan", message })));
        setMsg("手补未齐，请按列表补全");
        return;
      }
      const res = await fetch(`/api/jobs/${activeId}/patch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lines, plan_mode: "manual_lines" }),
      });
      const data = await res.json();
      if (!data.ok) {
        setMsg(data.error || "手补保存失败");
        return;
      }
      setMsg(
        `手补已保存 · 总条数 ${data.job?.meta?.total_strips ?? ""} · 可点「生成订单与产品标签包」`,
      );
      await refresh();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "手补保存失败");
    } finally {
      setBusy(false);
    }
  }

  async function createJob() {
    setBusy(true);
    setMsg("");
    setIssues([]);
    try {
      const strips = Number(totalStrips);
      if (!shipDate || !Number.isFinite(strips) || strips <= 0) {
        setMsg("请填写订单交货日与总条数");
        return;
      }
      const lines = planHint.trim()
        ? [{ qty_cartons: 1, qty_strips: strips, size: planHint.trim() }]
        : undefined;
      const res = await fetch("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          entity_code: entity,
          ship_date: shipDate,
          order_date: orderDate || undefined,
          actual_delivery_date: actualDeliveryDate || undefined,
          total_strips: strips,
          lines,
        }),
      });
      const data = await res.json();
      if (!data.ok) {
        setMsg(data.error || "创建失败");
        return;
      }
      selectJob(data.job.id);
      setMsg(
        `已创建：${data.job.meta?.order_code || data.job.project_code}` +
          (data.source === "memory"
            ? "（已写入本地作业库，跳转库务后可恢复）"
            : ""),
      );
      setTotalStrips("");
      setPlanHint("");
      setView("input");
      await refresh();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "创建失败");
    } finally {
      setBusy(false);
    }
  }

  async function uploadFile(section: string, file: File | null) {
    if (!activeId || !file) return;
    setBusy(true);
    setIssues([]);
    try {
      const fd = new FormData();
      fd.set("section", section);
      fd.set("file", file);
      const res = await fetch(`/api/jobs/${activeId}/upload`, { method: "POST", body: fd });
      const data = await res.json();
      if (!data.ok) {
        setMsg(data.error || "上传失败");
        if (data.accept) {
          setIssues([
            { code: "bad_ext", message: `允许格式：${(data.accept as string[]).join(" ")}` },
          ]);
        }
        return;
      }
      setMsg(`已登记：${data.label} · ${file.name}`);
      if (data.recognition) {
        const list = (
          Array.isArray(data.recognition) ? data.recognition : [data.recognition]
        ) as RecogRow[];
        setRows((prev) => {
          const next = [...prev];
          for (const r of list) {
            const mapped: EditRow = {
              warehouse_code: r.warehouse_code || "",
              fba_shipment_id: r.fba_shipment_id || "",
              reference_id: r.reference_id || "",
              tracking_id: r.tracking_id || "",
              source_filename: r.source_filename || file.name,
              recognize_notes: r.recognize_notes || "",
            };
            const blankIdx = next.findIndex(
              (x) => !x.warehouse_code && !x.fba_shipment_id && !x.source_filename,
            );
            if (blankIdx >= 0) next[blankIdx] = mapped;
            else next.push(mapped);
          }
          return next;
        });
      }
      await refresh();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "上传失败");
    } finally {
      setBusy(false);
    }
  }

  async function onPasteCarton(e: ClipboardEvent) {
    const items = e.clipboardData?.items;
    if (!items) return;
    const hasImage = Array.from(items).some((item) =>
      item.type.startsWith("image/"),
    );
    if (!hasImage) return;
    e.preventDefault();
    setPasteHint("已停用截图粘贴（防卡顿）。请上传 PDF 外箱贴。");
    setMsg("外箱贴仅接受 PDF；截图粘贴已关闭");
  }

  async function confirmRecognition() {
    if (!activeId) return;
    setBusy(true);
    setIssues([]);
    try {
      const res = await fetch(`/api/jobs/${activeId}/recognize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rows, confirm: true }),
      });
      const data = await res.json();
      if (!data.ok) {
        setMsg(data.error || "确认失败");
        setIssues(
          (data.issues || []).map((m: string) => ({ code: "recog", message: String(m) })),
        );
        return;
      }
      setMsg(`已确认 ${data.rows?.length || rows.length} 个仓库行，可作为三表依据`);
      await refresh();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "确认失败");
    } finally {
      setBusy(false);
    }
  }

  async function runWave(wave: WaveId) {
    if (!activeId) {
      setMsg("请先选择或创建作业");
      return;
    }
    setBusy(true);
    setIssues([]);
    try {
      const res = await fetch(`/api/jobs/${activeId}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          wave,
          confirm_gate: wave === "after_inbound" ? true : undefined,
        }),
      });
      const data = await res.json();
      if (!data.ok) {
        setMsg(data.error || "已阻断");
        setIssues((data.issues || data.preflight?.issues || []) as PreflightIssue[]);
        return;
      }
      const lines = (data.results || [])
        .map((r: { ok: boolean; message: string }) => `${r.ok ? "✓" : "✗"} ${r.message}`)
        .join(" · ");
      setView("output");
      await refresh();
      setMsg(
        (lines || "已执行") +
          " · 请在「输出」查看路径并下载（有落盘才可点下载）",
      );
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "执行失败");
    } finally {
      setBusy(false);
    }
  }

  async function confirmGateAndPack() {
    if (!activeId) return;
    setBusy(true);
    try {
      await fetch(`/api/jobs/${activeId}/gate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirm: true, checks_ok: true }),
      });
      await runWave("after_inbound");
    } finally {
      setBusy(false);
    }
  }

  async function downloadSection(sectionId: string, fileName?: string) {
    if (!activeId) {
      setMsg("请先选择作业");
      return;
    }
    setBusy(true);
    try {
      const q = new URLSearchParams({ section: sectionId });
      if (fileName) q.set("file", fileName);
      const ac = new AbortController();
      const t = window.setTimeout(() => ac.abort(), 20000);
      const res = await fetch(`/api/jobs/${activeId}/download?${q.toString()}`, {
        signal: ac.signal,
      });
      window.clearTimeout(t);
      const data = await res.json();
      if (!data.ok || !data.url) {
        setMsg(
          data.error
            ? `无法下载 ${sectionId}：${data.error}`
            : `无法下载 ${sectionId}：尚无落盘文件`,
        );
        return;
      }
      const pathHint = data.local_path
        ? `本机：${data.local_path}`
        : `存储：${data.storage_path || ""}`;
      const fileRes = await fetch(data.url as string);
      if (!fileRes.ok) {
        setMsg(`无法下载 ${sectionId}：文件接口 ${fileRes.status}`);
        return;
      }
      const blob = await fileRes.blob();
      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objectUrl;
      a.download = (data.file_name as string) || sectionId;
      a.rel = "noopener";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 30_000);
      setMsg(`已开始下载 ${data.file_name || sectionId} · ${pathHint}`);
    } catch (e) {
      const aborted = e instanceof DOMException && e.name === "AbortError";
      setMsg(
        aborted
          ? "下载超时：本地网页可能已停，请重新打开 http://localhost:3000/workspace"
          : e instanceof Error
            ? e.message
            : "下载失败",
      );
    } finally {
      setBusy(false);
    }
  }

  const meta = active?.meta;
  const uploads = meta?.uploads || {};
  const artifacts = meta?.artifacts || {};
  const storageFiles = meta?.storage_files || {};
  const recogConfirmed = Boolean(meta?.carton_recognition?.user_confirmed);

  return (
    <div className="ws">
      <header className="ws-hero">
        <p className="ws-brand">AutoExport</p>
        <h1>发货作业</h1>
        <p className="ws-lead">
          上传后须通过预检才可生成；多仓识别逐行确认。正式输出前交叉验证。
        </p>
        <div className="ws-plane" role="group" aria-label="执行面">
          <span className="ws-meta">
            执行面：<strong>{planeLabel}</strong>
            {syncHint ? ` · ${syncHint}` : ""}
          </span>
          <span className="ws-plane-actions">
            <button
              type="button"
              className={plane === "local" ? "ws-btn ws-btn-sm active" : "ws-btn ws-btn-sm"}
              disabled={busy}
              onClick={() => void setPlaneOverride("local")}
            >
              本机
            </button>
            <button
              type="button"
              className={plane === "cloud" ? "ws-btn ws-btn-sm active" : "ws-btn ws-btn-sm"}
              disabled={busy}
              onClick={() => void setPlaneOverride("cloud")}
            >
              云端
            </button>
            <button
              type="button"
              className="ws-btn ws-btn-sm"
              disabled={busy}
              onClick={() => void setPlaneOverride("auto")}
            >
              自动
            </button>
          </span>
        </div>
      </header>

      <nav className="ws-stages" aria-label="作业视图">
        <button
          type="button"
          className={view === "input" ? "ws-stage active" : "ws-stage"}
          onClick={() => setView("input")}
        >
          输入
        </button>
        <button
          type="button"
          className={view === "output" ? "ws-stage active" : "ws-stage"}
          onClick={() => setView("output")}
        >
          输出
        </button>
      </nav>

      <section className="ws-panel" aria-labelledby="new-job">
        <h2 id="new-job">新建一票（发货计划）</h2>
        <div className="ws-form ws-form-plan">
          <label>
            店铺
            <select
              value={entity}
              onChange={(e) => setEntity(e.target.value as "C04" | "C07")}
            >
              <option value="C04">C04 · {brandForEntity("C04")}</option>
              <option value="C07">C07 · {brandForEntity("C07")}</option>
            </select>
          </label>
          <label>
            下单日
            <input type="date" value={orderDate} onChange={(e) => setOrderDate(e.target.value)} />
          </label>
          <label>
            订单交货日
            <input type="date" value={shipDate} onChange={(e) => setShipDate(e.target.value)} />
          </label>
          <label>
            实际交货日
            <input
              type="date"
              value={actualDeliveryDate}
              onChange={(e) => setActualDeliveryDate(e.target.value)}
              title="可空：空则与订单交货日相同"
            />
          </label>
          <p className="ws-meta ws-span2" style={{ margin: 0 }}>
            实际交货日可空；空则按规则视为 = 订单交货日（存档树同日）。
          </p>
          <label>
            总条数
            <input
              type="number"
              min={1}
              value={totalStrips}
              onChange={(e) => setTotalStrips(e.target.value)}
            />
          </label>
          <label className="ws-span2">
            计划摘要（可选）
            <input
              value={planHint}
              onChange={(e) => setPlanHint(e.target.value)}
              placeholder="例：米白 60X126 6条装"
            />
          </label>
          <button
            type="button"
            className="ws-btn"
            disabled={busy || !shipDate || !totalStrips}
            onClick={() => void createJob()}
          >
            创建作业（自动编号）
          </button>
        </div>
        {msg ? <p className="ws-msg">{msg}</p> : null}
        {issues.length > 0 ? (
          <ul className="ws-issues">
            {issues.map((i, idx) => (
              <li key={`${i.code}-${idx}`}>{i.message}</li>
            ))}
          </ul>
        ) : null}
        {source ? (
          <p className="ws-meta">
            数据源：{source}
            {source === "memory"
              ? " · 作业已落盘到本地库（跳转库务后再回可恢复）"
              : ""}
            {dbError ? ` · DB：${dbError}` : ""}
          </p>
        ) : null}
      </section>

      <section className="ws-panel" aria-labelledby="job-list">
        <h2 id="job-list">作业列表</h2>
        {jobs.length === 0 ? (
          <p className="ws-meta">还没有作业。</p>
        ) : (
          <ul className="ws-jobs">
            {jobs.map((j) => (
              <li key={j.id}>
                <button
                  type="button"
                  className={j.id === activeId ? "ws-job active" : "ws-job"}
                  onClick={() => {
                    selectJob(j.id);
                    setView("input");
                    setMsg("");
                    setIssues([]);
                  }}
                >
                  <span className="ws-job-code">
                    {j.meta?.order_code || j.project_code}
                  </span>
                  <span className="ws-meta">
                    {j.entity_code} · Gate {j.gate_final}
                    {j.meta?.outbound_short ? ` · ${j.meta.outbound_short}` : ""}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {active ? (
        <>
          <section className="ws-panel">
            <h2>当前作业</h2>
            <p className="ws-meta">
              订单 {meta?.order_code || "—"} · 出货 {meta?.outbound_short || "—"} · 总条数{" "}
              {meta?.total_strips ?? "—"} · {meta?.phase || active.status}
            </p>
          </section>

          {view === "input" ? (
            <section className="ws-panel" aria-labelledby="in-sec">
              <h2 id="in-sec">输入</h2>
              <p className="ws-meta">
                每步生成前自动预检。多仓：每仓一行，不限数量（5～十余仓均可）。
              </p>
              <div className="ws-grid">
                {INPUT_SECTIONS.map((sec) => (
                  <div key={sec.id} className="ws-slot">
                    <h3>{sec.label}</h3>
                    <p className="ws-meta">
                      {(sec.accept as string[]).join(" ")} · ≤{sec.max_mb}MB
                      {uploads[sec.id] ? " · 已登记" : ""}
                    </p>
                    <input
                      type="file"
                      disabled={busy}
                      accept={(sec.accept as string[]).join(",")}
                      onChange={(e) =>
                        void uploadFile(sec.id, e.target.files?.[0] || null)
                      }
                    />
                    {sec.id === "carton_and_tracking" ? (
                      <div
                        ref={pasteRef}
                        className="ws-paste"
                        tabIndex={0}
                        onPaste={(e) => void onPasteCarton(e)}
                        onClick={() => pasteRef.current?.focus()}
                        role="button"
                      >
                        {pasteHint}
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>

              <div className="ws-panel ws-recog" style={{ marginTop: "1rem" }}>
                <h3>外箱贴 / PDF · 识别结果（须确认）</h3>
                <p className="ws-meta">
                  一仓一行：仓库 / 货件号 / 参考号 / 追踪码。继续上传 PDF 会追加行（已停用截图）。
                  当前 {rows.length} 行 · {recogConfirmed ? "已确认" : "未确认"}
                </p>
                <div className="ws-recog-rows">
                  {rows.map((r, i) => (
                    <div key={i} className="ws-recog-row">
                      <div className="ws-recog-head">
                        <strong>第 {i + 1} 仓</strong>
                        <span className="ws-meta">{r.source_filename || "手填"}</span>
                        <button
                          type="button"
                          className="ws-btn-text"
                          disabled={busy}
                          onClick={() => removeRow(i)}
                        >
                          删除行
                        </button>
                      </div>
                      {r.recognize_notes ? (
                        <p className="ws-meta">{r.recognize_notes}</p>
                      ) : null}
                      <div className="ws-form ws-form-plan">
                        <label>
                          仓库代码
                          <input
                            value={r.warehouse_code}
                            onChange={(e) =>
                              updateRow(i, { warehouse_code: e.target.value })
                            }
                            placeholder="如 AVP1"
                          />
                        </label>
                        <label>
                          货件号
                          <input
                            value={r.fba_shipment_id}
                            onChange={(e) =>
                              updateRow(i, { fba_shipment_id: e.target.value })
                            }
                            placeholder="FBA… / STAR…"
                          />
                        </label>
                        <label>
                          参考号
                          <input
                            value={r.reference_id}
                            onChange={(e) =>
                              updateRow(i, { reference_id: e.target.value })
                            }
                          />
                        </label>
                        <label>
                          追踪码
                          <input
                            value={r.tracking_id}
                            onChange={(e) =>
                              updateRow(i, { tracking_id: e.target.value })
                            }
                          />
                        </label>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="ws-actions" style={{ marginTop: "0.75rem" }}>
                  <button
                    type="button"
                    className="ws-btn"
                    disabled={busy}
                    onClick={addRow}
                  >
                    添加仓库行
                  </button>
                  <button
                    type="button"
                    className="ws-btn"
                    disabled={busy}
                    onClick={() => void confirmRecognition()}
                  >
                    确认全部识别结果
                  </button>
                </div>
              </div>

              <div className="ws-actions" style={{ marginTop: "1rem" }}>
                <button
                  type="button"
                  className="ws-btn"
                  disabled={busy}
                  onClick={() => void runWave("after_plan")}
                >
                  生成订单与产品标签包
                </button>
                <button
                  type="button"
                  className="ws-btn"
                  disabled={busy}
                  onClick={() => void runWave("trio_after_carton")}
                >
                  生成出货 / 货代 / 报关
                </button>
                <button
                  type="button"
                  className="ws-btn"
                  disabled={busy}
                  onClick={() => void confirmGateAndPack()}
                >
                  打包贴标包并确认 Gate
                </button>
              </div>
            </section>
          ) : (
            <section className="ws-panel" aria-labelledby="out-sec">
              <h2 id="out-sec">输出</h2>
              <p className="ws-meta" style={{ marginTop: 0 }}>
                下载优先正式件（订单 xlsx / 标签 PDF）。作业中只写当前执行面；做完后本机可「上传云端」，或「从云端拉取」到本机。
              </p>
              <div className="ws-actions" style={{ marginBottom: "0.75rem" }}>
                <button
                  type="button"
                  className="ws-btn"
                  disabled={busy || !activeId || plane !== "local"}
                  onClick={() => void syncJob("push")}
                  title="本机成品 → Supabase；沉淀仅排队"
                >
                  上传云端
                </button>
                <button
                  type="button"
                  className="ws-btn"
                  disabled={busy || !activeId || plane !== "local"}
                  onClick={() => void syncJob("pull")}
                  title="Supabase → 本机 blobs + Shipments"
                >
                  从云端拉取
                </button>
                <button
                  type="button"
                  className="ws-btn ws-btn-sm"
                  disabled={busy || !activeId}
                  onClick={() => void syncJob("status")}
                >
                  同步状态
                </button>
              </div>
              <ul className="ws-out">
                {OUTPUT_SECTIONS.map((sec) => {
                  const art = artifacts[sec.id];
                  const files = storageFiles[sec.id] || [];
                  const primary = pickPrimaryStoredFile(sec.id, files);
                  return (
                    <li key={sec.id} className="ws-out-item">
                      <div className="ws-out-head">
                        <strong>{sec.label}</strong>
                        <span className="ws-meta">
                          {art ? art.status : "未生成"}
                          {primary?.backend ? ` · ${primary.backend}` : ""}
                        </span>
                        <button
                          type="button"
                          className="ws-btn ws-btn-sm"
                          disabled={busy || !primary}
                          onClick={() =>
                            void downloadSection(sec.id, primary?.name)
                          }
                        >
                          下载
                        </button>
                      </div>
                      {primary ? (
                        <div className="ws-out-path">
                          <span className="ws-meta">文件</span> {primary.name}
                          <br />
                          <span className="ws-meta">路径</span>{" "}
                          <code>{primary.storage_path}</code>
                          {files.length > 1 ? (
                            <>
                              <br />
                              <span className="ws-meta">同区共</span> {files.length}{" "}
                              个（含草稿/清单旁注）
                            </>
                          ) : null}
                          {art?.note ? (
                            <>
                              <br />
                              <span className="ws-meta">备注</span> {art.note}
                            </>
                          ) : null}
                        </div>
                      ) : art ? (
                        <p className="ws-meta" style={{ margin: "0.35rem 0 0" }}>
                          有状态但无落盘记录
                          {art.note ? `：${art.note}` : "（可能生成失败或未写入 Storage）"}
                        </p>
                      ) : null}
                    </li>
                  );
                })}
                <li className="ws-out-item">
                  <div className="ws-out-head">
                    <strong>{ARCHIVE_SECTION.label}</strong>
                    <span className="ws-meta">
                      Gate {active.gate_final}
                      {artifacts.audit_archive
                        ? ` · ${artifacts.audit_archive.status}`
                        : ""}
                    </span>
                    <button
                      type="button"
                      className="ws-btn ws-btn-sm"
                      disabled={
                        busy || !(storageFiles.audit_archive || []).length
                      }
                      onClick={() => void downloadSection("audit_archive")}
                    >
                      下载
                    </button>
                  </div>
                  {(storageFiles.audit_archive || []).length ? (
                    <div className="ws-out-path">
                      <span className="ws-meta">路径</span>{" "}
                      <code>
                        {
                          storageFiles.audit_archive![
                            storageFiles.audit_archive!.length - 1
                          ].storage_path
                        }
                      </code>
                    </div>
                  ) : null}
                </li>
              </ul>
              <div className="ws-actions" style={{ marginTop: "1rem" }}>
                <button
                  type="button"
                  className="ws-btn"
                  disabled={busy || active.gate_final !== "CONFIRMED"}
                  onClick={() => void runWave("finalize")}
                >
                  写入汇总存档
                </button>
              </div>
            </section>
          )}
        </>
      ) : null}
    </div>
  );
}
