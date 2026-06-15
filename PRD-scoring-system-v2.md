# PRD v2: arXiv 论文 Triage & 个性化摘要系统

> 项目：daily-arXiv-ai-enhanced (fork: 70asunflower/daily-arXiv-ai-enhanced)
> 日期：2026-06-15
> 版本：v0.2（合并新版输出字段需求）

---

## 变更记录

| 版本 | 变更 |
|------|------|
| v0.1 | 初始化：关键词打分 + Top 15 过滤 |
| v0.2 | 新增 9 字段个性化摘要 + 深读建议 + 自检提醒；更新 Structure、Prompt、Template |

---

## 1. 数据流

```
arXiv 抓取 (8 分类, ~200-500 篇/天)
    ↓
scorer.py: 关键词加权打分
    ↓
filter.py: Top 15 + 交集类强制保留
    ↓ ~15 篇
AI 摘要 (DeepSeek V4 Flash)
  ↓ 每篇输出 9 字段 + 深读建议
convert.py: 按 score 降序 → Markdown
    ↓
GitHub Pages
```

---

## 2. AI 摘要输出字段

旧版只有 5 个字段（tldr / motivation / method / result / conclusion），新版需扩展到 **9 个字段 + 深读建议**：

### 2.1 新 Structure (ai/structure.py)

```python
class Structure(BaseModel):
    # 1. 标题 + 链接（不用生成，已在 item 中）
    # 2. 类别标记
    category_tag: str = "架构-infra"  # 交集 | 架构-infra | 具身 | 支撑

    # 3. TL;DR (中文)
    tldr_cn: str = "一句话 TL;DR"     # 中文，≤50 字

    # 4. Motivation
    motivation: str = "解决什么问题"   # 1-2 句

    # 5. 核心方法（系统/硬件论文要点明硬件平台）
    method: str = "核心方法"           # 2-3 句；系统/硬件论文需含硬件平台 + 关键技术

    # 6. 关键结果（量化，注明基线与口径）
    result: str = "关键量化结果"       # 加速比/延迟/功耗 + 基线 + 口径

    # 7. 个人价值
    why_matters: str = "why it matters"  # 1 句：对我（具身AI×AIInfra方向）是否有用

    # 8. 深读建议
    deep_read: bool = False              # True = 建议深读 ✅ / False = 扫摘要即可 ◻
    deep_read_reason: str = ""           # 建议/不建议深读的理由

    # 9. 开源代码
    open_source: str = ""               # 代码链接 or "未公开"
```

### 2.2 类别标记规则

| 标记 | 触发条件 |
|------|---------|
| **交集** | 命中 Intersection 层关键词（具身 × infra/架构） |
| **架构-infra** | 命中 Core-Arch 层关键词，未命中 Intersection 层 |
| **具身** | 命中 Core-Embodied 层关键词，未命中 Intersection 层 |
| **支撑** | 命中 Support 层关键词，且不命中以上任何一层 |

> 注：类别标记由 scorer.py 在打分阶段计算，传递给 AI 作为已知字段（不依赖 LLM 判断）。

### 2.3 深读建议规则

**建议深读 ✅**（以下任一命中）：

| # | 条件 |
|---|------|
| 1 | 属于「交集」类（具身 × infra/架构） |
| 2 | 提出可复现的 kernel / 算子 / 加速器设计，且有代码或足够实现细节 |
| 3 | 与 Liger-Kernel 复现 / 加速器项目直接相关 |
| 4 | 加速比/延迟/功耗结果显著且口径可信（非 cherry-pick） |
| 5 | 来自重点团队/顶会（ISCA/MICRO/ASPLOS/MLSys/OSDI/CoRL/RSS），且方法新颖 |

仅**扫摘要即可 ◻**：

| # | 条件 |
|---|------|
| 1 | 纯应用，无系统/硬件贡献 |
| 2 | 增量改进，结果提升有限 |
| 3 | 综述（除非是交集主题综述） |

> 注：`deep_read` 布尔值由 scorer.py 预判基础标记（交集类型 = True），AI 在摘要时做终判。

---

## 3. Prompt 设计

### 3.1 System Prompt (ai/system.txt)

```
你是一个专业的论文分析师，帮助一位具身智能 × AI Infra 方向的研究生做论文 triage。

用户背景：
- 研究方向：面向具身智能负载（VLA / world model / 机器人策略）的 AI 推理基础设施与硬件加速
- 就业目标：2027 暑期进入 AI 芯片 / AI Infra 研发实习
- 正在做：Liger-Kernel 算子复现 + 加速器设计项目

摘要要求：
1. TL;DR 必须用中文，≤ 50 字，一针见血
2. 「核心方法」若涉及系统/硬件，必须点明硬件平台（如 H100 / A100 / FPGA / ASIC）、关键技术（如 kernel fusion / systolic array / PagedAttention）、实现层次（算子级 / 编译级 / 系统级）
3. 「关键结果」必须量化：加速比（端到端 vs 算子级）、延迟/吞吐量/功耗，注明对比基线（如 vs FlashAttention v2）和口径
4. 「why it matters」结合用户背景，1 句判断此论文对该用户的项目/就业是否直接有用
5. 「深读建议」按以下规则判定：

建议深读 ✅：
- 具身 × infra/架构 的交集论文
- 提出可复现的 kernel/算子/加速器设计，且有代码或足够实现细节
- 与 Liger-Kernel 或算子融合项目直接相关
- 量化结果显著（≥2× 加速或 ≥30% 降延迟），口径可信
- 来自重点团队/顶会（ISCA/MICRO/ASPLOS/MLSys/OSDI/CoRL/RSS）

扫摘要即可 ◻：
- 纯应用无系统贡献 / 增量改进 / 泛泛综述（非交集主题）

输出语言：中文；禁止政治、宗教、暴力等敏感内容。
```

