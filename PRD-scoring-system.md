# PRD: arXiv 论文 Triage & 评分系统

> 项目：daily-arXiv-ai-enhanced (fork: 70asunflower/daily-arXiv-ai-enhanced)
> 日期：2026-06-15
> 版本：v0.1

---

## 1. 背景与目标

### 1.1 现状

目前 daily-arXiv-ai-enhanced 按 CATEGORIES 变量爬取 8 个 arXiv 分类的论文，全部送入 DeepSeek 生成 AI 摘要，前端按分类平铺展示。用户端关键词/作者匹配是前端 localStorage 级别的二进制过滤，没有服务端评分或排序。

### 1.2 痛点

1. **信息过载**：8 个分类每天几百篇论文，AI 摘要为每篇花 ~0.2 元，大部分与用户研究方向无关
2. **无优先级区分**：具身 × infra 的交集论文与泛泛的论文混在一起
3. **缺少 triage**：用户没精力每天看几百篇，需要机器先过滤 + 打分
4. **API 浪费**：每天 ~20 元跑 100 篇摘要，其中 80% 是噪声

### 1.3 目标

实现一个可配置的、Pipeline 内嵌的论文评分 + 过滤系统，使：
- 每天只保留 ~15 篇高价值论文（含交集类论文强制保留）
- 按加权得分降序排列
- 对系统/硬件类论文引导 AI 输出关键 benchmark 细节
- 减少 AI API 调用量 80%+

---

## 2. 用户画像

| 角色 | 需求 |
|------|------|
| **Felix (本人)** | 具身智能 × AI Infra 方向研究生。每天想看到：① 具身 × 系统/架构的交集论文（一篇不漏）；② 高分的架构/算子/芯片论文；③ 高分的具身智能论文；④ 每日 top 15，按分排序。过滤器不要漏掉重要论文，但可以容忍少量噪声通过。 |

---

## 3. 功能需求

### FR-01: 关键词配置 (config/keywords.yaml)

一个 YAML 文件，定义多层关键词体系：

| 层级 | 权重 | 用途 |
|------|------|------|
| 交集 (Intersection) | ×3 | 具身 × infra，必须一篇不漏 |
| 核心-架构 (Core-Arch) | ×2 | 就业弹药：GPU kernel / chip / accelerator |
| 核心-具身 (Core-Embodied) | ×2 | 导师方向：VLA / manipulation / world model |
| 支撑-MLSys (Support) | ×1 | 理解负载背景 |
| 排除 (Exclude) | -2 | 可降权的噪声主题 |

**匹配范围**：标题 + 摘要（小写不区分大小写）

### FR-02: 打分引擎 (ai/scorer.py)

评分公式：
```
score = Σ(命中关键词所属层级权重)
        + 1.0  (if paper 分类在 核心集: cs.RO/cs.AR/cs.DC)
        + 0.5  (if 有明确可复现细节: 代码链接 / 硬件平台 / benchmark)
        + 0.3  (if 知名机构 or 顶会: ISCA/MICRO/ASPLOS/MLSys/OSDI/CoRL/RSS)
```

### FR-03: Top-N 过滤

- 每天打分后，取 **score 降序 Top 15**
- **交集类论文强制保留**：即使分数低于 Top 15 阈值，也包含在输出中
- 输出两个 JSONL 文件：
  - `{date}_scored.jsonl` — 全量打分数据（含所有论文 + score 字段）
  - `{date}_top15.jsonl` — 过滤后的 top 15 + 交集类，送入 AI 摘要

### FR-04: Prompt 增强

在 AI 摘要的 system prompt 中追加指令：
> "对于涉及系统架构、硬件设计、性能评测的论文（关键词：accelerator, FPGA, ASIC, benchmark, throughput, latency, hardware, GPU kernel 等），你必须保留以下关键细节：硬件平台/工艺节点、benchmark 设置、加速比口径（端到端 vs 算子级）、核心指标数值（FLOPs / latency / throughput）、ablation 分析结论。"

### FR-05: 前端排序

- `convert.py` 按 score 降序排列论文
- 论文卡片显示 score 徽章
- 前端按 score 降序渲染（替代当前按分类排序）

### FR-06: GitHub Actions 集成

在现有 workflow 的 "Crawl" 和 "AI Enhancement" 之间插入新步骤：

```
Crawl → [NEW] Score & Filter → AI Enhancement → Convert → ...
```

---

## 4. 非功能需求

| 维度 | 要求 |
|------|------|
| **性能** | 打分步骤应在 <3 秒内完成（纯字符串匹配，无网络请求） |
| **成本** | AI 摘要的论文量从全量减少到每天 ~15 篇，API 费用降至 ~3 元/天 |
| **可配置** | 关键词/权重/阈值可通过 YAML 修改，无需改代码 |
| **可扩展** | 新增关键词层级或权重只需改 YAML，评分公式可扩展新因子 |
| **可观测** | 工作流日志输出：总论文数、过滤后数、保留的交集数、最高/最低分 |

---

## 5. 架构设计

