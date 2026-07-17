# 系统说明与使用报告 · daily-arXiv-ai-enhanced

> 带宽受限边缘集群大模型分布式推理论文雷达
> 文档版本：2026-07-17 ｜ 作者：Senior Developer (高级开发工程师)

---

## 1. 系统概述

本系统是一个**自动化 arXiv 论文情报雷达**：每天定时抓取 arXiv 最新论文，按"带宽受限、多节点边缘集群（7×Jetson Thor，无 NVLink，25GbE 以太网）大模型分布式推理"这一研究定位进行打分、筛选、LLM 增强，并生成一个可交互的静态网站。

核心目标不是"尽量多抓"，而是**每天精选少量真正影响实验设计 / 研究问题 / 源码学习的论文**，并产出结构化的中文情报报告（23 个字段）。

| 项 | 值 |
|---|---|
| 仓库 | `70asunflower/daily-arXiv-ai-enhanced`（fork 自 `dw-dengwei/daily-arXiv-ai-enhanced`） |
| 站点 | GitHub Pages（从 `main` 分支根目录构建） |
| 数据分支 | `data`（仅存每日数据文件，前端按需拉取） |
| 定时 | `cron 0 1 * * *` ≈ 北京时间 09:00 |
| LLM | `deepseek-v4-flash`，base_url `https://api.deepseek.com` |
| 语言 | 默认中文（`LANGUAGE` 变量控制） |

---

## 2. 系统架构

```
                         GitHub Actions (run.yml, 每日 09:00 UTC+8)
   ┌──────────────────────────────────────────────────────────────────┐
   │ ① Crawl   daily_arxiv/scrapy  → data/<date>.jsonl                  │
   │ ② Dedup   check_stats.py (比对近 7 天, 删重复)                       │
   │ ③ Score   ai/scorer.py  → *_scored.jsonl  (四支柱 / 11 标签 / 降权) │
   │ ④ Filter  ai/filter.py  → *_top15.jsonl  (must_read / key / cand) │
   │ ⑤ Enhance ai/enhance.py → *_AI_enhanced_<lang>.jsonl (LLM 23字段)  │
   │ ⑥ Convert to_md/convert.py → <date>.md (本地产物, 见 §11)          │
   └───────────────┬───────────────────────────┬──────────────────────┘
                   │ git push origin main        │ git push origin data
                   ▼                             ▼
            main 分支 (HTML/CSS/JS + 流水线代码)   data 分支 (*.jsonl + assets/file-list.txt)
                   │                             │
                   │ GitHub Pages 自动发布        │ 前端 fetch raw.githubusercontent.com/.../data/...
                   ▼                             ▼
            公开静态站点 (index.html)      ───────► 浏览器加载当日 JSONL 并渲染
```

**关键设计：代码与数据分离。** `main` 分支承载站点与流水线代码；`data` 分支只存每日数据文件。前端通过 `js/data-config.js` 中注入的仓库信息，从 `data` 分支拉取对应日期的 JSONL，实现"代码更新"与"数据更新"互不阻塞。

> ⚠️ **部署前提**：本仓库 `run.yml` 内**没有** `actions/deploy-pages` 步骤，依赖仓库 **Settings → Pages → Source = Deploy from a branch → `main` / (root)** 在每次 push `main` 时自动发布。请确认该设置已开启，否则站点不会更新。

---

## 3. 端到端数据流

| 步骤 | 脚本 / 动作 | 输入 → 输出 | 失败处理 |
|---|---|---|---|
| ① 抓取 | `daily_arxiv` (Scrapy) | arXiv `new` 列表 → `data/<date>.jsonl` | 无文件 → 后续 no_data |
| ② 去重 | `check_stats.py` | 比对近 7 天 id，删除重复 | 退出码 0/1/2 → 决定是否继续 |
| ③ 打分 | `ai/scorer.py` | `*.jsonl` → `*_scored.jsonl` | — |
| ④ 筛选 | `ai/filter.py` | `*_scored.jsonl` → `*_top15.jsonl` | — |
| ⑤ 增强 | `ai/enhance.py` | `*_top15.jsonl` → `*_AI_enhanced_<lang>.jsonl` | >50% 全默认 → `sys.exit(1)` 中止 |
| ⑥ 转 MD | `to_md/convert.py` | JSONL → `<date>.md`（本地产物） | — |
| ⑦ 发布 | `run.yml` | 推送 `main` + `data` 分支 | 3 次重试 |

