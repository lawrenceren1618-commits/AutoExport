# 亚马逊货件仓库地址表

> 机器可读权威：[`Scripts/amazon_warehouse_addresses.json`](../Scripts/amazon_warehouse_addresses.json)  
> 货代 E8（收件地址1）调用本表。确认日：2026-08-20

## 规则

| 项 | 约定 |
|----|------|
| 主键 | 仓码（FC：AVP1 / CLT2…；AWD：IUTE / IUTJ / IUSP / HEA2…） |
| 货代地址 | `{仓码} - {街道} {邮编} - {城市}, {州} - United States`（以表内 `freight_addr` 为准） |
| 新仓 | **使用者提供地址 → 沉淀入 JSON → 之后生成调用** |
| 表中无行 | 生成时警告 + 占位；**禁止**把占位写进本表 |
| 改地址 | 须当次确认；同仓新旧地址冲突则汇报，不静默覆盖 |

## 当前已沉淀

| 仓码 | 渠道 | 地址（freight_addr） |
|------|------|----------------------|
| AVP1 | FC | AVP1 - 550 Oak Ridge Road - Hazle Township, PA 18202-9361 - United States |
| CLT2 | FC | CLT2 - 10240 Old Dowd Rd 28214-8082 - Charlotte, NC - United States（2026-08-20 你确认格式） |
| GYR2 | FC | GYR2 - 17341 W MINNEZONA AVE - GOODYEAR, AZ 85395-7672 - United States |
| LGB8 | FC | LGB8 - 1568 N Linden Ave - Rialto, CA 92376-8624 - United States |
| MDW2 | FC | MDW2 - 250 EMERALD DR - Joliet, IL 60433-3280 - United States |
| **LAS1** | FC | **LAS1 - 12300 Bermuda Road 89044-8746 - HENDERSON, NV - United States**（2026-08-20 C26089-A） |
| **TEB9** | FC | **TEB9 - 601 Randolph Road 08873 - SOMERSET, NJ - United States**（2026-08-20 C26089-A） |
| **SBD1** | FC | **SBD1 - 3388 S Cactus Ave 92316-3819 - BLOOMINGTON, CA - United States**（2026-08-20 C26089-A） |
| **LAX9** | FC | **LAX9 - 11263 Oleander Ave 92337-7441 - FONTANA, CA - United States**（2026-08-20 C26089-A） |
| HEA2 | AWD | HEA2 - 650 BOULDER DR Suite A 18031-1536 - BREINIGSVILLE, PA - United States |
| IUTE | AWD | IUTE - 16155 W Elwood St 85338 - GOODYEAR, AZ - United States（2026-08-19） |
| **IUTJ** | AWD | **IUTJ - 9253 Dreamland Drive 92335 - Fontana, CA - United States**（2026-08-20 C26089-B） |
| **IUSP** | AWD | **IUSP - 8140 Caliente Rd 92344 - HESPERIA, CA - United States**（2026-08-25 C26089-B 重建） |

## 与生成

`Scripts/09_generate_freight_customs_drafts.py` → `m1.warehouse_address.get_address`。

| **SCK8** | FC | **SCK8 - 4700 WILBUR AVE 94561-2677 - OAKLEY, CA - United States**（2026-08-25 C26095-A 大件仓） |
| **GEU3** | FC | **GEU3 - 18900 W McDowell Road 85396 - BUCKEYE, AZ - United States**（2026-08-25 C26095-B） |
