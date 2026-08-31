# OCR / 格式转换 · 规划与现役

> 更新：2026-08-19  
> 外箱贴 OCR **默认不跑**（防卡顿）；已设计的 Tesseract **不删除**，降为备用引擎。  
> 确认闸门仍强制。LlamaParse 默认不调用。

## 原则（已确认）

| 项 | 规则 |
|----|------|
| 主路径 | 外箱贴 / 仓头：**PDF 文本层 ASCII**（`fba-recognize.ts`） |
| 备用 | **`tesseract.js`**（`convertWithTesseractBackup`）；**当且仅当**主路径无法处理或报错：非 PDF/图片、无文本层、抽不出仓码 **且** 货件号 |
| 禁止 | 主路径成功时仍跑 OCR；静默定稿；卸载 `tesseract.js` |
| 确认 | 主路径或备用抽出的字段都只是建议，须人工点确认 |
| 单价截图 | **另一条线**：仍以 Tesseract 为主（无 PDF 文本层）。见 `Templates/Cost_Shot_Recognize.md` |
| LlamaParse | 可选对照，不替代主/备用；须 `OCR_DUAL_COMPARE=on` + `LLAMA_CLOUD_API_KEY` |

扫描 PDF 无文本层时，备用会对原文件调 Tesseract。Tesseract 主要吃图片；纯扫描 PDF 可能仍失败 → 空行手填，不另加 PDF 栅格化依赖。

## 现役效果

| 场景 | 引擎 | 何时跑 |
|------|------|--------|
| 外箱贴 **PDF**（有文本层且抽出仓或货件号） | 文本层 ASCII | **主路径** |
| 外箱贴 PDF 无文本层 / 抽不出仓+货件号 | `tesseract.js` | **备用** |
| 外箱贴 / 货件 **图片** | `tesseract.js` | 主路径不能处理 → **备用** |
| 单价截图 | `tesseract.js` + 金额抽取 | **该场景的主路径**；仍须确认 |

不准时改数字/手填即可。

## LlamaParse（技术参考，默认关）

- **全名**：[LlamaParse](https://developers.llamaindex.ai/llamaparse/parse/)（LlamaCloud）  
- **做什么**：把难啃的 PDF / 扫描件 / 复杂版式图转成可抽取文本  
- **本仓**：代码已留对照；**默认关闭**。无 Key 不请求。  
- **怎么开**（须你明示）：`web/.env.local`

```text
OCR_DUAL_COMPARE=on
LLAMA_CLOUD_API_KEY=你的密钥
```

开启后：对照只附加判定；下游仍用主路径（外箱贴=PDF 文本层，失败后才是 Tesseract；单价截图=Tesseract）。不把 LlamaParse 当成自动第三引擎。

## 机器

| 文件 | 职责 |
|------|------|
| `web/lib/fba-recognize.ts` | 外箱贴主路径 + 失败后备用 OCR |
| `web/lib/pipeline/ocr-dual-convert.ts` | `convertWithTesseractBackup`、LlamaParse 对照 |
| `web/lib/pipeline/cost-shot-recognize.ts` | 单价截图（人读：`Templates/Cost_Shot_Recognize.md`） |
| `Scripts/carton_destination_rules.json` | 目的地 + 引擎策略（与 web 副本必须同文） |
