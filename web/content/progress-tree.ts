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

/** Fallback tree when Supabase is not configured — mirrors migration seed */
export const PROGRESS_TREE: ProgressNode[] = [
  {
    id: "root",
    parentId: null,
    title: "OFCE 总目标：订单→出货→货代→(FBA仓)→报关 可追溯可终审",
    status: "doing",
    module: "Gate",
    nextAction: "按 P0→P5 推进",
    sort: 0,
  },
  {
    id: "P0",
    parentId: "root",
    title: "P0 基建",
    status: "doing",
    module: "P0",
    nextAction: "完成 GitHub / Supabase / Vercel 隔离",
    sort: 10,
  },
  {
    id: "P0-1",
    parentId: "P0",
    title: "GitHub 仓库 office-cp-ofce + 本机 git 身份",
    status: "doing",
    module: "P0",
    nextAction: "gh auth login 后创建并 push",
    sort: 11,
  },
  {
    id: "P0-2",
    parentId: "P0",
    title: "Supabase 项目 + 核心表",
    status: "todo",
    module: "P0",
    nextAction: "新建 office-cp-ofce 并执行 migration",
    sort: 12,
  },
  {
    id: "P0-3",
    parentId: "P0",
    title: "Vercel 部署 web + 环境变量隔离",
    status: "todo",
    module: "P0",
    nextAction: "Import 仓库 Root=web，填 OFCE_/Supabase 密钥",
    sort: 13,
  },
  {
    id: "P1",
    parentId: "root",
    title: "P1 沉淀与总表",
    status: "todo",
    module: "M0",
    nextAction: "上传人工总表并确认入库",
    sort: 20,
  },
  {
    id: "P1-1",
    parentId: "P1",
    title: "上传/导入人工总表 → 确认入库",
    status: "todo",
    module: "M0",
    nextAction: "放到 00_Master_Reference 或后台导入",
    sort: 21,
  },
  {
    id: "P1-2",
    parentId: "P1",
    title: "对照 API / 03_cross_validate 逻辑云端化",
    status: "todo",
    module: "Gate",
    nextAction: "实现 /api/cross-check",
    sort: 22,
  },
  {
    id: "P2",
    parentId: "root",
    title: "P2 M1 订单出货",
    status: "todo",
    module: "M1",
    nextAction: "确认模板列映射后生成草稿",
    sort: 30,
  },
  {
    id: "P2-1",
    parentId: "P2",
    title: "模板列映射确认",
    status: "todo",
    module: "M1",
    nextAction: "更新 01_Order_Outbound_Correspondence",
    sort: 31,
  },
  {
    id: "P2-2",
    parentId: "P2",
    title: "生成草稿",
    status: "todo",
    module: "M1",
    nextAction: "写入 draft_documents",
    sort: 32,
  },
  {
    id: "P2-3",
    parentId: "P2",
    title: "装箱变更汇报流",
    status: "todo",
    module: "M1",
    nextAction: "冲突时阻断并汇报",
    sort: 33,
  },
  {
    id: "P3",
    parentId: "root",
    title: "P3 M4+M2 货代（仓后）",
    status: "blocked",
    module: "M2",
    nextAction: "等待 FBA 货件/仓库信息",
    sort: 40,
  },
  {
    id: "P3-1",
    parentId: "P3",
    title: "等 FBA 货件/仓库",
    status: "blocked",
    module: "M4",
    nextAction: "创建入库货件后解除 blocked",
    sort: 41,
  },
  {
    id: "P3-2",
    parentId: "P3",
    title: "生成货代下单草稿",
    status: "todo",
    module: "M2",
    nextAction: "握手 H12+H42",
    sort: 42,
  },
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
    title: "模板确认后生成 + 对照",
    status: "todo",
    module: "M3",
    nextAction: "握手 H13",
    sort: 51,
  },
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
    id: "P5-1",
    parentId: "P5",
    title: "通过后写入最终件 / 存储",
    status: "todo",
    module: "Gate",
    nextAction: "握手 HX",
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
