from pydantic import BaseModel, Field


class Structure(BaseModel):
    """Output schema: keeps original field names for frontend backward-compat, adds new fields."""

    # === Original fields (same names as before, frontend expects these) ===

    tldr: str = Field(
        default="",
        description="One-sentence TL;DR in Chinese, ≤50 characters, punchy. The original 'tldr' field name is kept for frontend compatibility."
    )

    motivation: str = Field(
        default="",
        description="What problem does this paper solve? 1-2 sentences."
    )

    method: str = Field(
        default="",
        description="Core method. For system/hardware papers: must specify hardware platform (H100/A100/FPGA/ASIC), "
                    "key technique (kernel fusion/systolic array/PagedAttention), and implementation level "
                    "(operator-level/compiler-level/system-level). 2-3 sentences."
    )

    result: str = Field(
        default="",
        description="Key quantitative results. Must include: speedup ratio (end-to-end vs operator-level), "
                    "latency/throughput/power numbers, comparison baseline (e.g. vs FlashAttention v2), "
                    "and measurement scope (single GPU / multi-node / etc)."
    )

    conclusion: str = Field(
        default="",
        description="1-sentence conclusion or takeaway message."
    )

    # === New fields (not rendered by original frontend but available in JSONL) ===

    category_tag: str = Field(
        default="支撑",
        description="Category tag: 交集 / 架构-infra / 具身 / 支撑"
    )

    why_matters: str = Field(
        default="",
        description="Why this paper matters to a researcher working on Embodied AI × AI Infra / accelerator design. 1 sentence."
    )

    deep_read: bool = Field(
        default=False,
        description="True if recommending deep read, False if skim-only"
    )

    deep_read_reason: str = Field(
        default="",
        description="Reason for the deep read recommendation or skim-only."
    )

    open_source: str = Field(
        default="",
        description="GitHub link or '未公开' if no open source code available"
    )
