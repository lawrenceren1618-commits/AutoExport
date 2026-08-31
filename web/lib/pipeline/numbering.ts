import fs from "fs";
import path from "path";

export type EntityCode = "C04" | "C07";

export type PlanLine = {
  size?: string;
  color?: string;
  strips_per_pack?: number;
  qty_cartons: number;
  strips_per_carton?: number;
  qty_strips?: number;
  fnsku?: string;
};

type OrderSeqFile = {
  baselines: Record<
    string,
    { last_allocated_short: string; next_short: string; note?: string }
  >;
};

type OutboundSeqFile = {
  year_abbr: Record<string, string>;
  baselines: Record<
    string,
    {
      C04_next?: string;
      C07_next?: string;
      C04_last?: string;
      C07_last?: string;
    }
  >;
};

const memOrderShort: Record<string, string> = {};
const memOutboundNext: Record<string, { C04: number; C07: number }> = {};

function repoRoot(): string {
  // web/ runs with cwd=web or monorepo root
  const candidates = [
    path.join(process.cwd(), "Scripts"),
    path.join(process.cwd(), "..", "Scripts"),
  ];
  for (const c of candidates) {
    if (fs.existsSync(path.join(c, "order_code_seq.json"))) return path.dirname(c);
  }
  return path.join(process.cwd(), "..");
}

function readJson<T>(rel: string, fallback: T): T {
  try {
    const p = path.join(repoRoot(), rel);
    return JSON.parse(fs.readFileSync(p, "utf8")) as T;
  } catch {
    return fallback;
  }
}

function writeJson(rel: string, data: unknown): boolean {
  try {
    const p = path.join(repoRoot(), rel);
    fs.writeFileSync(p, JSON.stringify(data, null, 2) + "\n", "utf8");
    return true;
  } catch {
    return false;
  }
}

function yearKey(d = new Date()): string {
  return String(d.getFullYear());
}

function yyOf(year: string): string {
  return year.slice(2);
}

/** Parse C26080 → { yy:26, nnn:80 } */
export function parseOrderShort(short: string): { yy: number; nnn: number } | null {
  const m = /^C(\d{2})(\d{3})$/.exec(short.trim());
  if (!m) return null;
  return { yy: Number(m[1]), nnn: Number(m[2]) };
}

export function formatOrderShort(yy: number, nnn: number): string {
  return `C${String(yy).padStart(2, "0")}${String(nnn).padStart(3, "0")}`;
}

export function sumPlanStrips(lines: PlanLine[]): number {
  return lines.reduce((acc, line) => {
    if (line.qty_strips != null && Number.isFinite(line.qty_strips)) {
      return acc + Number(line.qty_strips);
    }
    const per =
      line.strips_per_carton != null
        ? Number(line.strips_per_carton)
        : line.strips_per_pack != null
          ? Number(line.strips_per_pack)
          : 0;
    return acc + Number(line.qty_cartons || 0) * per;
  }, 0);
}

export function buildOrderCode(input: {
  short: string;
  entity_code: EntityCode;
  total_strips: number;
}): string {
  return `EF-${input.short}-${input.entity_code}-${input.total_strips}`;
}

export function buildProjectCode(input: {
  order_code: string;
  entity_code: EntityCode;
  ship_date: string;
  total_strips: number;
}): string {
  const ymd = input.ship_date.replace(/-/g, "");
  return `${input.order_code}_${input.entity_code}_${ymd}_${input.total_strips}`;
}

/** Allocate next EF short CyyNNN (calendar year, shared across stores). */
export function allocateOrderShort(at = new Date()): {
  short: string;
  persisted: boolean;
} {
  const year = yearKey(at);
  const yy = Number(yyOf(year));
  const file = readJson<OrderSeqFile>("Scripts/order_code_seq.json", {
    baselines: {
      [year]: { last_allocated_short: "C26080", next_short: "C26081" },
    },
  });

  const memKey = year;
  let next = memOrderShort[memKey];
  if (!next) {
    next = file.baselines[year]?.next_short || formatOrderShort(yy, 1);
  }
  const parsed = parseOrderShort(next) || { yy, nnn: 1 };
  const short = formatOrderShort(parsed.yy, parsed.nnn);
  const following = formatOrderShort(parsed.yy, parsed.nnn + 1);

  memOrderShort[memKey] = following;
  file.baselines[year] = {
    last_allocated_short: short,
    next_short: following,
    note: file.baselines[year]?.note,
  };
  const persisted = writeJson("Scripts/order_code_seq.json", {
    confirmed_at: "2026-07-27",
    rule: "EF long = EF-{short}-{entity}-{total_strips}",
    short_pattern: "C{YY}{NNN}",
    year_abbr: { "2026": "26", "2027": "27" },
    short_increments_per_calendar_year: true,
    note: "订单短码按自然年全局递增（跨 C04/C07 共用）；尾数=计划总条数",
    baselines: file.baselines,
  });

  return { short, persisted };
}

