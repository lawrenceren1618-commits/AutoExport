-- office-cp-ofce — Supabase schema (run in SQL Editor or via supabase db push)
-- Project name must be independent from home-PC Supabase projects.

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- Settled knowledge (沉淀库)
-- ---------------------------------------------------------------------------

create table if not exists settled_products (
  id uuid primary key default gen_random_uuid(),
  sku_key text not null,
  brand text not null,
  entity_code text not null check (entity_code in ('C04', 'C07')),
  color text,
  size text,
  gram_weight text,
  confirmed_order_date date,
  source text not null check (source in ('document', 'master_table', 'manual')) default 'manual',
  confirmed_by_user boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (sku_key, brand, entity_code)
);

create table if not exists settled_packing (
  id uuid primary key default gen_random_uuid(),
  product_key text not null,
  brand text not null,
  entity_code text not null check (entity_code in ('C04', 'C07')),
  strips_per_carton numeric,
  packs_per_carton numeric,
  carton_size_cm text,
  gross_kg numeric,
  net_kg numeric,
  volume_cbm numeric,
  effective_order_date date,
  source text not null check (source in ('document', 'master_table', 'manual')) default 'manual',
  confirmed_by_user boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists settled_packing_lookup_idx
  on settled_packing (product_key, brand, entity_code, effective_order_date desc);

create table if not exists settled_fnsku (
  id uuid primary key default gen_random_uuid(),
  fnsku text not null,
  entity_code text not null check (entity_code in ('C04', 'C07')),
  brand text not null,
  color text,
  size text,
  amazon_store_key text,
  source text not null check (source in ('document', 'master_table', 'manual')) default 'manual',
  confirmed_by_user boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (fnsku, entity_code)
);

create table if not exists master_table_imports (
  id uuid primary key default gen_random_uuid(),
  file_name text not null,
  row_count int not null default 0,
  confirmed_at timestamptz,
  notes text,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Drafts & final gate
-- ---------------------------------------------------------------------------

create table if not exists draft_documents (
  id uuid primary key default gen_random_uuid(),
  batch_id text not null,
  doc_type text not null check (doc_type in ('order', 'outbound', 'freight', 'customs')),
  payload jsonb not null default '{}'::jsonb,
  status text not null check (status in ('draft', 'cross_check_failed', 'ready', 'finalized')) default 'draft',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists draft_documents_batch_idx on draft_documents (batch_id, doc_type);

create table if not exists cross_check_logs (
  id uuid primary key default gen_random_uuid(),
  batch_id text not null,
  passed boolean not null,
  report jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Admin progress tree (后台目标树)
-- ---------------------------------------------------------------------------

create table if not exists progress_nodes (
  id text primary key,
  parent_id text references progress_nodes (id) on delete cascade,
  title text not null,
  status text not null check (status in ('todo', 'doing', 'done', 'blocked')) default 'todo',
  module text not null,
  next_action text,
  sort int not null default 0,
  updated_at timestamptz not null default now()
);

-- Seed tree (idempotent upsert)
insert into progress_nodes (id, parent_id, title, status, module, next_action, sort) values
  ('root', null, 'OFCE 总目标：订单→出货→货代→(FBA仓)→报关 可追溯可终审', 'doing', 'Gate', '按 P0→P5 推进', 0),
  ('P0', 'root', 'P0 基建', 'doing', 'P0', '完成 GitHub / Supabase / Vercel 隔离', 10),
  ('P0-1', 'P0', 'GitHub 仓库 office-cp-ofce + 本机 git 身份', 'doing', 'P0', 'gh auth login 后创建并 push', 11),
  ('P0-2', 'P0', 'Supabase 项目 + 核心表', 'todo', 'P0', '在控制台新建 office-cp-ofce 并执行 migration', 12),
  ('P0-3', 'P0', 'Vercel 部署 web + 环境变量隔离', 'todo', 'P0', 'Import 仓库 Root=web，填 OFCE_/Supabase 密钥', 13),
  ('P1', 'root', 'P1 沉淀与总表', 'todo', 'M0', '上传人工总表并确认入库', 20),
  ('P1-1', 'P1', '上传/导入人工总表 → 确认入库', 'todo', 'M0', '放到 00_Master_Reference 或后台导入', 21),
  ('P1-2', 'P1', '对照 API / 03_cross_validate 逻辑云端化', 'todo', 'Gate', '实现 /api/cross-check', 22),
  ('P2', 'root', 'P2 M1 订单出货', 'todo', 'M1', '确认模板列映射后生成草稿', 30),
  ('P2-1', 'P2', '模板列映射确认', 'todo', 'M1', '更新 01_Order_Outbound_Correspondence', 31),
  ('P2-2', 'P2', '生成草稿', 'todo', 'M1', '写入 draft_documents', 32),
  ('P2-3', 'P2', '装箱变更汇报流', 'todo', 'M1', '冲突时阻断并汇报', 33),
  ('P3', 'root', 'P3 M4+M2 货代（仓后）', 'blocked', 'M2', '等待 FBA 货件/仓库信息', 40),
  ('P3-1', 'P3', '等 FBA 货件/仓库', 'blocked', 'M4', '创建入库货件后解除 blocked', 41),
  ('P3-2', 'P3', '生成货代下单草稿', 'todo', 'M2', '握手 H12+H42', 42),
  ('P4', 'root', 'P4 M3 报关（延期可）', 'blocked', 'M3', '报关模板确认后再做', 50),
  ('P4-1', 'P4', '模板确认后生成 + 对照', 'todo', 'M3', '握手 H13', 51),
  ('P5', 'root', 'P5 Gate 终审导出', 'todo', 'Gate', '对照通过后写最终件', 60),
  ('P5-1', 'P5', '通过后写入最终件 / 存储', 'todo', 'Gate', '握手 HX', 61)
on conflict (id) do update set
  title = excluded.title,
  module = excluded.module,
  next_action = excluded.next_action,
  sort = excluded.sort,
  updated_at = now();

-- RLS: enable; service role bypasses. Anon read of progress for admin UI after auth later.
alter table settled_products enable row level security;
alter table settled_packing enable row level security;
alter table settled_fnsku enable row level security;
alter table master_table_imports enable row level security;
alter table draft_documents enable row level security;
alter table cross_check_logs enable row level security;
alter table progress_nodes enable row level security;

-- Dev-friendly policies: authenticated read/write (tighten in production)
do $$ begin
  create policy progress_nodes_select on progress_nodes for select using (true);
exception when duplicate_object then null;
end $$;

do $$ begin
  create policy settled_products_select on settled_products for select using (confirmed_by_user = true);
exception when duplicate_object then null;
end $$;
