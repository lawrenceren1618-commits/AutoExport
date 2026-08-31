/** 纯展示辅助（无 fs，可供 client 组件引用） */

export function orderShortFromCode(orderCode: string): string {
  const m = /EF-(C\d{5})/i.exec(orderCode);
  if (m) return m[1].toUpperCase();
  const bare = /^(C\d{5})\b/i.exec(orderCode.trim());
  if (bare) return bare[1].toUpperCase();
  return orderCode.length > 12 ? `${orderCode.slice(0, 10)}…` : orderCode;
}

export function formatLeafLabel(e: {
  order_code: string;
  order_short?: string;
  batch_label: string;
  carton_count: number | null;
}): string {
  const short = e.order_short || orderShortFromCode(e.order_code);
  const boxes = e.carton_count == null ? "箱数待填" : `${e.carton_count}箱`;
  return `${short} · ${e.batch_label} · ${boxes}`;
}
