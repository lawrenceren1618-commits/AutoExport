"use client";

import { useMemo, useState } from "react";
import type {
  ArchiveDayNode,
  ArchiveEntry,
  ArchiveMonthNode,
  ArchiveYearNode,
  ArchiveCostPendingLine,
} from "@/lib/pipeline/archive-index";
import { formatLeafLabel, orderShortFromCode } from "@/lib/pipeline/archive-display";

type Props = {
  tree: ArchiveYearNode[];
};

function monthLabel(mo: string): string {
  const n = Number(mo);
  return Number.isFinite(n) ? `${n}月` : `${mo}月`;
}

function dayLabel(d: ArchiveDayNode): string {
  const n = Number(d.day);
  return Number.isFinite(n) ? `${n}日` : d.day;
}

function CostPanel({
  entry,
  onUpdated,
}: {
  entry: ArchiveEntry;
  onUpdated: (e: ArchiveEntry) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [lines, setLines] = useState<ArchiveCostPendingLine[]>(
    entry.cost?.pending?.proposed_lines || [],
  );
  const [total, setTotal] = useState<string>(
    entry.cost?.pending?.proposed_batch_total != null
      ? String(entry.cost.pending.proposed_batch_total)
      : entry.cost?.batch_total_cost != null
        ? String(entry.cost.batch_total_cost)
        : "",
  );

  async function onUpload(file: File | null) {
    if (!file) return;
    setBusy(true);
    setMsg("识别中…");
    try {
      const fd = new FormData();
      fd.set("entry_id", entry.id);
      fd.set("file", file);
      const res = await fetch("/api/ops/archives/cost-shot", { method: "POST", body: fd });
      const data = await res.json();
      if (!data.ok) {
        setMsg(data.error || "上传失败");
        return;
      }
      onUpdated(data.entry);
      setLines(data.entry?.cost?.pending?.proposed_lines || []);
      setTotal(
        data.entry?.cost?.pending?.proposed_batch_total != null
          ? String(data.entry.cost.pending.proposed_batch_total)
          : "",
      );
      setMsg(data.message || "请核对后确认");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onConfirm() {
    setBusy(true);
    setMsg("写入中…");
    try {
      const res = await fetch("/api/ops/archives/cost-confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          entry_id: entry.id,
          confirm: true,
          batch_total_cost: Number(total),
          lines,
        }),
      });
      const data = await res.json();
      if (!data.ok) {
        setMsg(data.error || "确认失败");
        return;
      }
      onUpdated(data.entry);
      setMsg(data.message || "已确认");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="arch-cost">
      <p className="arch-cost-hint">
        单价截图优先 → 识别后须你确认 → 云端只留批次总成本，本地写规格单价。
      </p>
      <label className="arch-cost-upload">
        <span>上传单价截图</span>
        <input
          type="file"
          accept="image/*,.pdf"
          disabled={busy}
          onChange={(ev) => onUpload(ev.target.files?.[0] || null)}
        />
      </label>
      {entry.cost?.pending?.ocr_text_preview ? (
        <p className="muted arch-cost-ocr">OCR：{entry.cost.pending.ocr_text_preview}</p>
      ) : null}
      {entry.cost?.pending?.dual_compare ? (
        <p
          className={
            entry.cost.pending.dual_compare.verdict === "disagree"
              ? "arch-cost-dual arch-cost-dual-warn"
              : "arch-cost-dual muted"
          }
        >
          对照[{entry.cost.pending.dual_compare.verdict}] overlap=
          {entry.cost.pending.dual_compare.overlap_ratio} —{" "}
          {entry.cost.pending.dual_compare.note}
          {entry.cost.pending.dual_compare.verdict === "disagree" &&
          entry.cost.pending.dual_compare.secondary_preview
            ? ` · LlamaParse节选：${entry.cost.pending.dual_compare.secondary_preview}`
            : ""}
        </p>
      ) : null}
      {lines.length > 0 ? (
        <div className="arch-cost-lines">
          {lines.map((l, i) => (
            <div key={`${l.label}-${i}`} className="arch-cost-line">
              <span className="arch-cost-label" title={l.label}>
                {l.label}
              </span>
              <input
                type="number"
                step="0.01"
                className="arch-cost-input"
                value={l.unit_price ?? ""}
                disabled={busy}
                onChange={(ev) => {
                  const v = ev.target.value === "" ? null : Number(ev.target.value);
                  setLines((prev) =>
                    prev.map((x, j) => (j === i ? { ...x, unit_price: v } : x)),
                  );
                }}
              />
            </div>
          ))}
          <div className="arch-cost-line arch-cost-total">
            <span>批次总成本</span>
            <input
              type="number"
              step="0.01"
              className="arch-cost-input"
              value={total}
              disabled={busy}
              onChange={(ev) => setTotal(ev.target.value)}
            />
          </div>
          <button
            type="button"
            className="arch-cost-confirm"
            disabled={busy}
            onClick={() => void onConfirm()}
          >
            确认写入
          </button>
        </div>
      ) : null}
      {entry.cost?.status === "confirmed" && entry.cost.batch_total_cost != null ? (
        <p className="arch-cost-done">
          已确认总成本 <strong>{entry.cost.batch_total_cost}</strong>
        </p>
      ) : null}
      {msg ? <p className="muted">{msg}</p> : null}
    </div>
  );
}

function EntryRow({
  e,
  onPatched,
}: {
  e: ArchiveEntry;
  onPatched: (e: ArchiveEntry) => void;
}) {
  const [detailOpen, setDetailOpen] = useState(false);
  const [costOpen, setCostOpen] = useState(e.cost?.status === "awaiting_confirm");
  const short = e.order_short || orderShortFromCode(e.order_code);
  const details = e.spec_details || [];

  return (
    <li className="arch-leaf">
      <div className="arch-leaf-row">
        <span className="arch-leaf-main" title={e.order_code}>
          {formatLeafLabel(e)}
        </span>
        <span className="arch-leaf-meta">
          {e.entity_code}
          {e.total_strips != null ? ` · ${e.total_strips}条` : ""}
          {e.cost?.batch_total_cost != null ? ` · 成本${e.cost.batch_total_cost}` : ""}
        </span>
        <span className="arch-leaf-actions">
          <button
            type="button"
            className="arch-mini"
            onClick={() => setDetailOpen((v) => !v)}
            disabled={!details.length}
            title={details.length ? "规格箱数明细" : "无规格明细"}
          >
            详细
          </button>
          <button
            type="button"
            className="arch-mini"
            onClick={() => setCostOpen((v) => !v)}
            title="单价截图"
          >
            单价
          </button>
        </span>
      </div>
      <p className="arch-leaf-long muted" title={e.order_code}>
        {short !== e.order_code ? e.order_code : null}
        {e.fba_shipment_ids?.length
          ? ` · FBA ${e.fba_shipment_ids.slice(0, 3).join(",")}${e.fba_shipment_ids.length > 3 ? "…" : ""}`
          : ""}
      </p>
      {detailOpen && details.length ? (
        <ul className="arch-spec">
          {details.map((s, i) => (
            <li key={i}>
              <span>{s.label || [s.size, s.color].filter(Boolean).join(" ")}</span>
              <span>{s.carton_count}箱</span>
            </li>
          ))}
        </ul>
      ) : null}
      {costOpen ? (
        <CostPanel
          key={`${e.id}-${e.cost?.screenshot?.at || e.cost?.status || "none"}`}
          entry={e}
          onUpdated={onPatched}
        />
      ) : null}
    </li>
  );
}

function DayBlock({
  day,
  defaultOpen,
  onPatched,
}: {
  day: ArchiveDayNode;
  defaultOpen: boolean;
  onPatched: (e: ArchiveEntry) => void;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className={`arch-node arch-day${open ? " open" : ""}`}>
      <button
        type="button"
        className="arch-toggle"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="arch-chevron" aria-hidden />
        <span className="arch-date">{dayLabel(day)}</span>
        <span className="arch-pill">{day.date}</span>
        <span className="arch-stat">
          {day.ticket_count}票
          {day.carton_sum > 0 ? ` · ${day.carton_sum}箱` : ""}
        </span>
      </button>
      {open ? (
        <ul className="arch-leaves">
          {day.entries.map((e) => (
            <EntryRow key={e.id} e={e} onPatched={onPatched} />
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function MonthBlock({
  month,
  defaultOpen,
  onPatched,
}: {
  month: ArchiveMonthNode;
  defaultOpen: boolean;
  onPatched: (e: ArchiveEntry) => void;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className={`arch-node arch-month${open ? " open" : ""}`}>
      <button
        type="button"
        className="arch-toggle"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="arch-chevron" aria-hidden />
        <span className="arch-label">{monthLabel(month.month)}</span>
        <span className="arch-stat">
          {month.ticket_count}票
          {month.carton_sum > 0 ? ` · ${month.carton_sum}箱` : ""}
        </span>
      </button>
      {open ? (
        <div className="arch-children">
          {month.days.map((d, i) => (
            <DayBlock
              key={d.date}
              day={d}
              defaultOpen={i === 0}
              onPatched={onPatched}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function YearBlock({
  year,
  defaultOpen,
  onPatched,
}: {
  year: ArchiveYearNode;
  defaultOpen: boolean;
  onPatched: (e: ArchiveEntry) => void;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className={`arch-node arch-year${open ? " open" : ""}`}>
      <button
        type="button"
        className="arch-toggle"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="arch-chevron" aria-hidden />
        <span className="arch-year-label">{year.year}</span>
        <span className="arch-stat">
          {year.ticket_count}票
          {year.carton_sum > 0 ? ` · ${year.carton_sum}箱` : ""}
        </span>
      </button>
      {open ? (
        <div className="arch-children">
          {year.months.map((m, i) => (
            <MonthBlock
              key={m.month}
              month={m}
              defaultOpen={i === 0}
              onPatched={onPatched}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function ArchiveTree({ tree: initialTree }: Props) {
  const [tree, setTree] = useState(initialTree);
  const empty = tree.length === 0;
  const firstOpen = useMemo(() => true, []);

  function onPatched(updated: ArchiveEntry) {
    setTree((prev) =>
      prev.map((y) => ({
        ...y,
        months: y.months.map((m) => ({
          ...m,
          days: m.days.map((d) => ({
            ...d,
            entries: d.entries.map((e) => (e.id === updated.id ? updated : e)),
          })),
        })),
      })),
    );
  }

  if (empty) {
    return (
      <p className="muted arch-empty">
        尚无存档索引。Gate 确认并完成「汇总存档」后，整票会按实际交货日（优先）或订单交货日出现在此树中（含规格详细与单价入口）。
      </p>
    );
  }

  return (
    <div className="arch-tree" role="tree">
      {tree.map((y, i) => (
        <YearBlock
          key={y.year}
          year={y}
          defaultOpen={firstOpen && i === 0}
          onPatched={onPatched}
        />
      ))}
    </div>
  );
}