去重逻辑（②）：若当日论文与近 7 天历史**完全重复**（无新内容），工作流以 `no_new_content` 提前结束，不再跑 ③④⑤⑥，避免重复发布。

---

## 4. 目录结构与模块职责

```
daily-arXiv-ai-enhanced/
├── .github/workflows/run.yml     # CI/CD 全流程编排
├── ai/
│   ├── scorer.py                 # 关键词打分 + 11 标签分类 + 降权
│   ├── filter.py                 # 按分数筛选顶层论文 + 三级分层(tier)
│   ├── enhance.py                # 调用 LLM 产出 23 字段结构化情报
│   ├── structure.py              # LLM 输出 Pydantic schema (23 字段)
│   ├── template.txt              # 用户提示词（含 {content} 等占位符）
│   └── system.txt                # 系统提示词（研究定位 / 字段填写规范）
├── to_md/
│   ├── convert.py                # JSONL → Markdown 报告
│   └── paper_template.md         # Markdown 模板（29 个 {key} 占位符）
├── daily_arxiv/                  # Scrapy 爬虫（arxiv.py 抓取 new 列表）
├── config/research_focus.yaml    # ★ 单一事实来源：研究定位/分类/四支柱/打分/降权
├── js/                           # 前端：app.js(主逻辑) / auth.js / data-config.js / statistic.js / settings.js
├── css/ assets/                  # 样式与静态资源（含自托管 flatpickr）
├── index.html login.html settings.html statistic.html  # 页面
├── sw.js                         # Service Worker（导航 network-first，数据 pass-through）
├── pyproject.toml uv.lock        # Python 依赖（uv 管理）
└── run.sh                        # 本地调试脚本（crawl + dedup + enhance + convert）
```

**改动中枢：`config/research_focus.yaml`** —— 评分关键词、四支柱、11 标签、降权规则、每日分层阈值全部集中在此。修改研究方向时优先改这里，避免与 Prompt / 前端 / 工作流彼此脱节。

---

## 5. 评分与分类体系

### 5.1 四支柱（Pillars）
| 支柱 | 关注点 | 标签 |
|---|---|---|
| P1 | 边缘 SoC 分布式推理与内存 | A, Memory |
| P2 | 受限/动态网络下的通信优化与弹性恢复 | B, C |
| P3 | MoE 与分布式投机解码 | MoE, Spec |
| P4 | 能效与资源管理 | Energy |

### 5.2 11 个论文标签（主标签 + 副标签）
`Memory / MoE / Spec / Energy / C / B / A / Infra / Arch / Space / Background`
优先级：`Memory > MoE > Spec > Energy > C > B > A > Arch > Infra > Space > Background`（技术细分优先于粗粒度 A/B/C，凸显研究方向）。

### 5.3 打分规则（可解释、防堆叠）
- P1 概念交集命中（宽词单独不计）：**+8 且强制保留**
- P2 通信优化 / 容错：**+5** 每组
- 强系统（vLLM/SGLang/NCCL/Megatron/Ray）：**+4** 每个（封顶 2）
- 硬件+互联+benchmark：**+3**；MoE/MTP+多节点通信调度：**+3**
- 开源 **+2**；可信量化结果 **+2**；架构+LLM **+2**；能效(功耗+性能) **+2**
- 降权：纯 VLA/机器人 **−6**、纯精度 **−5**、纯训练 **−4**、纯卸载 **−3**、综述 **−2**（除非命中系统贡献例外词）
- 关键词总分封顶 45；低于 `hard_score_threshold`(−100) 直接丢弃

