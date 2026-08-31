# 清点项用户答复纪要（2026-07-24）

## 已全部拍板

| ID | 决定 | 落盘 |
|----|------|------|
| **U1** | 空索引表删掉 | settled 去掉 products/packing/fnsku/sku 空数组 |
| **U2** | C04=许昌畅选贸易有限公司；C07=许昌易尚电子商务有限公司；**仅备案**，不影响流程 | entities + entity_brand_rules；`legal_name_role=internal_filing_only` |
| **U3** | C07 报关同 C04（波丽丝+畅选+波丽丝文件名） | 03_Customs / brand rules |
| **U4** | 尺寸短码**维持现表、锁定** | size_shortcode_map locked |
| **U5** | GWD 停用 | Carton_Label / settled |
| **U6** | 脚本按需留删 | one_off_scripts_policy |
| **U7** | 不硬收敛 01/02/03；先完成任务再简洁 | folder_simplify_policy |
| **U8** | 接口表 + **本机绝对路径速查并存**（已删旧 dump，新建 Local_Operational_Paths） | 见下 |
| **U9** | 云端后置；可 git→GitHub | 约定 |
| **U10** | FC/AWD 两套中文规格命名 | spec_folder_naming |
| **U11** | 交叉对照属沉淀一部分 → **已补最小可用 03**，并标下一步优先扩展 | `03_cross_validate.py` + gate_cross_validate |
| **U12** | 报关等表美金、不做汇率 | fx_rate_profit_only |

## U8 说明（已按你的本地稳定需求）

- **不是**「只用接口、禁止绝对路径」。  
- **数据接口**：任务从哪取模板（可移植/云端）。  
- **本机绝对路径**：办公室机上仓库/标签源/输出等速查 → `Templates/Local_Operational_Paths.md`。
