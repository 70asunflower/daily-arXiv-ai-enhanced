# 重构报告 / Refactor Report — 四支柱论文雷达

> 仓库：`daily-arXiv-ai-enhanced`
> 目标：从「泛 AI 论文自动收集器」调整为「带宽受限边缘集群大模型分布式推理论文雷达」
> 实验载体：7×NVIDIA Jetson Thor（无 NVLink，25GbE / 普通以太网）
> 日期：2026-07-12

---

## 1. 读取的文件（Pre-checks）

| 文件 | 作用 | 结论 |
|------|------|------|
| `README.md` | 项目说明 | 已含新定位，更新了标签列表 |
| `RESEARCH_FOCUS.md` | 维护者文档 | 已重写为四支柱 / 11 标签 |
| `.github/workflows/run.yml` | CI 工作流 | cron `0 1 * * *`（北京 09:00）；链路安全，无破坏性 |
| `daily_arxiv/.../spiders/arxiv.py` | Scrapy 爬虫 | 读 `CATEGORIES` env，抓 `arxiv.org/list/{cat}/new`，只产 `id+categories` |
| `daily_arxiv/.../pipelines.py` | 元数据补全 | 用 `arxiv` lib 逐篇补全 title/authors/summary |
| `daily_arxiv/.../check_stats.py` | 7 日去重 | 按 arXiv ID 去重，保留最新 |
| `ai/scorer.py` | 打分 | 重写为四支柱加权引擎 |
| `ai/filter.py` | 每日分层 | 3 层输出（must_read/key/candidate） |
| `ai/enhance.py` | LLM 摘要 | 扩展 20 字段 + 兜底字典 |
| `ai/structure.py` | LLM schema | Pydantic 20 字段 |
| `ai/system.txt` / `ai/template.txt` | Prompt | 升级字段 + 约束 |
| `to_md/convert.py` / `to_md/paper_template.md` | Markdown | 11 标签 + 新字段渲染 |
| `js/app.js` / `css/styles.css` | 前端 | 11 标签筛选 + 新字段 + 配色 |
| `config/research_focus.yaml` | 单一事实来源 | 四支柱 / 11 标签 / 打分 / 输出 |

**关键事实确认**：
- 后端实际抓取：`cs.DC > cs.AR > cs.PF > cs.NI > cs.OS`（核心，全量进入）+ `cs.LG, cs.ET`（支撑，先关键词筛选）。
- 关键词是**后端**预过滤 + 打分用（scorer/filter 读 config），不是前端-only。
- Settings「Interested Keywords」**仅 localStorage**：`js/settings.js` 读 `preferredKeywords`，只做前端高亮/排序，不影响后端抓取/打分（已在 `settings.html` 标注「不影响后台抓取」）。

## 2. 原系统 vs 新系统

| 维度 | 原系统 | 新系统 |
|------|--------|--------|
| 定位 | 泛 AI 论文收集 | 带宽受限边缘集群 LLM 分布式推理雷达 |
| 分类 | P0–P4 分层（8 标签） | 四支柱 P1–P4 + Cross/Background（11 标签） |
| 标签 | A/B/C/Infra/Arch/Space/Background | + Memory/MoE/Spec/Energy（共 11） |
| 打分 | P0 交集 +8 等 | P1 交集 +8 强制保留；P2 通信/容错 +5；强系统 +4；硬件 +3；MoE/MTP +3；开源/结果/架构/能效 +2；space-only 0；VLA/训练/精度/卸载/综述 降权 |
| LLM 字段 | 17 字段 | 20 字段（新增 内存与KV / 测量口径 / 所属Pillar） |
| 配置 | 分散（多文件） | `config/research_focus.yaml` 单一来源 |

## 3. 修改的文件（13 个）

```
M README.md
M RESEARCH_FOCUS.md
M ai/enhance.py          (+7  : 新字段兜底 + pillar 输入变量)
M ai/filter.py           (+6  : 注释修正 P0→P1)
M ai/scorer.py           (重写 : 四支柱加权引擎)
M ai/structure.py        (+30 : 新增 memory_kv / measurement / pillar)
M ai/system.txt          (+26 : 23 字段说明 + 创新点约束)
M ai/template.txt        (+3  : pillar 输入变量)
M config/research_focus.yaml (重写 : 四支柱/11标签/打分/输出)
M css/styles.css         (+26 : 11 标签配色)
M js/app.js              (+26 : 11 标签 + 新字段渲染 + pillar 副标签)
M to_md/convert.py       (+17 : 11 标签 + 新字段)
M to_md/paper_template.md (+6 : 新字段)
```
（无数据/历史文件被删除；无密钥入仓。）

## 4. 单一配置来源

`config/research_focus.yaml` 现在集中维护：**定位 / 抓取分类 / 四支柱与权重 / 11 标签与展示名 / 主标签优先级 / 打分规则与上限 / 降权例外 / 强系统词 / 加分项 / 每日输出分层 / 建议精读规则**。
`scorer.py`、`filter.py`、`enhance.py`、`convert.py`、前端说明均从它派生。改研究方向优先改它，再同步 GitHub Variable `CATEGORIES`。

## 5. 四支柱如何影响排序

- 支柱是**排序倾向**（pillar 权重 35/30/20/15），不要求每天严格凑比例（spec §9 明确）。
- 每篇论文按**主标签**归属支柱；主标签由 `tags.priority`（Memory>MoE>Spec>Energy>C>B>A>Arch>Infra>Space>Background）决定，技术细分标签优先于粗粒度 A/B/C。
- `pillar` 字段写入 JSONL，前端卡片/弹窗与 Markdown 均展示「所属 Pillar」。
- 每日分层仍由 `score` 驱动（must_read/key/candidate），支柱权重体现在打分加分结构里（P1 交集 +8 最高、P2 通信/容错 +5/组、P3 MoE/MTP +3、P4 能效 +2）。

