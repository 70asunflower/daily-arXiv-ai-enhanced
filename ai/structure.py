from pydantic import BaseModel, Field


class Structure(BaseModel):
    """Output schema for the 20-field paper intelligence report.

    Field names are kept mostly stable for frontend/markdown backward-compat:
    tldr / motivation / method / result / conclusion are rendered by the
    existing frontend and convert.py. New fields (problem, hardware, comm_mechanism,
    memory_kv, key_results, baseline, measurement, abc_tag, pillar, value_7xthor,
    infra_assumption, nvlink_free_holds, differentiation, sub_tags, open_source) are
    available in the JSONL and rendered in the markdown where present.
    """

    # === Core rendered fields (frontend + markdown) ===
    tldr: str = Field(
        default="",
        description="一句话 TL;DR（中文，≤50 字，精炼）。仍保留字段名 tldr 以兼容前端。",
    )
    motivation: str = Field(
        default="",
        description="研究问题：论文要解决什么问题？1-2 句。",
    )
    method: str = Field(
        default="",
        description="核心方法。系统/硬件论文必须写明硬件平台（Jetson Thor/A100/H100/FPGA/ASIC）、"
                    "关键技术（通信压缩/分区/overlap/KV迁移/量化）、实现层级（算子/编译/系统）。2-3 句。",
    )
    result: str = Field(
        default="",
        description="关键量化结果：吞吐、TTFT、TPOT、尾延迟、带宽、通信量、扩展效率、能效、恢复时间；"
                    "必须给出对比基线与测量口径。禁止“性能提升”这类空话。",
    )
    conclusion: str = Field(
        default="",
        description="1 句结论或一句话 takeaway。",
    )

    # === New intelligence fields (17-field report) ===
    ai_category_tag: str = Field(
        default="Background-支撑",
        description="主类别（由 scorer 输入，取值之一：A-测量与瓶颈 / B-通信与调度 / "
                    "C-容错与弹性 / Memory-统一内存KV / MoE-专家并行 / Spec-MTP投机解码 / "
                    "Energy-能效资源 / Infra-推理引擎 / Arch-体系结构 / Space-场景延伸 / Background-支撑）",
    )
    pillar: str = Field(
        default="Background",
        description="所属 Pillar（沿用 scorer 输入：P1 边缘SoC分布式推理与内存 / "
                    "P2 受限动态网络通信优化与弹性恢复 / P3 MoE与分布式投机解码 / "
                    "P4 能耗与资源管理 / Cross 跨支柱 Infra-Arch-Space / Background）。"
                    "一般直接沿用输入值，不要自行改写。",
    )
    sub_tags: str = Field(
        default="",
        description="副标签（逗号分隔的短代码，如 B,Arch；多个类别命中时的次要类别）",
    )
    problem: str = Field(
        default="",
        description="要解决的问题（与 motivation 互补：更聚焦实验/系统层面的 gap）",
    )
    hardware: str = Field(
        default="",
        description="系统与硬件环境：节点数、GPU/加速器型号、互联（以太网/25GbE/NVLink 有无）、"
                    "内存/带宽配置。论文摘要未明确则写“论文摘要未明确”。",
    )
    comm_mechanism: str = Field(
        default="",
        description="并行/通信/调度/容错机制：TP/PP/混合并行、collective、压缩、overlap、"
                    "KV 迁移/卸载、prefill/decode 分离、容错/恢复策略。无则写“论文摘要未明确”。",
    )
    memory_kv: str = Field(
        default="",
        description="内存与 KV cache 机制：显存/统一内存占用、KV cache 量化/分页/卸载、"
                    "PagedAttention、KV 压缩、KV 跨节点迁移与复用、上下文长度对内存压力的影响。"
                    "摘要未明确写“论文摘要未明确”。",
    )
    key_results: str = Field(
        default="",
        description="关键量化结果（结构化列出，含单位与口径）",
    )
    baseline: str = Field(
        default="",
        description="对比基线与方法 + 测量口径（如 vs vLLM / vs Megatron，单节点/多节点）",
    )
    measurement: str = Field(
        default="",
        description="测量口径：实验配置、负载/数据集、指标定义（吞吐 token/s、TTFT、TPOT、"
                    "尾延迟 p99、带宽利用率、扩展效率）、重复次数与置信区间。务必保留论文原文数字与单位，"
                    "不要泛化。摘要未明确写“论文摘要未明确”。",
    )
    abc_tag: str = Field(
        default="",
        description="对应 A/B/C 哪一项（A 测量与瓶颈 / B 通信与调度 / C 容错弹性），或 Background",
    )
    value_7xthor: str = Field(
        default="",
        description="对 7×Jetson Thor 课题的直接启发：哪些变量/方法可复现或改造",
    )
    infra_assumption: str = Field(
        default="",
        description="依赖的数据中心假设（如高带宽节点间、NVLink、充足内存），论文摘要未明确写“论文摘要未明确”",
    )
    nvlink_free_holds: str = Field(
        default="",
        description="放到无 NVLink、受限以太网环境下是否仍然成立？给出判断与原因",
    )
    differentiation: str = Field(
        default="",
        description="我的可能差异化研究点（结合 A/B/C 与 7×Thor 约束）",
    )
    deep_read: bool = Field(
        default=False,
        description="是否建议精读（True/False），并见于 deep_read_reason 说明",
    )
    deep_read_reason: str = Field(
        default="",
        description="建议精读/略读的理由",
    )
    open_source: str = Field(
        default="",
        description="开源代码链接（github.com/...），否则写“未公开”",
    )
