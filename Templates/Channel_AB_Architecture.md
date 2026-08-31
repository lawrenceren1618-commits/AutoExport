# 双渠道架构（A 用户端 · B 黑箱技支）

> 确认日：2026-07-26  
> 机器键：`Scripts/settled_knowledge_db.json` → `confirmed_defaults.channel_ab_roles`  
> 接口表：[`Data_Source_Interfaces.md`](Data_Source_Interfaces.md)

## 目标分层

| 层 | 角色 | 路径 / 载体 |
|----|------|-------------|
| **根本库** | 已确认业务真理 | `Scripts/settled_knowledge_db.json`（+ 将来 Supabase 同步表）；总表入库须 H01 |
| **B 渠道** | 技术支持：已验证完整自动生成过程；文件+资料的**次级源** | `1_Input_Raw/Shipments/`、`2_Processed_AI/`、`Scripts/`、必要时 `3_Output_Final/` |
| **A 渠道** | 每次做单的**新作业地点**（上传 / 取件 / 审查存档） | `User_IO/{项目}/` |

```text
A 输入端 ──(接线后)──► B 黑箱生成/对照 ──► A 输出端 + A 汇总存档
                ▲
                └── 根本库 settled（对照 Gate）
B 不替代 settled；B 是过程与样例次级源。
```

## A 渠道（User_IO）

| 子树 | 用途 |
|------|------|
| `输入端/发货计划`（原「订单发货数据」） | 店、产品×箱数、下单日、发货日；订单号系统生成 |
| `输入端/亚马逊外箱贴与追踪截图` | 外箱贴 + 追踪截图 |
| `输入端/货代入库贴` | 货代回传 |
| `输出端/*` | 订单表、货代下单表、报关单证、产品标签、贴标包 |
| `汇总存档/` | 本票及后续发货审查向存档 |

详见 [`User_IO_Layout.md`](User_IO_Layout.md)。

## B 渠道（Shipments 黑箱）

- 现役脚本入口一律 `--project` → `Shipments/{项目}/…`
- 子夹：`订单表` / `出货表` / `货代入库贴下单表` / `报关资料表` / `FBA外箱贴` / `产品标签` / `货代入库贴` / `拆单比对` 等
- 作用：保留**可复现、已验证**的完整流水线与历史样例，供技支、对照、模板 interim_reference

## 接线状态（2026-07-26）

| 环节 | 状态 |
|------|------|
| A 目录骨架 | ✅ |
| B 流水线脚本 | ✅（本地作业） |
| A→B 导入 | ❌ 未实现 |
| B→A 导出复制 | ❌ `wire_export_pending` |
| Gate→Final 明示 | 本票 C26080 **WAIT** |
| 云端 Storage/API | 接口已登记，`pending_cloud` |

## GitHub / Supabase 分工

| 进 GitHub | 进 Supabase（接口/表/Storage） | 本机可留、默认不进仓 |
|-----------|-------------------------------|----------------------|
| 规则、Templates、Scripts、settled/interfaces JSON、migrations、User_IO 空树+轻 README、**少量**已验证轻样例 | 重 PDF、标签源、当票外箱贴树、总表行数据（H01 后）、作业上传 | 完整 Shipments 历史树、`2_Processed_AI` 调试、微信 zip 大包 |