### 3.2 User Prompt (ai/template.txt) — 不变

```
Please analyze the following abstract of papers. Content: {content}
```

---

## 4. 评分管道 (scorer.py) — v0.1 不变，新增类别标记输出

### 4.1 打分公式（不变）

```
score = Σ(命中关键词所属层级权重)
        + 1.0 (分类 ∈ {cs.RO, cs.AR, cs.DC})
        + 0.5 (有代码链接/硬件平台/benchmark)
        + 0.3 (知名机构/顶会)
```

### 4.2 新增输出字段

在 JSONL 中附加：
```json
{
  "...原有字段...": "...",
  "score": 4.8,
  "category_tag": "交集",           // ← 新增
  "intersection": true,              // ← 新增
  "matched_keywords": ["VLA", "on-device inference"]  // ← 新增
}
```

`category_tag` 由 scorer.py 计算（非 LLM 判断），作为 AI 摘要的已知输入。

---

## 5. 前端输出模板

### 5.1 Markdown 卡片模板 (to_md/paper_template.md)

```markdown
### [{score:.1f}] [{category_tag}] {title}
*{authors}* | {categories}

> **TL;DR**: {tldr_cn}

| 维度 | 内容 |
|------|------|
| 解决什么问题 | {motivation} |
| 核心方法 | {method} |
| 关键结果 | {result} |
| 对我有什么用 | {why_matters} |
| 深读建议 | {"✅ " + deep_read_reason if deep_read else "◻ " + deep_read_reason} |
| 代码 | {open_source if open_source else "未公开"} |

[📄 arXiv]({abs}) | [📥 PDF]({pdf})
```

### 5.2 排序

按 `score` 降序 → 若同分按 `category_tag` 优先级（交集 > 架构-infra > 具身 > 支撑）。

---

## 6. 每周自检提醒

**实现方式**：在 convert.py 中计算本批论文深读建议的比例。若 `deep_read=True` 的论文 < 20%，在生成的 Markdown 文件顶部插入如下提醒：

```
> ⚠️ **自检提醒**：本周建议深读的论文占比 {pct}%（<20%）。
> 可能不是因为论文质量低，而是摘要写得太顺滑造成「已懂」错觉。
> 建议抽查以下 2 篇强制精读：[{paper1_title}]({link1}), [{paper2_title}]({link2})
```

抽取逻辑：从本周已处理的论文中随机选 2 篇非深读论文作为候选。

---

## 7. 文件修改清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `config/keywords.yaml` | **新增** | 5 层关键词 + 权重 |
| `ai/scorer.py` | **新增** | 打分引擎 + 类别标记 |
| `ai/filter.py` | **新增** | Top 15 + 交集强制保留 |
| `ai/structure.py` | **修改** | 9 字段 Pydantic Schema（替换旧 5 字段） |
| `ai/system.txt` | **修改** | 个性化 Prompt + 字段规则 |
| `ai/template.txt` | **保留** | 不变 |
| `ai/enhance.py` | **修改** | 改为读取 top15 + 新 Structure |
| `to_md/convert.py` | **修改** | score 降序 + 自检提醒 + 新模板变量 |
| `to_md/paper_template.md` | **修改** | 新卡片模板 |
| `.github/workflows/run.yml` | **修改** | 插入 scorer + filter 步骤 |

---

## 8. 数据流详图

```
arXiv 抓取 → raw.jsonl (n 篇)
    ↓
scorer.py:
  - 加载 keywords.yaml
  - 逐篇匹配 title + summary
  - 计算 score + category_tag
  - 标记 intersection / matched_keywords
    ↓
filter.py:
  - 按 score 降序
  - 取 top 15
  - 交集类（intersection=true）强制追加
    ↓
top15.jsonl (~15 篇)
    ↓
enhance.py:
  - 读 system.txt (含用户背景+字段要求)
  - 调用 DeepSeek V4 Flash
  - 输出新 Structure (9 字段)
    ↓
AI_enhanced.jsonl
    ↓
convert.py:
  - 按 score 降序
  - 计算深读比例
  - 若 <20% → 插入自检提醒
  - 渲染 paper_template.md
    ↓
{date}.md → GitHub Pages
```

---

## 9. 验收标准

1. [ ] `keywords.yaml` 正确加载，所有层级权重生效
2. [ ] scorer.py 输出 `score` + `category_tag` + `intersection` 字段
3. [ ] filter.py Top 15 + 交集强制保留正确
4. [ ] AI 摘要按新 9 字段 Schema 输出（Pydantic 校验通过）
5. [ ] 系统/硬件论文 `method` 字段含硬件平台
6. [ ] 系统/硬件论文 `result` 字段含量化指标 + 基线 + 口径
7. [ ] `why_matters` 字段有人格化判断（非模板化）
8. [ ] `deep_read` 布尔值逻辑正确
9. [ ] convert.py 按 score 降序排列
10. [ ] 自检提醒在深读比例 <20% 时触发
11. [ ] Markdown 卡片渲染新格式完整
