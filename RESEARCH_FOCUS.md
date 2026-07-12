# RESEARCH_FOCUS.md — 维护者文档

> 本文件是 **daily-arXiv-ai-enhanced** 的研究定位与筛选逻辑维护说明。
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

## 3. 抓取分类（要改这里 + GitHub Variable）

来源：`research_focus.yaml → categories`，以及 **GitHub repo variable `CATEGORIES`**（CI 中读取注入爬虫）。
两者必须保持一致。

- **核心（core）**：`cs.DC, cs.AR, cs.PF, cs.NI, cs.OS` —— 全部进入摘要阶段。
- **支撑（support）**：`cs.LG, cs.ET` —— 数量大，须先经关键词/语义筛选，命中才进摘要。
- **优先级**（额度受限时）：`cs.DC > cs.AR > cs.PF > cs.NI > cs.OS > cs.LG > cs.ET`。

> 修改分类：编辑 `research_focus.yaml` 的 `categories`，并用
> `gh variable set CATEGORIES --body "cs.DC, cs.AR, ..." --repo 70asunflower/daily-arXiv-ai-enhanced`
> 同步 GitHub Variable。

## 4. 关键词分层（P0–P4）

| 层 | 含义 | 权重 | 说明 |
|----|------|------|------|
| **P0** | 研究交集（concept-intersection） | +8 且**强制保留** | 必须是“有意义组合”（见 yaml `p0_intersection.patterns`），单独命中 distributed/edge/inference 等宽词**不计** |
| **P1** | B/C 机制（通信感知分区/调度 + 容错弹性） | +5/个 | `comm_scheduling` 与 `fault_tolerance` 两组 |
| **P2** | AI Infra / 推理引擎 | +2/个 | vLLM/SGLang/TensorRT-LLM 等（强系统词排除避免重复计分） |
| **P3** | 体系结构 / 硬件副线 | +2/个（需通过 `arch_llm_gate`） | 仅当同时涉及 LLM 推理/内存瓶颈/Jetson 等才进高优先级 |
| **P4** | 太空场景 | +1/个（仅与系统层组合才计分） | 辅助，不单独置顶 |

**降权 / 排除**：命中 `downweight.weak_keywords`（VLA / 机器人 / 纯训练 / 纯精度 / 纯任务卸载 / survey 等）
且无 `system_exception_keywords` 系统贡献 → 按 `penalties` 降权（取最严重一项，不堆叠）。

## 5. 分类映射与主类别

每篇保留下来的论文归入一个主类别，其余作副标签：

`A-测量与瓶颈 / B-通信与调度 / C-容错与弹性 / Infra-推理引擎 / Arch-体系结构 / Space-场景延伸 / Background-支撑`

主类别判定优先级（scorer 内）：**C > B > A > Infra > Arch > Space > Background**。

## 6. 打分与上限

- 强系统（vLLM/SGLang/NCCL/Megatron/Ray）：+4/个（上限 2）。
- 加分：开源代码 +2、硬件/benchmark +3、明确结果 +2、核心 arXiv 分类 +1。
- 防堆叠：`score_caps.max_total_keyword_score = 45`。

详见 `research_focus.yaml` 第 8 节。

## 7. 每日输出分层（filter.py）

| 分层 | 上限 | 入选规则 |
|------|------|----------|
| **建议精读 (must_read)** | ≤2 | 满足 `must_read_rules`：主类别 ∈ {A,B,C} 且 有开源 且 系统/低带宽相关 且 分数 ≥ 10 |
| **今日重点 (key)** | ≤5 | 按分数取最高 |
| **今日候选 (candidate)** | ≤12 | 其余相关论文（不填充弱论文；当天少则少出） |

前端按 `tier` 显示徽章并排序（建议精读 > 今日重点 > 今日候选）。

## 8. LLM 摘要（17 字段情报）

`ai/system.txt` + `ai/template.txt` 驱动 `ai/enhance.py`，结构化输出由
`ai/structure.py` 定义，包含：

`主类别 / 副标签 / TL;DR / 研究问题 / 核心方法 / 硬件与互联 / 并行通信调度容错机制 /
关键结果 / 对比基线 / 对应A/B/C / 对7×Thor启发 / 基础设施假设 / 无NVLink是否成立 /
差异化研究点 / 建议精读 / 开源代码`。

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

1. 改 `config/research_focus.yaml`（categories / keywords / classification / output）。
2. 同步 GitHub Variable `CATEGORIES`（`gh variable set ...`）。
3. 必要时改 `ai/system.txt` / `ai/structure.py` / `to_md/paper_template.md` / `js/app.js`。
4. 本地 dry-run：`CATEGORIES=... python ai/scorer.py data/X.jsonl data/X_scored.jsonl && python ai/filter.py data/X_scored.jsonl data/X_top15.jsonl`，人工抽查分层与分类是否合理。
