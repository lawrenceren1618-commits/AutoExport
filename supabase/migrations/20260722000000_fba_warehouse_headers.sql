-- FBA 仓头 / 追踪码（P9–P10；独立于产品沉淀主库）
-- Run in Supabase SQL Editor after 20260720000000_init_ofce.sql

create table if not exists fba_warehouse_headers (
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
  on fba_warehouse_headers (order_code, split_leg_id);

create index if not exists fba_wh_fba_idx
  on fba_warehouse_headers (fba_shipment_id);

alter table fba_warehouse_headers enable row level security;

do $$ begin
  create policy fba_wh_service_all on fba_warehouse_headers
    for all using (true) with check (true);
exception when duplicate_object then null;
end $$;
