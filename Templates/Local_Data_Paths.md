# Local Data Paths（本机重数据路径登记）

## 策略

| 类别 | 去向 |
|------|------|
| 规则、对应关系、轻量 JSON/脚本、迁移、本票必要草稿（xlsx/json/md） | **GitHub** 仓库 AutoExport |
| 重 PDF：标签源库、FBA 外箱贴（FC/AWD 等树）、当票产品标签 | **本机路径登记**；云端阶段 → **Supabase Storage**（storage: supabase_pending） |

禁止把 桌布标签/、FBA外箱贴/、产品标签/ 整树推上 GitHub。助手只登记路径、从源**复制出**标签；不把重文件当仓库主体。

## 机器可读登记

见 [Scripts/local_data_paths.json](../Scripts/local_data_paths.json)。

| 键 | 含义 |
|----|------|
| label_source | 核心标签库 1_Input_Raw/00_Master_Reference/桌布标签 |
| shipment_project_C26079 | 发货项目夹 EF-C26079-C04-36460  桌布-2026.7.10 |
| ba_carton_labels | 该票 FBA外箱贴/（含 FC、AWD 等） |
| product_labels | 该票 产品标签/ |

github_ok = 可进 GitHub 的轻量规则/数据；supabase_pending = 重文件待上云存储。

## 与沉淀库

Scripts/settled_knowledge_db.json → confirmed_defaults.local_data_paths 指向本文档与 JSON。
