import json
import argparse
import os
import random
import sys
from itertools import count


def compute_deep_read_ratio(data) -> float:
    """Compute ratio of papers recommended for deep read."""
    total = len(data)
    if total == 0:
        return 0.0
    deep = sum(1 for item in data if item.get("AI", {}).get("deep_read", False))
    return deep / total


def generate_weekly_reminder(data) -> str:
    """Generate self-check reminder if deep_read ratio < 20%."""
    ratio = compute_deep_read_ratio(data)
    if ratio >= 0.2 or len(data) < 5:
        return ""

    # Pick 2 random non-deep-read papers as forced reading candidates
    non_deep = [item for item in data if not item.get("AI", {}).get("deep_read", False)]
    if len(non_deep) < 2:
        return ""

    picks = random.sample(non_deep, min(2, len(non_deep)))
    paper_links = []
    for p in picks:
        title = p.get("title", "Unknown")
        url = p.get("abs", "#")
        paper_links.append(f"[{title[:60]}]({url})")

    reminder = f"""
> ⚠️ **每周自检提醒**
> 
> 本周建议深读的论文占比 **{ratio*100:.0f}%** (&lt;20%)。
> 可能不是因为论文质量低，而是摘要写得太顺滑造成了「已懂」错觉。
> 
> 建议抽查以下 2 篇强制精读：
> - ✅ {paper_links[0]}
> - ✅ {paper_links[1]}
>
> ---
"""
    return reminder


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=str, help="Path to the jsonline file")
    args = parser.parse_args()

    data = []
    with open(args.data, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))

    # Sort by score descending, then by intersection, then by category_tag priority
    tag_priority = {"交集": 0, "架构-infra": 1, "具身": 2, "支撑": 3}
    data.sort(key=lambda x: (
        -x.get("score", 0),
        tag_priority.get(x.get("category_tag", "支撑"), 99)
    ))

    # Group by category_tag (not arXiv category)
    tags_order = ["交集", "架构-infra", "具身", "支撑"]
    tag_groups = {}
    for tag in tags_order:
        tag_groups[tag] = [item for item in data if item.get("category_tag") == tag]

    # Build Table of Contents
    markdown = ""
    reminder = generate_weekly_reminder(data)
    if reminder:
        markdown += reminder

    markdown += "<div id=toc></div>\n\n# Table of Contents\n\n"
    for tag in tags_order:
        papers = tag_groups[tag]
        if papers:
            markdown += f"- [{tag}](#{tag}) [Total: {len(papers)}]\n"

    # Load template
    template = open(os.path.join(os.path.dirname(__file__), "paper_template.md"), "r", encoding="utf-8").read()

    # Render papers by tag
    idx = count(1)
    for tag in tags_order:
        papers = tag_groups[tag]
        if not papers:
            continue

        markdown += f"\n\n<div id='{tag}'></div>\n\n"
        markdown += f"# {tag}  [[Back]](#toc)\n\n"

        rendered = []
        for item in papers:
            ai_data = item.get("AI", {})
            if not ai_data or not isinstance(ai_data, dict):
                continue

            required_fields = ["tldr_cn", "motivation", "method", "result", "why_matters"]
            if not all(f in ai_data for f in required_fields):
                continue

            score = item.get("score", 0)
            category_tag = item.get("category_tag", "支撑")
            deep_read = ai_data.get("deep_read", False)
            deep_icon = "✅" if deep_read else "◻"
            deep_reason = ai_data.get("deep_read_reason", "")
            open_source = ai_data.get("open_source", "").strip()
            if not open_source or open_source == "None":
                open_source = "未公开"

            rendered.append(
                template.format(
                    title=item.get("title", ""),
                    authors=", ".join(item.get("authors", [])),
                    cates=", ".join(item.get("categories", [])),
                    score=f"{score:.1f}",
                    tag=category_tag,
                    tldr_cn=ai_data.get("tldr_cn", ""),
                    motivation=ai_data.get("motivation", ""),
                    method=ai_data.get("method", ""),
                    result=ai_data.get("result", ""),
                    why_matters=ai_data.get("why_matters", ""),
                    deep_icon=deep_icon,
                    deep_reason=deep_reason,
                    open_source=open_source,
                    url=item.get("abs", ""),
                    pdf=item.get("pdf", ""),
                    idx=next(idx),
                )
            )

        markdown += "\n\n".join(rendered)

    # Write output
    data_filename = os.path.basename(args.data)
    base_date = data_filename.split("_")[0]
    output_path = os.path.join(os.path.dirname(args.data), "..", f"{base_date}.md")
    output_path = os.path.abspath(output_path)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    print(f"Converted {len(data)} papers → {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