## 6. Settings 前端/后端控制边界

- **后端控制**：`config/research_focus.yaml` + GitHub Variable `CATEGORIES`（抓取）、`scorer/filter` 用 config 打分分层。
- **前端-only**：Settings「Interested Keywords / Authors」→ `localStorage`，仅本地高亮与置顶，**不回传、不影响后台**。已在 `settings.html` 写明「仅影响当前浏览器显示，不影响后台抓取」。
- 若未来想让前端关键词真正影响后端，必须同步进 `research_focus.yaml`（当前设计刻意不耦合）。

## 7. Dry-run 计数（代表性 16 篇样本）

> 说明：未调用付费 LLM（spec §13 要求基础测试不花 LLM 费用）。以下为 scorer→filter 链路（无需 LLM）：

| 阶段 | 数量 |
|------|------|
| 输入样本 | 16 |
| scorer 输出 | 16（分数区间 −4.0 ~ +33.0；P1 交集强制保留 11） |
| filter 保留 | 14（2 篇被软下限 score<0 丢弃） |
| 建议精读 must_read | 2 |
| 今日重点 key | 3 |
| 今日候选 candidate | 9 |

## 8. 每支柱 / 标签样本计数（dry-run）

| 标签 | Pillar | 样本数 | 代表 |
|------|--------|--------|------|
| B-通信与调度 | P2 | 3 | 00004/00002/00016 |
| C-容错与弹性 | P2 | 1 | 00005（must_read） |
| Memory-统一内存/KV | P1 | 1 | 00003 |
| A-测量与瓶颈 | P1 | 3 | 00015/00001/00009 |
| MoE-专家并行 | P3 | 1 | 00006 |
| Spec-MTP/投机解码 | P3 | 1 | 00007 |
| Energy-能效资源 | P4 | 1 | 00008 |
| Space-场景延伸 | Cross | 1 | 00010（candidate，非 Top） |
| Background-支撑 | Background | 1 | 00013（survey，candidate） |
| （丢弃） | — | 2 | 00011 VLA(−3)、00012 纯训练(−4) |

## 9. 三个样本（分数 / 标签 / 理由）

1. **2501.00005**（score 30.0 / C-容错与弹性 / P2 / must_read）
   理由：命中 P1 交集（distributed+inference）+8；容错关键词 fault-tolerant/node failure/straggler/model repartitioning/service recovery 计满 +20；开源 +2；结果 +2。主标签 C（容错信号），满足 must_read_rules（A/B/C + 开源 + 系统/低带宽 + 分数≥10）。

2. **2501.00003**（score 20.0 / Memory-统一内存/KV / P1 / key）
   理由：P1 交集（unified memory+LLM、zero-copy+KV cache、KV cache+offloading）+8；memory 信号（unified memory/KV cache/zero-copy）命中主标签 Memory；副标签 B/A/Arch。pillar=P1。

3. **2501.00011**（score −3.0 / **已丢弃**）
   理由：纯 VLA/机器人论文（vision-language-action, robot manipulation）。原本因摘要含 “benchmarks” 误触发 `system_exception_keywords` 的 “benchmark” 而逃脱降权、且得 +3，被错误保留为 candidate。已修复：将 benchmark/throughput/latency/bandwidth 从例外词移除（它们是测量词不是系统贡献），现在正确降权 −6 + 硬件 +3 = −3，低于候选软下限被丢弃。

## 10. 测试与前端构建结果

- **Python 语法**：`ai/scorer.py / structure.py / enhance.py / filter.py / to_md/convert.py` 全部 `py_compile` 通过。
- **前端语法**：`js/app.js / settings.js / statistic.js` 全部 `node --check` 通过。
- **打分/分层 dry-run**：16 篇样本分类、pillar、分层全部符合预期（见 §7/§8/§9）。
- **Markdown 渲染**：用合成 20 字段记录跑 `convert.py`，新字段「所属 Pillar / 副标签 / 内存与 KV cache / 测量口径」均正确渲染，无 KeyError。
- **密钥扫描**：diff 中无 `sk-`/`ghp_`/`api_key`/`password`/`token` 等；无历史文件删除。
- **CI**：`run.yml` 未改动，链路安全（crawl→check_stats→scorer→filter→enhance→convert→双分支部署）。
- 注：未执行真实 LLM 调用（遵守「基础测试不花 LLM 费用」）；LLM 20 字段 schema 与兜底字典已对齐，仅待 CI 真实运行验证。

## 11. 待办 / 开放问题（Open issues）

1. **纯 survey / 模型架构类** 在某些措辞下仍可能因 `architecture` 等例外词逃脱降权（如样本 00013 得 0 分、candidate）。不影响 Top，但可后续收紧例外词口径。
2. **P1 交集命中偏多**：真实 arXiv 数据需观察交集触发率，必要时收紧 `intersection_patterns`。
3. **LLM 真实运行**未在本机执行（无 API 调用），20 字段在 CI 跑通后建议抽看 3–5 篇确认 `memory_kv / measurement / pillar` 质量。
4. 前端 `Interested Keywords` 与后端解耦是**有意设计**；若日后想打通需同步 `research_focus.yaml`。

## 12. 应维护的配置文件

**唯一需要长期维护的配置文件：`config/research_focus.yaml`**
（改 categories / pillars / tags / scoring / output 都在这里；并同步 GitHub Variable `CATEGORIES`）。
其余代码/前端/Prompt 仅在标签名或字段名变动时需同步。
维护说明见 [`RESEARCH_FOCUS.md`](./RESEARCH_FOCUS.md)。
