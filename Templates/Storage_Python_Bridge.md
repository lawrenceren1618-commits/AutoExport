# Storage 真流 + Python 生成器桥接

> 确认日：2026-07-27（补齐出货 / 09 参数化 / 标签只读复制）  
> **执行面（2026-08-13）**：作业中按本机/云端**单写**；完成后再 sync。全文 → [`Local_Cloud_Execution_Plane.md`](Local_Cloud_Execution_Plane.md)

## 已接线

| 能力 | 实现 |
|------|------|
| 上传 | `POST /api/jobs/[id]/upload` → 按执行面单写（local→blobs / cloud→Supabase） |
| 完成同步 | `POST /api/jobs/[id]/sync` `push`\|`pull`\|`status` |
| 下载 | `GET /api/jobs/[id]/download?section=`（优先正式件 xlsx/PDF） |
| 桥 | `Scripts/19_cloud_job_step.py` |
| `gen_order` | `m1` 填单 |
| `gen_product_labels` | `m1/label_copy.py`：订单行→源库**只读复制**→`{EF}标签/{N}条装/{尺寸}/原名.pdf` |
| `gen_trio` | `m1/outbound_fill.py` 出货 + 物化 headers/recognize → `09`（可传 JSON 路径） |

## 前期缺口根因（核查）

| 项 | 具体原因 |
|----|----------|
| 出货表无脚本 | **实现顺序刻意延后**：规则/`outbound_short_seq`/`table_field_maps` 已齐，但只做了 `05` 订单；云端曾标 `05b` 占位并阻断伪造成品。样本 xlsx 在 Shipments，生成器未开工。 |
| 09 不能上云 | **做成了 C26079-A 一次性脚本**：识别/仓头 JSON 文件名写死、输出名写死；云端未物化项目树就无法调用。 |
| 标签「只清点」误解 | **06 整票硬编码 C26079**；云端桥未调用复制逻辑，误写成 inventory。正确语义=按订单从源库 **copy** 出专属包，**禁止改源**（现已按此实现）。 |

## Supabase 核查

- 复检脚本：`node Scripts/20_supabase_health_check.mjs`
- 往返冒烟：`node Scripts/21_storage_roundtrip_smoke.mjs`
- **2026-07-27 复检**：`verdict=supabase_ready`（JWT 完整；四桶齐全；upload/download/signed URL 通过）

## 环境

`PYTHON_RUNNER=local|off|http`（见 `web/.env.local.example`）
