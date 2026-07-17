import json
import argparse
import os
import re
from itertools import count

# 新分类体系（与 config/research_focus.yaml 对齐 — 11 个论文标签）
TAXONOMY_ORDER = ['Memory', 'MoE', 'Spec', 'Energy', 'C', 'B', 'A', 'Infra', 'Arch', 'Space', 'Background']
TAXONOMY_TAGS = {
    'Memory': 'Memory-统一内存/KV',
    'MoE': 'MoE-专家并行',
    'Spec': 'Spec-MTP/投机解码',
    'Energy': 'Energy-能效资源',
    'C': 'C-容错与弹性',
    'B': 'B-通信与调度',
    'A': 'A-测量与瓶颈',
    'Infra': 'Infra-推理引擎',
    'Arch': 'Arch-体系结构',
    'Space': 'Space-场景延伸',
    'Background': 'Background-支撑',
}
LEGACY_TAG_MAP = {
    'Intersection': 'B',
    'Arch-Infra': 'Infra',
    'Embodied': 'Background',
    'Support': 'Background',
}
TIER_LABELS = {'must_read': '建议精读', 'key': '今日重点', 'candidate': '今日候选'}


def resolve_code(item):
    c = item.get('cat_code')
    if c and c in TAXONOMY_TAGS:
        return c
    ct = item.get('category_tag')
    if ct and ct in LEGACY_TAG_MAP:
        return LEGACY_TAG_MAP[ct]
    for k, v in TAXONOMY_TAGS.items():
        if v == ct:
            return k
    return 'Background'


def _render(template: str, fields: dict) -> str:
    """Brace-safe template substitution.

    Only replaces known ``{key}`` placeholders; any other literal ``{``/``}``
    in the template (e.g. markdown code blocks) or in the values is left
    untouched. This avoids str.format() crashing on stray braces in AI content.
    Keys are sorted longest-first so a key that is a prefix of another still
    matches correctly.
    """
    keys = sorted(fields.keys(), key=len, reverse=True)
    pattern = re.compile(r"\{(" + "|".join(re.escape(k) for k in keys) + r")\}")
    return pattern.sub(lambda m: str(fields[m.group(1)]), template)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=str, help="Path to the AI-enhanced jsonline file")
    args = parser.parse_args()

    data = []
    with open(args.data, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))

    # 按新分类体系（cat_code）分组；旧数据按 legacy 映射回退
    groups = {}
    order_index = {c: i for i, c in enumerate(TAXONOMY_ORDER)}
    for item in data:
        code = resolve_code(item)
        groups.setdefault(code, []).append(item)

    sorted_codes = sorted(groups.keys(), key=lambda c: order_index.get(c, 999))

    # 组内排序：建议精读 > 今日重点 > 今日候选 > 其它；同级按分数降序
    tier_rank = {'must_read': 0, 'key': 1, 'candidate': 2, '': 3, None: 3}
    for code in groups:
        groups[code].sort(key=lambda x: (tier_rank.get(x.get('tier'), 3), -x.get('score', 0)))

    template = open("paper_template.md", "r", encoding="utf-8").read()

    markdown = "# 论文雷达 / Paper Radar\n\n"
    markdown += "## 目录 / Contents\n\n"
    for code in sorted_codes:
        tag = TAXONOMY_TAGS.get(code, code)
        cnt = len(groups[code])
        markdown += f"- [{tag}](#{code}) [{cnt}]\n"
    markdown += "\n---\n\n"

    idx = count(1)
    for code in sorted_codes:
        tag = TAXONOMY_TAGS.get(code, code)
        markdown += f'\n## {tag} <a id="{code}"></a>\n\n'
        for item in groups[code]:
            ai = item.get('AI')
            if not isinstance(ai, dict):
                continue
            score = item.get('score', 0)
            cat_tag = item.get('category_tag', '')
            tier = item.get('tier') or ''
            tier_label = TIER_LABELS.get(tier, '')
            deep_icon = ' ✅' if ai.get('deep_read') else ''
            tldr = ai.get('tldr', '')
            sub_tags = ', '.join(item.get('sub_tags', []) or [])

            fields = {
                "idx": next(idx),
                "title": item.get('title', ''),
                "authors": ', '.join(item.get('authors', []) or []),
                "url": item.get('abs') or item.get('pdf') or f"https://arxiv.org/abs/{item.get('id', '')}",
                "cat": cat_tag,
                "tier": tier_label,
                "score": f"{score:.1f}",
                "pillar": item.get('pillar', ''),
                "sub_tags": sub_tags,
                "tldr": tldr + deep_icon,
                "problem": ai.get('problem', ''),
                "hardware": ai.get('hardware', ''),
                "method": ai.get('method', ''),
                "comm_mechanism": ai.get('comm_mechanism', ''),
                "memory_kv": ai.get('memory_kv', ''),
                "key_results": ai.get('key_results', ''),
                "baseline": ai.get('baseline', ''),
                "measurement": ai.get('measurement', ''),
                "abc_tag": ai.get('abc_tag', ''),
                "value_7xthor": ai.get('value_7xthor', ''),
                "infra_assumption": ai.get('infra_assumption', ''),
                "nvlink_free_holds": ai.get('nvlink_free_holds', ''),
                "differentiation": ai.get('differentiation', ''),
                "deep_read": ('✅ 建议精读' if ai.get('deep_read') else '—'),
                "open_source": ai.get('open_source', '未公开'),
                "motivation": ai.get('motivation', ''),
                "result": ai.get('result', ''),
                "conclusion": ai.get('conclusion', ''),
                # M1: deep_read (LLM 信号) 与 tier (规则信号) 是两个独立维度，可能不一致；
                # 这里分别渲染，互不覆盖，便于人工核对两者矛盾。
                "summary": item.get('summary', ''),
            }
            markdown += _render(template, fields)

    base = os.path.basename(args.data)
    name = base.split('_AI_enhanced_')[0].rsplit('.jsonl', 1)[0]
    out = name + '.md'
    with open(out, "w", encoding="utf-8") as f:
        f.write(markdown)
    print(f"Converted {len(data)} papers -> {out}")
