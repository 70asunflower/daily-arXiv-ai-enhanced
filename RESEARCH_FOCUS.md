# RESEARCH_FOCUS.md — 维护者文档

> 本文件是 **daily-arXiv-ai-enhanced** 的研究定位、四支柱与筛选逻辑维护说明。
> 真正的“单一事实来源”是 [`config/research_focus.yaml`](./config/research_focus.yaml)，
> 本文件解释其设计意图与修改方法；改研究方向时**优先改 yaml**，不要只改代码或 Prompt。

---

## 1. 一句话定位

**带宽受限边缘集群大模型分布式推理论文雷达** —— 面向“带宽受限、多节点边缘集群中的
大模型分布式推理（LLM serving / inference）”的论文情报系统。

目标不是尽量多抓论文，而是每天选出真正可能影响实验设计、研究问题与源码学习的少量论文。

- **实验载体**：地面 7×NVIDIA Jetson Thor；节点间无 NVLink；重点考虑普通以太网 / 25GbE 等受限互联。
- **长期延伸**：太空在轨 / 边缘分布式计算（Space）作为受限集群场景的扩展，不是近期唯一关键词。

## 2. 三条研究路径（LLM 判断“对应 A/B/C”用）

| 路径 | 内容 |
|------|------|
| **A. 测量与瓶颈** | TP/PP/混合并行；吞吐、TTFT、TPOT、尾延迟、能效；内存带宽、网络带宽、通信占比；扩展规律 |
| **B. 通信与调度** | communication-aware partitioning；TP/PP 选择与混合；activation compression；compute-communication overlap；KV cache 迁移/卸载/分层；prefill/decode disaggregation |
| **C. 容错与弹性** | 节点失效；链路中断或带宽骤降；straggler；模型分区重映射；请求恢复；低通信/迁移开销的服务恢复 |

> A/B/C 是**粗粒度度量切面**，不直接等于四支柱；论文按“主标签”归属某一支柱（见 §5）。

## 3. 抓取分类（要改这里 + GitHub Variable）

来源：`research_focus.yaml → categories`，以及 **GitHub repo variable `CATEGORIES`**（CI 中读取注入爬虫）。
两者必须保持一致。

- **核心（core）**：`cs.DC, cs.AR, cs.PF, cs.NI, cs.OS` —— 全部进入摘要阶段。
- **支撑（support）**：`cs.LG, cs.ET` —— 数量大，须先经关键词/语义筛选，命中才进摘要。
- **优先级**（额度受限时）：`cs.DC > cs.AR > cs.PF > cs.NI > cs.OS > cs.LG > cs.ET`。

> 修改分类：编辑 `research_focus.yaml` 的 `categories`，并用
> `gh variable set CATEGORIES --body "cs.DC, cs.AR, ..." --repo 70asunflower/daily-arXiv-ai-enhanced`
> 同步 GitHub Variable。

## 4. 四支柱（Pillars）与标签归属

四支柱是研究的**关注权重**（用于排序“倾向”，不要求每天严格凑成比例）。
每篇论文按其**主标签**落入某一支柱；支柱权重：P1 35 / P2 30 / P3 20 / P4 15。

| 支柱 | 名称 | 权重 | 主标签集合 |
|------|------|------|------------|
| **P1** | 边缘 SoC 分布式推理与内存系统 | 35% | A-测量与瓶颈, Memory-统一内存/KV |
| **P2** | 受限/动态网络下的通信优化与弹性恢复 | 30% | B-通信与调度, C-容错与弹性 |
| **P3** | MoE 与分布式投机解码 | 20% | MoE-专家并行, Spec-MTP/投机解码 |
| **P4** | 能效与资源管理 | 15% | Energy-能效资源 |
| **Cross** | 跨支柱切面 | — | Infra-推理引擎, Arch-体系结构, Space-场景延伸 |
| **Background** | 支撑/背景 | — | Background-支撑 |

## 5. 十一（11）个论文标签

每篇保留论文必须选 **一个主标签**，允许多个**副标签**。

`Memory-统一内存/KV / MoE-专家并行 / Spec-MTP投机解码 / Energy-能效资源 /
C-容错与弹性 / B-通信与调度 / A-测量与瓶颈 / Infra-推理引擎 / Arch-体系结构 /
Space-场景延伸 / Background-支撑`

**主标签判定优先级**（scorer 内，命中多个时取最先满足者为主标签）：
**Memory > MoE > Spec > Energy > C > B > A > Arch > Infra > Space > Background**。
技术细分标签（Memory/MoE/Spec/Energy）优先于粗粒度 A/B/C，以凸显研究方向；
A/B/C 仍保留为副标签。`Infra/Arch/Space` 与 `Background` 为跨切面兜底，pillar 标为 Cross/Background。

## 6. 打分规则（可解释，禁止关键词堆叠）

来源：`research_focus.yaml → scoring` + `score_caps`。