### 5.4 每日三级分层（tier）
| 层级 | 字段 | 上限 | 进入条件 |
|---|---|---|---|
| 建议精读 | `must_read` | 2 | 命中 A/B/C + 可复现开源 + 系统/低带宽相关 + 分数 ≥ 10 |
| 今日重点 | `key` | 5 | 按分数取 Top |
| 今日候选 | `candidate` | 12 | 次优相关 |

分层是规则信号（filter.py），与 LLM 的 `deep_read` 信号是两个独立维度，前端分别渲染便于人工核对矛盾。

---

## 6. LLM 增强（23 字段情报）

`enhance.py` 直接调用 OpenAI 兼容 SDK（`response_format=json_object`，`temperature=0`，`max_tokens=4096`，并对 DeepSeek 推理模型附加 `extra_body={"thinking":{"type":"disabled"}}`）。Prompt 由 `system.txt`（研究定位 + 字段规范）+ `template.txt`（论文上下文）拼成。

结构化输出 schema（`structure.py`，23 字段）：
`tldr, motivation, method, result, conclusion, ai_category_tag, sub_tags, pillar, problem, hardware, comm_mechanism, memory_kv, key_results, baseline, measurement, abc_tag, value_7xthor, infra_assumption, nvlink_free_holds, differentiation, deep_read(bool), deep_read_reason, open_source`

**健壮性机制：**
- JSON 修复：`_repair_and_parse` 处理 ```json``` 围栏、尾随逗号、reasoning_content 兜底。
- 字段纠正：`_coerce_field` 把 `deep_read` 归一成 bool。
- **Fail-loud**：若 >50% 论文的 `tldr == "摘要生成失败"`（即 LLM 整体失败），`enhance.py` 直接 `sys.exit(1)` 中止，**绝不发布空壳报告**（这是此前"数据悄无声息腐烂"根因的防护）。
- 重试：单篇最多 3 次；API key 等凭据来自 GitHub Secrets，不落前端。

---

## 7. 前端站点

- **数据来源**：`index.html` 加载 `js/app.js`，按 `js/data-config.js`（CI 注入仓库信息）从 `data` 分支拉取 `data/<date>_AI_enhanced_<lang>.jsonl`，解析后按 11 标签分组渲染。
- **交互**：日期选择器（flatpickr，自托管非 CDN）、关键词/作者过滤标签、全文搜索、分级徽章、PDF 预览、键盘导航（←/→/空格随机）、Kimi 对话预填。
- **多语言**：根据 `file-list.txt` 中可用语言自动选择（默认中文）。
- **认证**：`login.html` + `auth.js` 提供**客户端密码门禁**（SHA-256 比对，常量时间比较）。⚠️ 详见 §10 安全说明——此为混淆级防护，非真正机密保护。
- **缓存**：`sw.js` 导航请求 network-first，静态资源 stale-while-revalidate，跨域数据（raw.githubusercontent）pass-through。部署破坏性改动时记得 bump `CACHE_VERSION`。

---

## 8. 配置指南

### 8.1 GitHub Secrets（必填）
| Secret | 说明 |
|---|---|
| `OPENAI_API_KEY` | LLM API Key（当前为 DeepSeek key） |
| `OPENAI_BASE_URL` | `https://api.deepseek.com` |
| `TOKEN_GITHUB` | 用于 `enhance.py` 校验论文开源链接 star/更新时间（**可选但建议**，否则走未认证 API 限流） |
| `ACCESS_PASSWORD` | 可选；设置后启用站点密码门禁 |

### 8.2 GitHub Variables（仓库 Settings → Variables）
| Var | 默认值/建议 | 说明 |
|---|---|---|
| `CATEGORIES` | `cs.DC,cs.AR,cs.PF,cs.NI,cs.OS,cs.LG,cs.ET` | **必须与 `research_focus.yaml` 的 categories 一致** |
| `LANGUAGE` | `Chinese` | `Chinese` / `English` |
| `MODEL_NAME` | `deepseek-v4-flash` | |
| `EMAIL` / `NAME` | 提交用身份 | |

