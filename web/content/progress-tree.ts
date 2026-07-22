export type ProgressStatus = "todo" | "doing" | "done" | "blocked";

export type ProgressNode = {
  id: string;
  parentId: string | null;
  title: string;
  status: ProgressStatus;
  module: string;
  nextAction: string;
  sort: number;
};

/**
 * 后台目标树（仅 /admin/progress）。
 * done = 已完成（绿）；todo/doing/blocked = 未完成（黄）。
 * 状态按当前真实进度维护。
 */
export const PROGRESS_TREE: ProgressNode[] = [
  {
    id: "root",
    parentId: null,
    title: "AutoExport 总目标：订单→出货→货代→(FBA仓)→报关 可追溯可终审",
    status: "doing",
    module: "Gate",
    nextAction: "P0 基建已完成；推进 P1 人工总表 H01 入库",
    sort: 0,
  },

  // —— P0 基建 ——
  {
    id: "P0",
    parentId: "root",
    title: "P0 基建（文件夹 / Git / SSH / 云端）",
    status: "done",
    module: "P0",
    nextAction: "基建完成；进入 P1 总表入库",
    sort: 10,
  },
  {
    id: "P0-0",
    parentId: "P0",
    title: "总文件夹更名为 AutoExport；提交人保持 Office CP",
    status: "done",
    module: "P0",
    nextAction: "本机路径 D:\\.cursor\\Cursor-projects\\AutoExport；旧名已废弃",
    sort: 10.5,
  },
  {
    id: "P0-1a",
    parentId: "P0",
    title: "本机 git 身份 Office CP + 办公室 SSH 密钥",
    status: "done",
    module: "P0",
    nextAction: "—",
    sort: 11,
  },
  {
    id: "P0-1b",
    parentId: "P0",
    title: "GitHub 已添加办公室公钥；ssh -T github.com-office-cp 通过",
    status: "done",
    module: "P0",
    nextAction: "—",
    sort: 11.5,
  },
  {
    id: "P0-1c",
    parentId: "P0",
    title: "GitHub 仓库 AutoExport 创建 + 首次 push",
    status: "done",
    module: "P0",
    nextAction: "已推送到 origin/main",
    sort: 12,
  },
  {
    id: "P0-2",
    parentId: "P0",
    title: "Supabase 新建项目 AutoExport + 执行 migration",
    status: "done",
    module: "P0",
    nextAction: "本机试连通过（progress_nodes 可读）",
    sort: 13,
  },
  {
    id: "P0-3",
    parentId: "P0",
    title: "Vercel 绑定 AutoExport，Root=web，环境变量隔离",
    status: "done",
    module: "P0",
    nextAction: "已部署；用线上 /admin/login 验证",
    sort: 14,
  },
  {
    id: "P0-4",
    parentId: "P0",
    title: "本地 web 脚手架（后台登录 / 目标树 / 总表导入页）",
    status: "done",
    module: "P0",
    nextAction: "本地与线上均可访问",
    sort: 15,
  },
  {
    id: "P0-5",
    parentId: "P0",
    title: "后台 admin 口令（web/.env.local · OFCE_ADMIN_PASSWORD）",
    status: "done",
    module: "P0",
    nextAction: "已设置；Vercel 需同步同名变量",
    sort: 16,
  },

  // —— P1 沉淀 ——
  {
    id: "P1",
    parentId: "root",
    title: "P1 沉淀与总表（M0）",
    status: "doing",
    module: "M0",
    nextAction: "上传人工总表并 H01 确认入库",
    sort: 20,
  },
  {
    id: "P1-0",
    parentId: "P1",
    title: "三分法目录 + 人工总表目录 + 握手/闸门规则文档",
    status: "done",
    module: "M0",
    nextAction: "—",
    sort: 20.5,
  },
  {
    id: "P1-1",
    parentId: "P1",
    title: "上传/导入人工总表 → 确认入库（H01）",
    status: "todo",
    module: "M0",
    nextAction: "文件放 00_Master_Reference 或 /admin/master-import",
    sort: 21,
  },
  {
    id: "P1-2",
    parentId: "P1",
    title: "对照 API / 03_cross_validate 云端化",
    status: "todo",
    module: "Gate",
    nextAction: "实现 /api/cross-check",
    sort: 22,
  },

  // —— P2 M1 ——
  {
    id: "P2",
    parentId: "root",
    title: "P2 M1 订单出货（块 B）",
    status: "doing",
    module: "M1",
    nextAction: "确认装箱冲突 + 上传/确认人工总表后出首单",
    sort: 30,
  },
  {
    id: "P2-1",
    parentId: "P2",
    title: "订单/出库模板列映射确认",
    status: "doing",
    module: "M1",
    nextAction: "固定中文模板已建模（C26079 版式）；空白骨架 Templates/order_blank_zh.xlsx",
    sort: 31,
  },
  {
    id: "P2-2",
    parentId: "P2",
    title: "生成订单/出货草稿",
    status: "doing",
    module: "M1",
    nextAction: "Scripts/05_generate_order.py + Scripts/m1/*；待总表入库与冲突确认",
    sort: 32,
  },
  {
    id: "P2-3",
    parentId: "P2",
    title: "装箱规格变更汇报流",
    status: "doing",
    module: "M1",
    nextAction: "--scan 已产出冲突报告；须使用者确认后写入",
    sort: 33,
  },

  // —— P3 ——
  {
    id: "P3",
    parentId: "root",
    title: "P3 M4+M2 货代（仓后）",
    status: "doing",
    module: "M2",
    nextAction: "后台 /admin/fba-track 上传仓头并填追踪码",
    sort: 40,
  },
  {
    id: "P3-1",
    parentId: "P3",
    title: "FBA 仓头识别 + 追踪编码（H42）",
    status: "doing",
    module: "M4",
    nextAction: "Vercel 后台 /admin/fba-track；Supabase 执行 fba_warehouse_headers 迁移",
    sort: 41,
  },
  {
    id: "P3-2",
    parentId: "P3",
    title: "生成货代下单草稿",
    status: "todo",
    module: "M2",
    nextAction: "握手 H12+H42；先上传货代模板到 02_Freight_Forwarder",
    sort: 42,
  },

  // —— P4 ——
  {
    id: "P4",
    parentId: "root",
    title: "P4 M3 报关（延期可）",
    status: "blocked",
    module: "M3",
    nextAction: "报关模板确认后再做",
    sort: 50,
  },
  {
    id: "P4-1",
    parentId: "P4",
    title: "模板确认后生成 + 对照（H13）",
    status: "todo",
    module: "M3",
    nextAction: "上传模板到 03_Customs",
    sort: 51,
  },

  // —— P5 ——
  {
    id: "P5",
    parentId: "root",
    title: "P5 Gate 终审导出",
    status: "todo",
    module: "Gate",
    nextAction: "对照通过后写最终件",
    sort: 60,
  },
  {
    id: "P5-0",
    parentId: "P5",
    title: "交叉对照闸门规则 + 03_cross_validate 骨架",
    status: "done",
    module: "Gate",
    nextAction: "待接真实草稿与沉淀库",
    sort: 60.5,
  },
  {
    id: "P5-1",
    parentId: "P5",
    title: "通过后写入最终件 / 存储（HX）",
    status: "todo",
    module: "Gate",
    nextAction: "对照通过才写 3_Output_Final / 云端存储",
    sort: 61,
  },
];

export function buildProgressForest(nodes: ProgressNode[]) {
  const byParent = new Map<string | null, ProgressNode[]>();
  for (const n of [...nodes].sort((a, b) => a.sort - b.sort)) {
    const key = n.parentId;
    const list = byParent.get(key) ?? [];
    list.push(n);
    byParent.set(key, list);
  }
  return byParent;
}

export function summarizeProgress(nodes: ProgressNode[]) {
  const leaves = nodes.filter((n) => !nodes.some((c) => c.parentId === n.id));
  const done = leaves.filter((n) => n.status === "done").length;
  const pending = leaves.filter((n) => n.status !== "done").length;
  return { done, pending, total: leaves.length };
}