| 规则 | 分值 | 说明 |
|------|------|------|
| **P1 核心交集（concept-intersection）** | **+8 且强制保留** | 由 `pillars.P1.intersection_patterns` 判定有效组合；单独命中 distributed/edge/inference 等宽词**不计** |
| **P2 通信优化 或 容错机制** | +5/组（comm 与 fault 各 +5） | `pillars.P2.comm_keywords` 与 `fault_keywords` 两组，分别设上限 |
| **强系统**（vLLM/SGLang/NCCL/Megatron/Ray） | +4/个（上限 2） | `strong_systems.keywords` |
| **硬件 + 互联 + benchmark** | +3（记一次） | `bonuses.hw_indicators` |
| **MoE/MTP 且多节点通信/调度** | +3（记一次） | P3 关键词 + 网络/调度信号 |
| **开源代码** | +2 | `bonuses.open_indicators` |
| **可信系统量化结果** | +2 | `bonuses.result_indicators` |
| **体系结构 + LLM** | +2（门控） | `bonuses.arch_gate` 通过才计 |
| **能效（同时给功耗+性能测量）** | +2 | `pillars.P4.power_indicators` + `perf_indicators` 同时命中 |
| **Space-only** | 0 | 仅命中 space/satellite，无推理系统机制 |
| 惩罚：纯 VLA/机器人 | −6 | `downweight` 无系统贡献时 |
| 惩罚：纯精度 / 纯训练 / 纯卸载 / survey | −5 / −4 / −3 / −2 | 同上，取最严重一项，不堆叠 |

> 防堆叠：`score_caps.max_total_keyword_score = 45`（关键词相关总分上限）。

## 7. 每日输出分层（filter.py）

| 分层 | 上限 | 入选规则 |
|------|------|----------|
| **建议精读 (must_read)** | ≤2 | 满足 `must_read_rules`：主类别 ∈ {A,B,C} 且 有开源 且 系统/低带宽相关 且 分数 ≥ 10 |
| **今日重点 (key)** | ≤5 | 按分数取最高 |
| **今日候选 (candidate)** | ≤12 | 其余相关论文（不填充弱论文；当天少则少出） |

前端按 `tier` 显示徽章并排序（建议精读 > 今日重点 > 今日候选）。

> **注意（deep_read 与 tier 是两个独立信号）**：卡片/Markdown 里出现的 `建议精读` 徽章（规则判定，`tier=must_read`）与 LLM 字段 `deep_read`（AI 判断）**口径不同、可能不一致**，二者均会标注，看到矛盾属正常、不是 bug：
> - `tier=must_read`：由 `filter.py` 按硬规则判定（主类别 ∈ {A,B,C} 且 有开源 且 系统/低带宽相关 且 分数 ≥ 阈值）。
> - `deep_read`：由 LLM 按 A/B/C + 开源 + 显著结果 + 对 7×Thor 价值 综合判断。
> 若想调整 must_read 门槛，改 `config/research_focus.yaml` 的 `must_read_rules`；若想调整 AI 建议精读，改 `ai/system.txt` 第 6 节口径。

## 8. LLM 摘要（20 字段情报）

`ai/system.txt` + `ai/template.txt` 驱动 `ai/enhance.py`，结构化输出由
`ai/structure.py` 定义（Pydantic，20 字段），包含：

`主类别 / 副标签 / 所属Pillar / TL;DR / 研究问题 / 核心方法 / 硬件与互联 /
并行通信调度容错机制 / 内存与KV cache机制 / 关键结果 / 对比基线 / 测量口径 /
对应A/B/C / 对7×Thor启发 / 基础设施假设 / 无NVLink是否成立 / 差异化研究点 /
建议精读 / 开源代码`。

> **Prompt 约束（重要）**：统一内存（unified memory）/ 太空（space）/ MoE / MTP（投机解码）
> 都不能仅凭关键词直接判定为创新点；需看是否给出在受限/无 NVLink 环境下的可复现机制、
> 量化结果与测量口径、与通信/调度/容错/内存瓶颈的具体关联。否则不得给高相关或建议精读。
>
> 修改摘要口径：编辑 `ai/system.txt` 与 `ai/structure.py`（保持字段名一致），
> 并同步 `to_md/paper_template.md` 与 `js/app.js` 的渲染。

## 9. 工作流（.github/workflows/run.yml）

- 触发：`cron "0 1 * * *"`（北京 09:00 ≈ UTC 01:00）+ 手动。
- 链路：`crawl`（Scrapy, 读 `CATEGORIES`）→ `check_stats` 去重 → `scorer.py` → `filter.py`
  → `enhance.py`（LLM）→ `convert.py`（Markdown）。
- 双分支部署：代码在 `main`，数据 JSONL 在 `data` 分支，GitHub Pages 读 `data` 分支。

## 10. 安全

- 密钥（OPENAI_API_KEY / TOKEN_GITHUB / ACCESS_PASSWORD）只在 **GitHub Secrets**，不进仓库。
- LLM 输出原经敏感词检测（`ai/enhance.py` 的 `is_sensitive`）；该检测依赖上游作者的第三方端点且 fail-closed，已**禁用**（直接 return False）以避免静默数据丢失。如需内容审核请指向自己的端点。不打印密钥；不删除历史数据。
- 前端 “Interested Keywords / Authors” 仅 localStorage 本地排序高亮，**不影响**抓取/打分/筛选。

## 11. 想换研究方向时

1. 改 `config/research_focus.yaml`（categories / pillars / tags / scoring / output）。
2. 同步 GitHub Variable `CATEGORIES`（`gh variable set ...`）。
3. 必要时改 `ai/system.txt` / `ai/structure.py` / `to_md/paper_template.md` / `js/app.js`（保持标签名、字段名一致）。
4. 本地 dry-run：
   ```bash
   CATEGORIES="cs.DC,cs.AR,cs.PF,cs.NI,cs.OS,cs.LG,cs.ET" \
     python ai/scorer.py data/X.jsonl data/X_scored.jsonl
   python ai/filter.py data/X_scored.jsonl data/X_top15.jsonl
   ```
   人工抽查分层、分类与 pillar 是否合理。
