from pydantic import BaseModel, Field


class Structure(BaseModel):
    """9-field structured output for personalized paper triage."""

    # Category tag: 交集 / 架构-infra / 具身 / 支撑
    category_tag: str = Field(
        default="支撑",
        description="Category tag: 交集 (embodied×infra) / 架构-infra / 具身 / 支撑"
    )

    # One-line TL;DR in Chinese (≤50 chars)
    tldr_cn: str = Field(
        default="",
        description="One-sentence TL;DR in Chinese, ≤50 characters, punchy"
    )

    # What problem does this solve (1-2 sentences)
    motivation: str = Field(
        default="",
        description="What problem does this paper solve? 1-2 sentences"
    )

    # Core method (2-3 sentences; for system/hardware papers, MUST mention hardware platform and key techniques)
    method: str = Field(
        default="",
        description="Core method. For system/hardware papers: must specify hardware platform (H100/A100/FPGA/ASIC), "
                    "key technique (kernel fusion/systolic array/PagedAttention), and implementation level "
                    "(operator-level/compiler-level/system-level). 2-3 sentences."
    )

    # Key results (quantified: speedup/latency/power + baseline + measurement scope)
    result: str = Field(
        default="",
        description="Key quantitative results. Must include: speedup ratio (end-to-end vs operator-level), "
                    "latency/throughput/power numbers, comparison baseline (e.g. vs FlashAttention v2), "
                    "and measurement scope (single GPU / multi-node / etc)."
    )

    # Why this matters to me (1 sentence, personalized to the user's context)
    why_matters: str = Field(
        default="",
        description="Why this paper matters to a researcher working on Embodied AI × AI Infra / accelerator design. "
                    "1 sentence: does it help with VLA serving, edge inference for robots, kernel optimization, "
                    "or chip architecture? Be specific."
    )

    # Deep read recommendation
    deep_read: bool = Field(
        default=False,
        description="true if recommending deep read, false if skim-only"
    )
    deep_read_reason: str = Field(
        default="",
        description="Reason for the deep read recommendation (or reason for skim-only). "
                    "Mention which specific criterion triggered the recommendation."
    )

    # Open source code link if available
    open_source: str = Field(
        default="",
        description="GitHub link or '未公开' if no open source code available"
    )
