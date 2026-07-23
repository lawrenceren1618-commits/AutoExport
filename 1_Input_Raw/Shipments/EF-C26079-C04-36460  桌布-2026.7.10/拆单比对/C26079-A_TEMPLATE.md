# C26079-A 填写说明

1. 复制 `C26079-A_TEMPLATE.json（必填 split_leg_id: C26079-A）` 为 `C26079-A_manifest.json`（或直接改模板后另存）。
2. 按 **FBA 货件 / 实际出库** 填写顶栏、`by_size_color`、`by_fnsku`、`warehouses`（未发填 0）。
3. 保存后执行：

```powershell
python Scripts/07_split_shipment_ledger.py add-batch --project "D:\.cursor\Cursor-projects\AutoExport\1_Input_Raw\Shipments\EF-C26079-C04-36460  桌布-2026.7.10" --batch-json "D:\.cursor\Cursor-projects\AutoExport\1_Input_Raw\Shipments\EF-C26079-C04-36460  桌布-2026.7.10\拆单比对\C26079-A_manifest.json"
```

4. 脚本会更新 `split_ledger.json`、写入侧车 `C26079-A_manifest.json`，并刷新 `_last_compare_report.md`。
