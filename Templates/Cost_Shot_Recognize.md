# 单价截图识别（人读说明）

> 对应源码：`web/lib/pipeline/cost-shot-recognize.ts`  
> 这是 **TypeScript 源码**，不是视频。Windows 资源管理器常把 `.ts` 关联成 MPEG-2 传输流，双击会打不开或当视频；请用 **Cursor / VS Code** 打开该 `.ts`，或直接读本文。

## 做什么

发货统计（`Ship_Stats` S3）上传单价截图后：

1. **主路径**：本机 `tesseract.js`（英+中，失败再试英）抽文字与金额  
2. 按规格行对齐候选单价；对不齐则列出「识别金额」供你改  
3. **LlamaParse** 仅当 `OCR_DUAL_COMPARE=on` 且有 Key 时做对照，**不改**主路径提案  
4. 必须你确认后才写入统计

与外箱贴识别是两条线：外箱贴主路径是 PDF 文本层，Tesseract 只在主路径抽不出仓码+货件号时备用。单价截图没有 PDF 文本层，所以仍以 Tesseract 为主。

## 机器入口

- `recognizeCostShot()` → `web/lib/pipeline/cost-shot-recognize.ts`  
- 对照工具 → `web/lib/pipeline/ocr-dual-convert.ts`  
- 规则 → `Templates/Ocr_Dual_Convert_Compare.md` · `Templates/Ship_Stats_Correspondence.md`