/** Allocate outbound short {store}-{YY}{NN} */
export function allocateOutboundShort(
  entity: EntityCode,
  at = new Date(),
): { short: string; persisted: boolean } {
  const year = yearKey(at);
  const yy = yyOf(year);
  const file = readJson<OutboundSeqFile>("Scripts/outbound_short_seq.json", {
    year_abbr: { "2026": "26", "2027": "27" },
    baselines: {
      [year]: { C04_next: "C04-2617", C07_next: "C07-2608" },
    },
  });

  if (!memOutboundNext[year]) {
    const b = file.baselines[year] || {};
    const parseNN = (s: string | undefined, fallback: number) => {
      const m = s ? /-(\d{2})(\d{2})$/.exec(s) : null;
      return m ? Number(m[2]) : fallback;
    };
    memOutboundNext[year] = {
      C04: parseNN(b.C04_next, 17),
      C07: parseNN(b.C07_next, 8),
    };
  }

  const nn = memOutboundNext[year][entity];
  const short = `${entity}-${yy}${String(nn).padStart(2, "0")}`;
  memOutboundNext[year][entity] = nn + 1;

  const nextC04 = `C04-${yy}${String(memOutboundNext[year].C04).padStart(2, "0")}`;
  const nextC07 = `C07-${yy}${String(memOutboundNext[year].C07).padStart(2, "0")}`;
  const lastC04 =
    entity === "C04" ? short : file.baselines[year]?.C04_last || `C04-${yy}16`;
  const lastC07 =
    entity === "C07" ? short : file.baselines[year]?.C07_last || `C07-${yy}07`;

  file.baselines[year] = {
    C04_last: entity === "C04" ? short : lastC04,
    C07_last: entity === "C07" ? short : lastC07,
    C04_next: nextC04,
    C07_next: nextC07,
  };

  const persisted = writeJson("Scripts/outbound_short_seq.json", {
    confirmed_at: "2026-07-27",
    rule: "outbound_short = {store}-{YY}{NN}",
    year_abbr: file.year_abbr,
    U_in_filename: "USA",
    filename_pattern: "{short}-U-{delivery_yyyy.M.d}.xlsx",
    cell_customer_order_no: "short only (no U, no date)",
    ship_date: "order_delivery_date (交货日期; not 下单日期)",
    leave_empty_columns: ["所属仓库"],
    belonging_order: "order short Cxxxxx",
    sales_person_default: "任胜国",
    detail_source: "order_upper_summary_size_color",
    layout: {
      row_height: "uniform 37; auto-extend",
      merges: "A/B/F/I follow C04-2615",
    },
    baselines: file.baselines,
  });

  return { short, persisted };
}

export function allocateJobCodes(input: {
  entity_code: EntityCode;
  ship_date: string;
  order_date?: string;
  total_strips: number;
  lines?: PlanLine[];
}): {
  order_short: string;
  order_code: string;
  outbound_short: string;
  project_code: string;
  total_strips: number;
  seq_persisted: boolean;
} {
  const strips =
    input.total_strips > 0
      ? input.total_strips
      : input.lines
        ? sumPlanStrips(input.lines)
        : 0;
  if (strips <= 0) {
    throw new Error("total_strips required (or plan lines with carton×strips)");
  }
  const { short, persisted: p1 } = allocateOrderShort(
    input.order_date ? new Date(input.order_date) : new Date(),
  );
  const order_code = buildOrderCode({
    short,
    entity_code: input.entity_code,
    total_strips: strips,
  });
  const { short: outbound_short, persisted: p2 } = allocateOutboundShort(
    input.entity_code,
    input.ship_date ? new Date(input.ship_date) : new Date(),
  );
  const project_code = buildProjectCode({
    order_code,
    entity_code: input.entity_code,
    ship_date: input.ship_date,
    total_strips: strips,
  });
  return {
    order_short: short,
    order_code,
    outbound_short,
    project_code,
    total_strips: strips,
    seq_persisted: p1 && p2,
  };
}