> ⚠️ 若 `CATEGORIES` 变量为空或缺失，爬虫会静默抓到 0 篇（已修复为回退核心分类，但强烈建议显式设置）。

### 8.3 研究定位调参
改 `config/research_focus.yaml`：
- 想换抓取方向 → `categories`
- 想改关键词/降权 → `tags` / `downweight`（新增弱词务必同步 `weak_keyword_buckets`，否则被静默忽略并打印 WARNING）
- 想改每日产出数量/门槛 → `output`

---

## 9. 本地运行

前置：Python ≥ 3.12、`uv`、网络可访问 arXiv 与 LLM API。

```bash
# 1. 安装依赖
uv sync

# 2. 配置环境变量
export OPENAI_API_KEY="sk-..." 
export OPENAI_BASE_URL="https://api.deepseek.com"
export MODEL_NAME="deepseek-v4-flash"
export LANGUAGE="Chinese"
export CATEGORIES="cs.DC,cs.AR,cs.PF,cs.NI,cs.OS,cs.LG,cs.ET"
# export TOKEN_GITHUB="ghp_..."   # 可选

# 3. 一键本地调试（crawl + dedup + enhance + convert）
bash run.sh
```

也可分步手动跑（见 `run.sh` 内部步骤）：`scrapy crawl arxiv` → `python ai/scorer.py` → `python ai/filter.py` → `python ai/enhance.py --data ...` → `python to_md/convert.py --data ...`。

> 注：`run.sh` 的 `CATEGORIES` 默认值已与研究方向对齐（不再使用上游遗留的 `cs.CV`）。

---

## 10. 安全说明

- **客户端密码门禁是"混淆级"防护，不是机密保护**。`auth.js` 中 SHA-256 哈希与比对逻辑均随静态 JS 公开，任何人都可读到；它只挡住随意围观，不要用于保护真正敏感内容。若需真实访问控制，应改用服务端鉴权。
- **API Key 安全**：`OPENAI_API_KEY` 仅存在于 GitHub Secrets 与 CI 运行环境，前端只拉取公开的 `data` 分支 JSONL，不接触任何密钥。
- **Fork 自托管**：本仓库已修复 fork 兼容性问题（见 §12）——`data-config.js` / `auth-config.js` 注入与前端 `DATA_CONFIG` 读取现在尊重fork后的仓库信息，GitHub 统计也按注入的 owner/name 拉取。

---

## 11. 已知设计取舍（非缺陷）

1. **`convert.py` 生成的 Markdown 未被部署。** 前端直接消费 `data` 分支的 JSONL，`<date>.md` 仅为本地/人工阅读产物，不会进入 `data` 分支，也不会被站点渲染。如需发布 Markdown 版报告，需要在 `run.yml` 中把 `to_md/*.md` 也复制到 `data` 分支（当前 CI 的 commit 步骤已显式排除它，避免污染 `main`）。
2. **串行增强**。`enhance.py` 默认 `max_workers=1`（串行），以降低 LLM API 限流风险；Top15 规模下耗时可控。
3. **`hard_score_threshold = -100`** 实际几乎不丢弃论文（噪声主要靠降权规则处理），filter 本质是按分数取 Top N。

---

## 12. 本次严格审查发现与修复

### 12.1 本轮（2026-07-17）修复的 RED / 设计问题

