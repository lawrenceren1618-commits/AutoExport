"use client";

import { useRef, useState, type ClipboardEvent, type DragEvent } from "react";

type Props = {
  accept?: string;
  multiple?: boolean;
  disabled?: boolean;
  /** 主提示（框内） */
  hint?: string;
  /** 收到文件后回调（粘贴 / 拖放 / 点选） */
  onFiles: (files: File[]) => void;
};

function filesFromList(list: FileList | File[] | null | undefined): File[] {
  if (!list) return [];
  return Array.from(list).filter(Boolean);
}

function isAccepted(file: File, accept: string): boolean {
  if (!accept || accept === "*") return true;
  const tokens = accept.split(",").map((t) => t.trim().toLowerCase());
  const name = file.name.toLowerCase();
  const type = (file.type || "").toLowerCase();
  return tokens.some((t) => {
    if (t.startsWith(".")) return name.endsWith(t);
    if (t.endsWith("/*")) return type.startsWith(t.slice(0, -1));
    return type === t || name.endsWith(t);
  });
}

/**
 * 同一框：Ctrl+V 粘贴截图 / 拖放 PDF·图片 / 可选点选文件。
 * 不要求先把截图存盘再「选择文件」。
 */
export function PasteFileBox({
  accept = "image/*,.pdf,application/pdf",
  multiple = true,
  disabled = false,
  hint = "点此聚焦后 Ctrl+V 粘贴截图，或把 PDF/图片拖进此框；也可点选文件",
  onFiles,
}: Props) {
  const boxRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState(hint);
  const [dragOver, setDragOver] = useState(false);

  function emit(raw: File[]) {
    const next = raw.filter((f) => isAccepted(f, accept));
    if (!next.length) {
      setStatus("未识别到可用文件（需图片或 PDF）");
      return;
    }
    setStatus(
      next.length === 1
        ? `已加入 ${next[0].name}`
        : `已加入 ${next.length} 个文件（末：${next[next.length - 1].name}）`,
    );
    onFiles(next);
  }

  function onPaste(e: ClipboardEvent<HTMLDivElement>) {
    if (disabled) return;
    const items = e.clipboardData?.items;
    const fromItems: File[] = [];
    if (items) {
      for (const item of Array.from(items)) {
        if (item.kind !== "file") continue;
        const f = item.getAsFile();
        if (!f) continue;
        if (f.type.startsWith("image/") && (!f.name || f.name === "image.png" || f.name === "blob")) {
          const ext = f.type.includes("png")
            ? "png"
            : f.type.includes("webp")
              ? "webp"
              : "jpg";
          fromItems.push(
            new File([f], `paste_${Date.now()}_${fromItems.length}.${ext}`, {
              type: f.type,
            }),
          );
        } else {
          fromItems.push(f);
        }
      }
    }
    const fromFiles = filesFromList(e.clipboardData?.files);
    // 同一粘贴：items 与 files 常重复，只取一侧
    const merged = fromItems.length > 0 ? fromItems : fromFiles;
    if (!merged.length) {
      setStatus("剪贴板没有图片/文件，请先截图或复制 PDF 后再 Ctrl+V");
      return;
    }
    e.preventDefault();
    emit(merged);
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    if (disabled) return;
    emit(filesFromList(e.dataTransfer?.files));
  }

  return (
    <div className="paste-file-wrap">
      <div
        ref={boxRef}
        className={`paste-file-box${dragOver ? " drag" : ""}`}
        tabIndex={0}
        role="button"
        aria-disabled={disabled}
        onClick={() => {
          if (disabled) return;
          boxRef.current?.focus();
        }}
        onPaste={onPaste}
        onDragEnter={(e) => {
          e.preventDefault();
          if (!disabled) setDragOver(true);
        }}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
      >
        <p className="paste-file-status">{status}</p>
        <p className="muted paste-file-sub">
          截图：框内 Ctrl+V 即粘贴识别 · PDF：拖入此框或下方点选
        </p>
      </div>
      <div className="paste-file-actions">
        <button
          type="button"
          className="btn btn-secondary"
          disabled={disabled}
          onClick={() => inputRef.current?.click()}
        >
          点选 PDF / 图片
        </button>
        <input
          ref={inputRef}
          type="file"
          multiple={multiple}
          accept={accept}
          hidden
          disabled={disabled}
          onChange={(e) => {
            emit(filesFromList(e.target.files));
            e.target.value = "";
          }}
        />
      </div>
    </div>
  );
}
