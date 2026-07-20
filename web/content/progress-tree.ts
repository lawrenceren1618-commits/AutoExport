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
    nextAction: "先完成 P0 云端链接，再推进业务模块",
    sort: 0,
  },

  // —— P0 基建 ——
  {
    id: "P0",
    parentId: "root",
    title: "P0 基建（文件夹 / Git / SSH / 云端）",
    status: "doing",
    module: "P0",
    nextAction: "创建 GitHub 仓库 AutoExport 并 push，再接 Supabase、Vercel",
    sort: 10,
  },
  {
    id: "P0-0",
    parentId: "P0",
    title: "总文件夹更名为 AutoExport；提交人保持 Office CP",
    status: "done",
    module: "P0",
    nextAction: "旧目录 Order_Freight_Customs_Export 确认无用后可删",
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
    status: "todo",
    module: "P0",
    nextAction: "跑 supabase/migrations/20260720000000_init_ofce.sql，填 web/.env.local",
    sort: 13,
  },
  {
    id: "P0-3",
    parentId: "P0",
    title: "Vercel 绑定 AutoExport，Root=web，环境变量隔离",
    status: "todo",
    module: "P0",
    nextAction: "Import 仓库，OFCE_ENV=office + 办公室 Supabase 密钥",
    sort: 14,
  },
  {
    id: "P0-4",
    parentId: "P0",
    title: "本地 web 脚手架（后台登录 / 目标树 / 总表导入页）",
    status: "done",
    module: "P0",
    nextAction: "npm run dev 可预览；云端部署待 P0-3",
    sort: 15,
  },
  {
    id: "P0-5",
    parentId: "P0",
    title: "后台 admin 口令（web/.env.local · OFCE_ADMIN_PASSWORD）",
    status: "done",
    module: "P0",
    nextAction: "登录 /admin/login；Vercel 需同步同名环境变量",
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
    title: "P2 M1 订单出货",
    status: "todo",
    module: "M1",
    nextAction: "确认模板列映射后生成草稿",
    sort: 30,
  },
  {
    id: "P2-1",
    parentId: "P2",
    title: "订单/出库模板列映射确认",
    status: "todo",
    module: "M1",
    nextAction: "上传模板到 01_Order_Outbound 并更新 Correspondence",
    sort: 31,
  },
  {
    id: "P2-2",
    parentId: "P2",
    title: "生成订单/出货草稿",
    status: "todo",
    module: "M1",
    nextAction: "写入 draft_documents",
    sort: 32,
  },
  {
    id: "P2-3",
    parentId: "P2",
    title: "装箱规格变更汇报流",
    status: "todo",
    module: "M1",
    nextAction: "冲突时阻断并汇报（规则已写入）",
    sort: 33,
  },

  // —— P3 ——
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
    title: "等 FBA 货件/仓库（H42）",
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