| # | 严重度 | 位置 | 问题 | 修复 |
|---|---|---|---|---|
| R1 | 🔴 RED | `ai/enhance.py` | `template.format(...)` 把原始 arXiv 摘要作为 `content` 传入；摘要中常见的 LaTeX 花括号（`\{0,1\}^n`、`$\mathbb{R}$`）会被 `str.format` 当作格式字段而抛 `KeyError`/`IndexError`，导致该篇被静默降级为全默认占位（甚至触发 >50% 中止整轮） | 改用花括号安全的 `.replace()` 链式填充 |
| R2 | 🔴 RED | `run.yml` + `js/auth-config.js` / `js/data-config.js` | 工作流 `sed` 目标是 `PLACEHOLDER_PASSWORD_HASH` / `PLACEHOLDER_REPO_OWNER` 等占位符，但 JS 文件里实际是 `DISABLED_NO_PASSWORD_SET_IN_SECRETS` / `70asunflower` —— **占位符永远不匹配**，导致密码门禁从未真正启用、fork 的仓库信息从未被注入 | `sed` 改为匹配文件中的真实默认值（`DISABLED_...` 与 `70asunflower`） |
| R3 | 🔴 RED | `js/app.js`、`statistic.js`、`settings.js` | 前端硬编码 `70asunflower` 并强制覆盖 `DATA_CONFIG`（除非已等于 70asunflower），导致即便 CI 正确注入 fork 信息也会被覆盖回原仓库；GitHub 统计也写死原仓库 | 改为仅在 `DATA_CONFIG` 缺失时回退；统计 URL 改用注入的 `repoOwner/repoName` |
| D1 | 🟡 | `daily_arxiv/.../arxiv.py`、`run.sh` | 爬虫默认分类是上游遗留的 `cs.CV`（与研究定位不符）；且 `CATEGORIES` 变量为空时静默抓 0 篇 | 默认回退为核心分类 `cs.DC,cs.AR,cs.PF,cs.NI,cs.OS,cs.LG,cs.ET`（`os.environ.get(... ) or ...` 同时覆盖空字符串） |
| D2 | 🟡 | `to_md/convert.py`、`run.yml` | `convert.py` 用相对路径 `open("paper_template.md")`，从仓库根目录运行时失败；且生成的 `.md` 会被误提交到 `main` | 改用 `os.path.join(_SCRIPT_DIR, ...)`；CI commit 步骤显式 `git reset to_md/*.md` |
| D3 | 🟡 | `check_stats.py` | 去重用 `datetime.now()`（本地时区），而抓取用 `date -u`（UTC），本地跨午夜运行时可能差一天 | 改用 `datetime.now(timezone.utc)` 与抓取保持一致 |

### 12.2 上一轮（2026-07-16）已修复的要点（回顾）
- 移除 `langchain`，`enhance.py` 改为直接调用 `openai` SDK（修复了 langchain 不能透传 `response_format`/`thinking`/`max_tokens` 导致的**全部占位符静默失败**）。
- `scorer.py` 弱词→扣分桶改为从 `research_focus.yaml` 的 `weak_keyword_buckets` 读取（修复配置漂移）。
- `convert.py` 用花括号安全的 `_render()` 替换脆弱 `.format()`。
- `filter.py` 去重按 arXiv `id`（非对象身份 `id(p)`），删除恒空的"forced P0"分支。
- `auth.js` 密码比对改为常量时间。
- `uv.lock` 重建（去掉 langchain 及其传递依赖，显式钉 openai/pydantic/requests/pyyaml）。
- `run.yml` 修正误导头部注释；AI 增强步骤补 `export TOKEN_GITHUB`。

### 12.3 验证
- 全部 Python 文件 `py_compile` 通过；`run.yml` / `research_focus.yaml` YAML 校验通过。
- `enhance.py` 花括号填充单测：含 `\{0,1\}^n`、`$\mathbb{R}$` 的摘要不再崩溃，内容完整保留。
- `convert.py` 从仓库根目录运行成功（修复前会因相对路径失败）。

---

## 13. 后续建议
1. （可选）若希望发布 Markdown 报告，在 `run.yml` 把 `to_md/*.md` 一并复制进 `data` 分支并加入 `file-list.txt`。
2. （可选）将爬虫默认分类直接读取 `research_focus.yaml`，彻底消除"变量与配置不一致"隐患。
3. （安全）若站点内容需要真正访问控制，引入服务端鉴权，替代客户端哈希门禁。
4. 部署破坏性前端改动时记得 bump `sw.js` 的 `CACHE_VERSION`。
