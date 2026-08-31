# 本地 / 云端执行面与完成同步

> 确认日：2026-08-13  
> 目标：入口决定执行面；作业中单写；完成后再单向同步。废止中途本地/Supabase 混写。

## 1. 输入口 → 执行面

| 打开方式 | 执行面 | 强制覆盖 |
|----------|--------|----------|
| 本机 `npm run dev` / 非 Vercel | **local** | `EXECUTION_PLANE=local` |
| Vercel 部署 | **cloud** | `EXECUTION_PLANE=cloud` |
| 缺省 | `EXECUTION_PLANE=auto`（按上表自动） | `/workspace` 可临时切换（cookie `ae-plane`） |

机器：`web/lib/runtime/execution-plane.ts` · `GET /api/runtime/plane`

## 2. 作业中（单写）

| 面 | 写入 | 禁止 |
|----|------|------|
| **local** | 只写 `2_Processed_AI/cloud_job_blobs/`；业务树写 `1_Input_Raw/Shipments/{项目}/` | 中途上传 Supabase |
| **cloud** | 只写 Supabase `job-uploads` / `job-outputs` | 静默落到本机盘并假装成功 |

`storage_files[].backend` 必须与写入面一致（`local` | `supabase`）。

## 3. 完成后（单向同步）

```text
本机做完 → 显式「上传云端」push → Supabase（成品）
云端做完 → meta.sync.cloud_ready → 本机「从云端拉取」pull → blobs + Shipments
```

| API | 谁 | 行为 |
|-----|-----|------|
| `POST /api/jobs/[id]/sync` `{action:"push"}` | 本机 | local 对象 → Supabase；`meta.sync.pushed_at`；`settle_candidates` 列表（**不**自动 H01） |
| `POST …/sync` `{action:"pull"}` | 本机 | Supabase → blobs + Shipments 镜像 |
| `POST …/sync` `{action:"status"}` | 两边 | plane、各 section backend、待 push/pull |

云端**不能**主动推送到办公室硬盘；办公室落盘只靠本机 pull。

## 4. 与既有闸门

| 闸门 | 关系 |
|------|------|
| **H01** | 沉淀行进 `settle_candidates` 后仍须你确认才入库 |
| **Gate HX** | 最终成品对照不变；同步不替代 Gate |
| **Shipments** | 本机权威业务树；pull/push 不改标签源 |
| **下载** | 优先 xlsx/PDF（`pickPrimaryStoredFile`）；draft/manifest 为旁注 |

## 5. UI

`/workspace` 顶栏：`执行面：本机 | 云端`；输出区「上传云端」/「从云端拉取」。

## 6. 指针

- Storage 桥：[`Storage_Python_Bridge.md`](Storage_Python_Bridge.md)  
- 模块握手：[`Architecture_Modules_Handshake.md`](Architecture_Modules_Handshake.md)  
