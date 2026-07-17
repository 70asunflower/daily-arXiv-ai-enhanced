"""
Daily triage filter  (research_focus.yaml driven)

Reads scored JSONL, applies the hard-score threshold, then assigns every
surviving paper to ONE of three daily tiers:

  * must_read  (建议精读)  -- at most output.must_read (default 2)
  * key        (今日重点)  -- at most output.key_papers (default 5)
  * candidate  (今日候选)  -- at most output.candidate_papers (default 12)

Selection rules
---------------
1. Drop papers with score < hard_score_threshold (pure noise).
2. P1 intersection papers are always kept (force-include) even if below
   the soft ordering, but still subject to the hard threshold.
3. must_read: highest-scored papers that satisfy must_read_rules
   (main category in A/B/C, reproducible open-source, system/low-bandwidth
   relevance, score >= min_score). Capped at output.must_read.
4. key: top scoring papers by score (includes must_read ones).
5. candidate: next best related papers (score >= soft_floor, default 0), excluding
   those already in key. Capped at output.candidate_papers.
6. Never pad tiers with weak papers; if the day is thin, emit fewer.

Output keeps the `_top15.jsonl` filename so the existing workflow step
(`python filter.py ... _top15.jsonl` -> enhance.py) keeps working.
Each record gets a `tier` field: "must_read" | "key" | "candidate".
"""

import json
import sys
import os
import yaml
from typing import Dict, List


CONFIG_NAME = "research_focus.yaml"


def load_config() -> Dict:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "..", "config", CONFIG_NAME)
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {
        "output": {"key_papers": 5, "candidate_papers": 12, "must_read": 2,
                   "hard_score_threshold": -100},
        "must_read_rules": {"require_main_category": ["A", "B", "C"],
                             "require_reproducible": True,
                             "require_system_or_lowbandwidth": True,
                             "min_score": 10},
    }


def _satisfies_must_read(item: Dict, rules: Dict) -> bool:
    if item.get("score", 0) < rules.get("min_score", 10):
        return False
    if item.get("cat_code") not in rules.get("require_main_category", ["A", "B", "C"]):
        return False
    if rules.get("require_reproducible", True) and not item.get("open_source_hit", False):
        return False
    if rules.get("require_system_or_lowbandwidth", True) and not item.get("system_or_lowbw_hit", False):
        return False
    return True


def filter_papers(scored: List[Dict], cfg: Dict) -> List[Dict]:
    out = cfg.get("output", {})
    hard = out.get("hard_score_threshold", -100)
    n_key = out.get("key_papers", 5)
    n_cand = out.get("candidate_papers", 12)
    n_must = out.get("must_read", 2)
    rules = cfg.get("must_read_rules", {})

    # 1. hard threshold
    # 交集论文的 P1 +8 已使其分数高于 hard 阈值；文档约定交集仍受 hard 阈值约束，
    # 因此无需“强制保留低于阈值的论文”（原 forced 分支对正常阈值恒为空，属死代码）。
    # 去重按 arXiv id（稳定值），而非 Python 对象身份 id(p)——后者在论文以不同 dict
    # 对象出现（如重新解析 JSONL）时会漏判重复。
    seen_ids = set()
    survivors = []
    for p in scored:
        if p.get("score", 0) < hard:
            continue
        pid = p.get("id")
        if pid is not None and pid in seen_ids:
            continue
        if pid is not None:
            seen_ids.add(pid)
        survivors.append(p)

    if not survivors:
        return []

    # sort by score desc (stable)
    survivors.sort(key=lambda x: -x.get("score", 0))

    result: List[Dict] = []
    used_ids = set()

    def take(p):
        uid = p.get("id")
        if uid in used_ids:
            return False
        used_ids.add(uid)
        result.append(p)
        return True

    # 3. must_read
    must_pool = [p for p in survivors if _satisfies_must_read(p, rules)]
    for p in must_pool[:n_must]:
        p["tier"] = "must_read"
        take(p)

    # 4. key (top by score, includes any remaining must_read candidates not yet taken)
    for p in survivors:
        if len([r for r in result if r.get("tier") == "key" or r.get("tier") == "must_read"]) >= n_key:
            break
        if p.get("id") in used_ids:
            continue
        p["tier"] = "key"
        take(p)

    # 5. candidate (next best, related, not already taken)
    soft_floor = 0  # anything that survived the hard threshold is "related enough"
    for p in survivors:
        if len([r for r in result if r.get("tier") == "candidate"]) >= n_cand:
            break
        if p.get("id") in used_ids:
            continue
        if p.get("score", 0) < soft_floor:
            continue
        p["tier"] = "candidate"
        take(p)

    # final order: must_read, key, candidate (each by score desc)
    order = {"must_read": 0, "key": 1, "candidate": 2}
    result.sort(key=lambda x: (order.get(x.get("tier"), 3), -x.get("score", 0)))
    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: python filter.py <scored.jsonl> [output.jsonl]", file=sys.stderr)
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else input_path.replace("_scored.jsonl", "_top15.jsonl")

    config = load_config()
    data = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))

    filtered = filter_papers(data, config)

    with open(output_path, "w", encoding="utf-8") as f:
        for item in filtered:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    counts = {"must_read": 0, "key": 0, "candidate": 0}
    for p in filtered:
        counts[p.get("tier", "candidate")] = counts.get(p.get("tier", "candidate"), 0) + 1
    print(f"Filter: {len(data)} -> {len(filtered)} papers", file=sys.stderr)
    print(f"  建议精读 (must_read): {counts['must_read']}", file=sys.stderr)
    print(f"  今日重点 (key):       {counts['key']}", file=sys.stderr)
    print(f"  今日候选 (candidate): {counts['candidate']}", file=sys.stderr)


if __name__ == "__main__":
    main()
