# 目标核对 · 未完成清单（2026-07-26）

> 目标：A=`User_IO` 每次做单；B=`Shipments` 技支/次级源；根本库=`settled`。

## 一、目标对照

| 目标 | 状态 |
|------|------|
| A 渠道目录（输入三 / 输出五 / 汇总存档） | ✅ 骨架 |
| B 渠道完整本地生成过程（验证过的脚本+样例树） | ✅ 现役（C26080 03 PASS） |
| 根本库 settled | ✅ 规则键齐；行级总表/FNSKU 空（按 U1 已删空索引） |
| A↔B 自动接线（导入+导出） | ❌ |
| Gate→Final（C26080） | ❌ WAIT |
| 云端 Storage/API 实装 | ❌ 仅接口 + 新 migration 表结构 |
| GitHub 精简推送 | ⏳ 待你确认范围后 push |
| Supabase 数据灌入 | ⏳ migration 已写；CLI 未 link；灌数须确认 |

## 二、未完成任务（按优先级）

1. **拍板**：出货表是否进 A `输出端/` 单夹。  
2. **实现 A→B**：User_IO 输入 → 创建/更新同名 Shipments 黑箱。  
3. **实现 B→A**：黑箱/旧 `3_Output_Final` → User_IO 输出端 + 汇总存档（复制）。  
4. **明示 Gate→Final**（本票）或明确继续 pre-Final。  
5. **GitHub**：只推规则/脚本/Templates/User_IO 空树/migrations/轻样例；重 PDF 忽略（已改 `.gitignore`）。  
6. **Supabase**：`supabase db push` / Dashboard 跑 `20260726000000_channel_ab_interfaces.sql`；再同步 `settled_config` + `data_source_interfaces` 行（脚本可后补）。  
7. **测试债**：无前端单测；`next lint` 无配置失败；仅有 `Scripts/smoke_check.py` + 当票 `03`。  
8. **洁癖删除候选**（未确认不删）：`EF-C26080_待识别`、`_tmp_*`、本票 one-off 脚本等。

## 三、可行性摘要

可行。不足见对话回复与 [`Channel_AB_Architecture.md`](Channel_AB_Architecture.md)。
