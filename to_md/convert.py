import json
import argparse
import os
from itertools import count

# 新分类体系（与 config/research_focus.yaml 对齐）
TAXONOMY_ORDER = ['A', 'B', 'C', 'Infra', 'Arch', 'Space', 'Background']
TAXONOMY_TAGS = {
    'A': 'A-测量与瓶颈',
    'B': 'B-通信与调度',
    'C': 'C-容错与弹性',
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

            markdown += template.format(
                idx=next(idx),
                title=item.get('title', ''),
                authors=', '.join(item.get('authors', []) or []),
                url=item.get('abs') or item.get('pdf') or f"https://arxiv.org/abs/{item.get('id', '')}",
                cat=cat_tag,
                tier=tier_label,
                score=f"{score:.1f}",
                tldr=tldr + deep_icon,
                problem=ai.get('problem', ''),
                hardware=ai.get('hardware', ''),
                method=ai.get('method', ''),
                comm_mechanism=ai.get('comm_mechanism', ''),
                key_results=ai.get('key_results', ''),
                baseline=ai.get('baseline', ''),
                abc_tag=ai.get('abc_tag', ''),
                value_7xthor=ai.get('value_7xthor', ''),
                infra_assumption=ai.get('infra_assumption', ''),
                nvlink_free_holds=ai.get('nvlink_free_holds', ''),
                differentiation=ai.get('differentiation', ''),
                deep_read=('✅ 建议精读' if ai.get('deep_read') else '—'),
                open_source=ai.get('open_source', '未公开'),
                motivation=ai.get('motivation', ''),
                result=ai.get('result', ''),
                conclusion=ai.get('conclusion', ''),
                summary=item.get('summary', '')
            )

    base = os.path.basename(args.data)
    name = base.split('_AI_enhanced_')[0].rsplit('.jsonl', 1)[0]
    out = name + '.md'
    with open(out, "w", encoding="utf-8") as f:
        f.write(markdown)
    print(f"Converted {len(data)} papers -> {out}")
