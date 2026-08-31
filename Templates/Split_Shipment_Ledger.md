# 拆单发货比对账本（Split Shipment Ledger）

> 用途：同一工厂订单分多批发货时，记录 **计划总量 / 各批已发 / 剩余未发**。  
> **默认工作准则**：出货腿按订单短码 + 字母编号 — `C26079-A`、`C26079-B`、`C26079-C`…  
> 机器可读：`拆单比对/split_ledger.json`；脚本 `Scripts/07_split_shipment_ledger.py`

---

## 0. 默认准则（强制）

把**一笔工厂订单**的出货拆成有序腿：

| 腿 ID | 含义 |
|-------|------|
| `{订单短码}-A` | **第一批**出货（默认总是先开 A） |
| `{订单短码}-B` | 仅当 A 之后仍有剩余时开启 |
| `{订单短码}-C`… | 同理递推 |

**订单短码**：从 EF 长号取出中间段。例：`EF-C26079-C04-36460` → **`C26079`** → 腿为 `C26079-A` / `C26079-B` / …

### 何时没有 B、C

```text
若 C26079-A 的已发条数（及约定箱数口径）= 该订单下单计划总量
→ 本单出货一次完成，不再创建 -B、-C
→ 账本 status = split_complete（或等价：整单一次发完）
```

若 A 只发了部分：

```text
剩余 = 计划 − A已发  > 0
→ 开启 C26079-B（只发剩余规格/数量）
→ 若 B 仍未发完 → C26079-C …
```

> **默认假设**：先按 `-A` 作业；不必预先建 B/C 空壳。B/C 仅在比对后发现剩余时才开。

### 多单并腿（补充指针）

次单并入主单某腿时：腿 ID 仍用主单短码；字段见 [`Multi_Order_Ship_Batch.md`](Multi_Order_Ship_Batch.md)。本文件一单多腿准则不变。

### 与「出货短号」区分（两套号）

| 号码 | 例 | 用途 |
|------|-----|------|
| **拆单腿 ID** | `C26079-A` | 订单内第几批发；比对账本主键 |
| **出货短号** | `C04-2616` | 店铺年序出货号（表内客户订单号）；**每腿可各占一个** |

不要把 `C26079-A` 印成 `C04-…` 短号，也不要用短号代替腿 ID。

---

## 1. 何时建账本

| 情况 | 动作 |
|------|------|
| 确定本单可能分批发，或已决定拆单 | `split_shipment=true`，建账本；首腿计划为 `-A` |
| `-A` 发满整单 | 无 B/C；可保留账本作一次发完记录 |
| 从未拆单且一次发完 | 可不建；或建账本仅登记 `-A`=全量 |

---

## 2. 比对层级

| 层级 | 键 | 用途 |
|------|-----|------|
| L0 | 总条数、总箱数 | A 是否发满整单 |
| L1 | 尺寸+颜色 | 出货表；下腿只发剩余种类 |
| L2 | 尺寸+颜色+条数/包+FNSKU | 对 FBA 外箱贴 |

```text
剩余 = 计划 − Σ(A+B+C…已发)
A已发 == 计划  ⇒  不再开 B/C
```

---

## 3. 文件位置

```text
Shipments/{项目}/
  拆单比对/
    split_ledger.json
    C26079-A_manifest.json     # 腿 ID 命名（非 batch_1）
    C26079-B_manifest.json     # 仅有剩余时出现
    _last_compare_report.md
  PROJECT.json                 # split_order_stem、split_leg_current、split_leg_next
```

---

## 4. 操作流程（默认）

1. `init` → 写入 `plan`；`order_stem=C26079`；`next_leg=C26079-A`；剩余=计划  
2. 做 **A** 腿：外箱贴 / 数量 → `add-batch`（`split_leg_id=C26079-A`）  
3. `compare`：  
   - 若剩余条数（及箱）为 0 → **完成，无 B/C**  
   - 若仍有剩余 → `next_leg=C26079-B`，下批发货只针对剩余  
4. B、C 同理，直到剩余为 0  

---

## 5. 与出货 / 货代 / 报关

| 单据 | 数量口径 |
|------|----------|
| 出货表 | **本腿** L1（如仅 A 的已发），不是整单计划（除非 A=全量） |
| 货代 / 报关 | **本腿**各仓箱数/条数 |
| 账本 | 累计已发 + 剩余；剩余不写入本腿报关 |

---

## 6. 脚本

```text
python Scripts/07_split_shipment_ledger.py init --project "…"
python Scripts/07_split_shipment_ledger.py status --project "…"
python Scripts/07_split_shipment_ledger.py add-batch --project "…" --batch-json "…/C26079-A_manifest.json"
python Scripts/07_split_shipment_ledger.py compare --project "…"
```

`add-batch` 的 JSON 须含 `split_leg_id`（如 `C26079-A`）；缺省时按 `next_leg` 自动分配 A→B→C。
