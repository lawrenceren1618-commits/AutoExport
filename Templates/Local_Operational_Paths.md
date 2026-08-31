# 本机作业路径（办公室 · 绝对路径参考）

> 确认日：2026-07-24  
> 与 [`Data_Source_Interfaces.md`](Data_Source_Interfaces.md) **并存**：  
> - **数据接口** = 任务从哪个接口取模板/参考（可移植、面向云端）  
> - **本文件** = 本机稳定处理时的**绝对路径速查**（办公室机）

机器可读：[`Scripts/local_operational_paths.json`](../Scripts/local_operational_paths.json)

## 原则

1. 本地跑通、助手定位上传/输出时，**绝对路径更稳**，可写在本文件。  
2. 进 Git 的规则/脚本仍优先用**相对仓库根**路径。  
3. 禁止再做「整盘目录 dump」；只登记**当前作业必需**的根路径。

## 办公室机（AutoExport）

| 用途 | 绝对路径 |
|------|----------|
| 仓库根 | `D:\.cursor\Cursor-projects\AutoExport` |
| 发货项目 | `D:\.cursor\Cursor-projects\AutoExport\1_Input_Raw\Shipments` |
| 人工总表 | `D:\.cursor\Cursor-projects\AutoExport\1_Input_Raw\00_Master_Reference` |
| 标签源（只读） | `D:\.cursor\Cursor-projects\AutoExport\1_Input_Raw\00_Master_Reference\桌布标签` |
| 草稿 | `D:\.cursor\Cursor-projects\AutoExport\2_Processed_AI\drafts` |
| 对照报告 | `D:\.cursor\Cursor-projects\AutoExport\2_Processed_AI\cross_check_reports` |
| 成品输出（旧仓） | `D:\.cursor\Cursor-projects\AutoExport\3_Output_Final` |
| 用户端 IO（新） | `D:\.cursor\Cursor-projects\AutoExport\User_IO` |

用户端结构见 [`User_IO_Layout.md`](User_IO_Layout.md)。黑箱仍为 `Shipments` + `2_Processed_AI`。

换机时：改 JSON/`本机` 段，勿改业务规则正文。
