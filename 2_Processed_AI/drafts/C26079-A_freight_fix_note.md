# C26079-A freight forwarder xlsx fix

- Timestamp: 2026-07-22 17:22 +0800
- Template: D:\.cursor\Cursor-projects\AutoExport\1_Input_Raw\Shipments\EF-C26040-C04-8490_C04_20260510_8490\货代入库贴下单表\货代入库贴数据2026.5.10 HEA2 248箱.xlsx
- Template C2 preserved: 111111111 (never overwritten with tracking)

## Corrections applied (freight table only)

- Reset each file from freight template via shutil.copy2, then set allowed cells only.
- E3 warehouse code; E7 cleared; E8 = warehouse code + address; E10/E11/E12 cleared.
- A15 FBA id; B15 tracking; C15 cartons; F15 = floor(strips/cartons); G15 per-warehouse unit price.
- Restored fixed row-15 customs/product fields (I–R, M HS, N material, O use, H USD).
- S15 DISPIMG formula + re-injected xl/media / cellimages parts from template when openpyxl stripped them.
- Left C3/C5 and 客户单号 C2 unchanged from template rules; T15 empty (no invented URL).

## Files

- 货代下单表_C26079-A 2026.7.31桌布 AVP1 175箱.xlsx (AVP1): media=1, reinjected=True
- 货代下单表_C26079-A 2026.7.31桌布 CLT2 128箱.xlsx (CLT2): media=1, reinjected=True
- 货代下单表_C26079-A 2026.7.31桌布 GYR2 139箱.xlsx (GYR2): media=1, reinjected=True
- 货代下单表_C26079-A 2026.7.31桌布 LGB8 182箱.xlsx (LGB8): media=1, reinjected=True
- 货代下单表_C26079-A 2026.7.31桌布 MDW2 181箱.xlsx (MDW2): media=1, reinjected=True
