# 云端 / 本机隔离（强制）

> 确认日：2026-07-27  
> 用户要求：云端规则、接口、数据处理状态**不得影响本地**；Supabase 只满足云端运行。

## 单向原则

```text
本机权威（只读复制出去）
  Scripts/settled_knowledge_db.json
  Scripts/data_source_interfaces.json
  Scripts/*.py / 本地 Shipments
        │
        │  允许：local → cloud 快照灌入（--apply）
        ▼
云端运行库 autoexport.* + Storage
        │
        ✕ 禁止：cloud → 回写本机 settled / Shipments / 接口 JSON
```

| 允许 | 禁止 |
|------|------|
| 在 Supabase 执行 migration、建桶 | 用云端行覆盖本机 `settled_knowledge_db.json` |
| `17_sync_* --apply` **推送**元数据到云 | 拉取云端 job/Gate 状态改本地 PROJECT |
| Vercel 读写 `shipment_jobs` / Storage | 让本地脚本默认连云端当唯一库 |
| 云端作业状态留在云端表 | 云端规则「盖掉」本机 `.cursorrules` / Templates |

## 本机继续怎么用

- 本地发货样例、对照、Python 脚本：**仍读本机文件**，不依赖 Supabase 是否在线。  
- 云端作业台 `/workspace`：只读写 `autoexport` schema + Storage。  
- 两边字段**语义对齐**（同一套 JSON 规格），但**状态库分离**。

## 同步脚本约束

`Scripts/17_sync_interfaces_to_supabase.py`：

- 仅 `UPSERT` 到云端表；**零本机写入**。  
- 默认 dry-run；`--apply` 才推。  
- 失败不得改本地文件「补救」。