### 5.1 数据流

```
arXiv 列表抓取 (8分类)
    ↓ raw JSONL (n 篇, n~200-500)
scorer.py: 关键词加权打分
    ↓ scored JSONL (n 篇, 含 score 字段)
filter.py: Top 15 + 交集类强制保留
    ↓ top15 JSONL (~15 篇)
AI 摘要 (DeepSeek)
    ↓ AI-enhanced JSONL (~15 篇)
convert.py → 按 score 降序排列的 MD
    ↓
GitHub Pages
```

### 5.2 文件清单

| 文件 | 类型 | 说明 |
|------|------|------|
| `config/keywords.yaml` | 新增 | 关键词配置 + 权重 |
| `ai/scorer.py` | 新增 | 打分引擎 |
| `ai/filter.py` | 新增 | Top-N 过滤 + 交集强制保留 |
| `ai/enhance.py` | 修改 | 改为读取 top15 文件，追加 prompt |
| `ai/system.txt` | 修改 | 追加 benchmark 细节指令 |
| `ai/structure.py` | 保留 | 无需修改 |
| `to_md/convert.py` | 修改 | 按 score 降序排列 |
| `.github/workflows/run.yml` | 修改 | 插入打分 + 过滤步骤 |
| `js/app.js` | 可选 | 显示 score 徽章 |

---

## 6. 评分公式详解

```
score = keyword_match_score        ← 累加命中关键词的层级权重
        + category_bonus            ← 1.0 if 分类 ∈ 核心集
        + reproducibility_bonus     ← 0.5 if 有代码链接/硬件平台/benchmark
        + venue_bonus               ← 0.3 if 知名机构或顶会
```

### 权重层说明

| 层级 | 权重 | 数量 | 示例关键词 |
|------|------|------|-----------|
| 交集 (Intersection) | ×3 | 17 个 | on-device inference, VLA inference, robot SoC, hardware-software co-design |
| 核心-架构 (Core-Arch) | ×2 | 24 个 | accelerator, GPU kernel, Triton, systolic, PIM, chiplet, FlashAttention |
| 核心-具身 (Core-Embodied) | ×2 | 14 个 | VLA, manipulation, humanoid, diffusion policy, sim-to-real, world model |
| 支撑-MLSys (Support) | ×1 | 10 个 | LLM serving, inference engine, MLIR, TVM, distributed training |
| 排除 (Exclude) | -2 | 5 个 | pure theory, social, recommendation system, medical imaging |

### 阈值

- **硬阈值**：score <= 0 直接丢弃（除非是交集类论文）
- **Top-N**：取 score 降序前 15 篇
- **强制保留**：交集类论文（命中 Intersection 层 ≥1 个关键词）无论分数高低均保留

---

## 7. 输出格式

### 7.1 scored JSONL

```
{"id": "...", "title": "...", ..., "score": 4.8, "intersection": true, "matched_keywords": ["VLA", "on-device inference"], "code_url": "...", "code_stars": null}
```

新增字段：
| 字段 | 类型 | 说明 |
|------|------|------|
| `score` | float | 综合评分 |
| `intersection` | bool | 是否是交集类论文 |
| `matched_keywords` | string[] | 命中的关键词列表 |
| `reproducible` | bool | 是否有可复现细节 |
| `venue_score` | float | 顶会/机构加分 |

### 7.2 top15 JSONL

限制为 ~15 篇的高分论文子集 + 强制保留的交集论文。

---

## 8. 工作量估算

| 模块 | 预估 | 依赖 |
|------|------|------|
| `config/keywords.yaml` 编写 | ~10 分钟 | PRD 中定义的关键词列表 |
| `ai/scorer.py` 实现 | ~20 分钟 | YAML 读取 + 字符串匹配 + 公式 |
| `ai/filter.py` 实现 | ~5 分钟 | 排序 + Top-N + 交集强制保留 |
| `ai/enhance.py` 修改 | ~10 分钟 | 改为读取 top15 + 追加 prompt |
| `ai/system.txt` 修改 | ~5 分钟 | 追加 benchmark 细节指令 |
| `to_md/convert.py` 修改 | ~5 分钟 | 按 score 降序排列 |
| `run.yml` 修改 | ~10 分钟 | 插入打分 + 过滤步骤 |
| 前端 score 徽章 | ~15 分钟 | `js/app.js` 可选 |
| 测试验证 | ~15 分钟 | 本地跑通流程 |
| **合计** | **~1.5 小时** | |

---

## 9. 验收标准

1. [ ] `keywords.yaml` 读取正常，所有层级的权重生效
2. [ ] 打分论文输出 `score` 字段，计算逻辑正确
3. [ ] Top 15 过滤正常，交集类论文强制保留
4. [ ] AI 摘要只跑过滤后的论文（验证 API 用量减少）
5. [ ] 系统/硬件论文的摘要包含 benchmark 细节
6. [ ] 前端按 score 降序排列
7. [ ] score 徽章在论文卡片上可见
8. [ ] 工作流日志输出过滤统计信息
