import { HANDSHAKES, type EntityCode, brandForEntity } from "./schema";

export type HandshakeId = keyof typeof HANDSHAKES;

export type HandshakeResult = {
  id: HandshakeId;
  ok: boolean;
  message: string;
  payload?: Record<string, unknown>;
};

/** H12: M1 → M2 must carry brand lock matching store */
export function checkH12(input: {
  entity_code: EntityCode;
  brand?: string;
  cartons?: number;
  strips_per_carton?: number;
}): HandshakeResult {
  const expect = brandForEntity(input.entity_code);
  if (input.brand && input.brand !== expect) {
    return {
      id: "H12",
      ok: false,
      message: `品牌与店铺不符：期望 ${expect}，收到 ${input.brand}`,
      payload: input,
    };
  }
  if (input.cartons == null || input.strips_per_carton == null) {
    return {
      id: "H12",
      ok: false,
      message: "H12 缺箱数或条数/箱",
      payload: input,
    };
  }
  return { id: "H12", ok: true, message: "H12 ok", payload: input };
}

/** H42: warehouse + shipment id required for freight */
export function checkH42(input: {
  warehouse_code?: string;
  fba_shipment_id?: string;
}): HandshakeResult {
  if (!input.warehouse_code || !input.fba_shipment_id) {
    return {
      id: "H42",
      ok: false,
      message: "H42 缺仓库代码或货件号（可标待入库货件）",
      payload: input,
    };
  }
  return { id: "H42", ok: true, message: "H42 ok", payload: input };
}

/** HX: Final blocked unless user confirmed + checks passed */
export function checkHX(input: {
  checks_ok: boolean;
  gate_final: "WAIT" | "CONFIRMED" | "REJECTED";
}): HandshakeResult {
  if (!input.checks_ok) {
    return { id: "HX", ok: false, message: "交叉对照未通过，阻断 Final" };
  }
  if (input.gate_final !== "CONFIRMED") {
    return {
      id: "HX",
      ok: false,
      message: "Gate 未用户确认（WAIT），不得 Final",
    };
  }
  return { id: "HX", ok: true, message: "HX Final 允许" };
}

export function handshakeCatalog() {
  return HANDSHAKES;
}
