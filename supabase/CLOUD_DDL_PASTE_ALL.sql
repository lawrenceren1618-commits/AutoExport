-- =============================================================================
-- AutoExport · 云端 DDL 一键粘贴包（仅云端，不影响本机文件）
-- 用法：Supabase Dashboard → SQL Editor → New query → 全选粘贴本文 → Run
-- 跑完后必做：Settings → API → Exposed schemas → 勾选 autoexport → Save
-- =============================================================================

-- ----- 1/5 init -----
create extension if not exists "pgcrypto";

create schema if not exists autoexport;
grant usage on schema autoexport to postgres, anon, authenticated, service_role;

create table if not exists autoexport.settled_products (
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

create table if not exists autoexport.settled_packing (
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
  on autoexport.settled_packing (product_key, brand, entity_code, effective_order_date desc);

create table if not exists autoexport.settled_fnsku (
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

create table if not exists autoexport.master_table_imports (
  id uuid primary key default gen_random_uuid(),
  file_name text not null,
  row_count int not null default 0,
  confirmed_at timestamptz,
  notes text,
  created_at timestamptz not null default now()
);

create table if not exists autoexport.draft_documents (
  id uuid primary key default gen_random_uuid(),
  batch_id text not null,
  doc_type text not null check (doc_type in ('order', 'outbound', 'freight', 'customs')),
  payload jsonb not null default '{}'::jsonb,
  status text not null check (status in ('draft', 'cross_check_failed', 'ready', 'finalized')) default 'draft',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists draft_documents_batch_idx on autoexport.draft_documents (batch_id, doc_type);

create table if not exists autoexport.cross_check_logs (
  id uuid primary key default gen_random_uuid(),
  batch_id text not null,
  passed boolean not null,
  report jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists autoexport.progress_nodes (
  id text primary key,
  parent_id text references autoexport.progress_nodes (id) on delete cascade,
  title text not null,
  status text not null check (status in ('todo', 'doing', 'done', 'blocked')) default 'todo',
  module text not null,
  next_action text,
  sort int not null default 0,
  updated_at timestamptz not null default now()
);

insert into autoexport.progress_nodes (id, parent_id, title, status, module, next_action, sort) values
  ('root', null, 'OFCE 总目标：订单→出货→货代→(FBA仓)→报关 可追溯可终审', 'doing', 'Gate', '按 P0→P5 推进', 0),
  ('P0', 'root', 'P0 基建', 'doing', 'P0', '完成 GitHub / Supabase / Vercel 隔离', 10),
  ('P0-1', 'P0', 'GitHub 仓库 AutoExport + 本机 git 身份', 'doing', 'P0', 'gh auth login 后创建并 push', 11),
  ('P0-2', 'P0', 'Supabase 项目 + 核心表', 'todo', 'P0', '在控制台新建 AutoExport 并执行 migration', 12),
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

alter table autoexport.settled_products enable row level security;
alter table autoexport.settled_packing enable row level security;
alter table autoexport.settled_fnsku enable row level security;
alter table autoexport.master_table_imports enable row level security;
alter table autoexport.draft_documents enable row level security;
alter table autoexport.cross_check_logs enable row level security;
alter table autoexport.progress_nodes enable row level security;

do $$ begin
  create policy progress_nodes_select on autoexport.progress_nodes for select using (true);
exception when duplicate_object then null;
end $$;

do $$ begin
  create policy settled_products_select on autoexport.settled_products for select using (confirmed_by_user = true);
exception when duplicate_object then null;
end $$;

grant all on all tables in schema autoexport to postgres, service_role;
grant select on all tables in schema autoexport to anon, authenticated;
grant all on all sequences in schema autoexport to postgres, service_role;

alter default privileges in schema autoexport
  grant all on tables to postgres, service_role;
alter default privileges in schema autoexport
  grant select on tables to anon, authenticated;

-- ----- 2/5 fba headers -----
create table if not exists autoexport.fba_warehouse_headers (
  id uuid primary key default gen_random_uuid(),
  order_code text,
  split_leg_id text,
  warehouse_code text,
  warehouse_address text,
  fba_shipment_id text,
  reference_id text,
  tracking_id text,
  carton_count int,
  strip_count int,
  source_filename text,
  recognize_notes text,
  status text not null default 'pending_tracking'
    check (status in ('pending_tracking', 'tracking_filled', 'confirmed')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists fba_wh_order_idx
  on autoexport.fba_warehouse_headers (order_code, split_leg_id);

create index if not exists fba_wh_fba_idx
  on autoexport.fba_warehouse_headers (fba_shipment_id);

alter table autoexport.fba_warehouse_headers enable row level security;

do $$ begin
  create policy fba_wh_service_all on autoexport.fba_warehouse_headers
    for all using (true) with check (true);
exception when duplicate_object then null;
end $$;

grant all on all tables in schema autoexport to postgres, service_role;
grant select on all tables in schema autoexport to anon, authenticated;

-- ----- 3/5 schema comment + legacy public→autoexport move -----
comment on schema autoexport is
  'AutoExport (office) app data only. Isolate from other apps in this Supabase project.';

do $$
declare
  t text;
begin
  foreach t in array array[
    'settled_products',
    'settled_packing',
    'settled_fnsku',
    'master_table_imports',
    'draft_documents',
    'cross_check_logs',
    'progress_nodes',
    'fba_warehouse_headers'
  ]
  loop
    if exists (
      select 1 from information_schema.tables
      where table_schema = 'public' and table_name = t
    ) and not exists (
      select 1 from information_schema.tables
      where table_schema = 'autoexport' and table_name = t
    ) then
      execute format('alter table public.%I set schema autoexport', t);
    end if;
  end loop;
end $$;

grant usage on schema autoexport to postgres, anon, authenticated, service_role;
grant all on all tables in schema autoexport to postgres, service_role;
grant select on all tables in schema autoexport to anon, authenticated;
grant all on all sequences in schema autoexport to postgres, service_role;

alter default privileges in schema autoexport
  grant all on tables to postgres, service_role;
alter default privileges in schema autoexport
  grant select on tables to anon, authenticated;

-- ----- 4/5 interfaces + settled_config + user_io_projects -----
create table if not exists autoexport.data_source_interfaces (
  id text primary key,
  task text,
  needs text,
  channel text check (channel is null or channel in ('A', 'B', 'shared')),
  module text,
  obtain jsonb not null default '{}'::jsonb,
  cloud jsonb not null default '{"status":"pending_cloud"}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists autoexport.settled_config (
  key text primary key,
  value jsonb not null,
  source_file text not null default 'Scripts/settled_knowledge_db.json',
  confirmed_at date,
  updated_at timestamptz not null default now()
);

create table if not exists autoexport.user_io_projects (
  project_id text primary key,
  entity_code text,
  status text not null default 'scaffold',
  black_box_relpath text,
  gate_final text not null default 'WAIT',
  meta jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

grant select on autoexport.data_source_interfaces to anon, authenticated;
grant select on autoexport.settled_config to anon, authenticated;
grant select on autoexport.user_io_projects to anon, authenticated;
grant all on autoexport.data_source_interfaces to service_role;
grant all on autoexport.settled_config to service_role;
grant all on autoexport.user_io_projects to service_role;

-- ----- 5/5 shipment jobs -----
create table if not exists autoexport.shipment_jobs (
  id uuid primary key default gen_random_uuid(),
  project_code text not null,
  entity_code text not null check (entity_code in ('C04', 'C07')),
  ship_date date,
  status text not null default 'open'
    check (status in ('open', 'processing', 'pre_final', 'gate_wait', 'final', 'archived', 'blocked')),
  gate_final text not null default 'WAIT'
    check (gate_final in ('WAIT', 'CONFIRMED', 'REJECTED')),
  meta jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (project_code)
);

create table if not exists autoexport.job_artifacts (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null references autoexport.shipment_jobs(id) on delete cascade,
  section_id text not null,
  direction text not null check (direction in ('in', 'out', 'archive')),
  file_name text not null,
  content_type text,
  byte_size bigint,
  sha256 text,
  storage_path text not null,
  save_mode text not null default 'upload_raw'
    check (save_mode in ('upload_raw', 'draft', 'pre_final', 'final', 'archive')),
  meta jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists job_artifacts_job_idx on autoexport.job_artifacts (job_id, section_id);

create table if not exists autoexport.job_handshake_log (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null references autoexport.shipment_jobs(id) on delete cascade,
  handshake_id text not null,
  ok boolean not null default false,
  payload jsonb not null default '{}'::jsonb,
  message text,
  created_at timestamptz not null default now()
);

grant select, insert, update on autoexport.shipment_jobs to authenticated;
grant select, insert, update, delete on autoexport.job_artifacts to authenticated;
grant select, insert on autoexport.job_handshake_log to authenticated;
grant all on autoexport.shipment_jobs to service_role;
grant all on autoexport.job_artifacts to service_role;
grant all on autoexport.job_handshake_log to service_role;
grant select on autoexport.shipment_jobs to anon;
grant select on autoexport.job_artifacts to anon;

-- done
