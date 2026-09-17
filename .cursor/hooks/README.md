# AutoExport 项目级 Hooks（进仓）

权威配置：仓库根 `.cursor/hooks.json` + `.cursor/hooks/*.py`  
打开本仓库的电脑都会加载（随 git 走）。用户级 `~/.cursor/hooks.json` 已清空，避免双重催报。

| 事件 | 脚本 | 作用 |
|------|------|------|
| `sessionStart` | `session_start_report_rules.py` | 注入四行汇报规则 |
| `postToolUseFailure` | `must_report_on_tool_failure.py` | 打戳（官方暂不能注回模型） |
| `stop` | `must_report_on_stop.py` | aborted/error/有戳 → followup 催四行 |

命令使用 `python .cursor/hooks/...`（可移植；本机需 PATH 有 python）。

冷备份仍见：`docs/cursor_user_hooks_backup/`（恢复脚本现也可指向项目级，优先用本目录）。
