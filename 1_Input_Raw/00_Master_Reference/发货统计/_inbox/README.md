# 发货统计表 — 上传区（本地）

## 路径（复制用）

```text
D:\.cursor\Cursor-projects\AutoExport\1_Input_Raw\00_Master_Reference\发货统计\_inbox\
```

在资源管理器地址栏粘贴上述路径回车即可。当前正式工作表：

```text
D:\.cursor\Cursor-projects\AutoExport\1_Input_Raw\00_Master_Reference\发货统计\_inbox\2026年发货记录.xls
```

（表内同时记 **C04 畅选** 与 **C07 易尚**。  
多规格批次对齐历史样板 **C26064**（给货日期/规格/FBA/运费纵向合并；尺寸简写；细框线+居中）。  
**FBA 按腿**：同单同日可并列；FC 五仓货件号合并只对应该腿明细；AWD `STAR-…` 单独一块。  
旧文件名 `2025.畅选 发货情况(2)(1).xls` 已废止。）

## 流程

1. 把最新发货情况表放进本夹（可覆盖同名；助手会先备份）。
2. 对话里说「统计表已上传」或指出文件名。
3. 助手只读列出：工作表、表头、样例行 → 规格归一草案 + 缺月补行提案 → **你确认货件号/运费等** → 再写主表。
4. 字段权威：`Templates/Ship_Stats_Correspondence.md`；云端树：`/ops/archives`（另步，须明示）。

## 货件号

- **不以领星 MCP 查货件号**（当前无此接口）。
- 权威：本仓外箱贴/入库贴确认的 `FBA…` / `STAR-…`（一仓一号，多仓列全）。
- 表中只有代表号、或与本仓不一致 → 列入待确认清单，由你手核/手补后再写入。

## 备份

| 文件 | 含义 |
|------|------|
| `_bak_inbox_before_desktop_YYYYMMDD.xls` | 覆盖桌面版之前的 inbox 旧副本 |
| `_bak_before_jul_aug_YYYYMMDD.xls` | 追加 7–8 月行之前 |
| `_bak_*.xls` | 过程备份，非正式件 |
| `_tmp_write_*.xls` | 仅主表被占用时的临时写入；正常应删除 |
| ~~`*_merged_*.xls`~~ | 已废止临时名，勿保留 |


## 注意

- 本夹 = inbox；历史颜色归一（ivory→米白）等大范围改写须你另确认。
- 运费金额不编造；新行渠道写货代，运费列留空待填。
