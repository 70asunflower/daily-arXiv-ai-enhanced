"""
Top-N Filter with Intersection Force-Include

Reads scored JSONL, sorts by score descending, takes top N,
and force-includes all intersection papers regardless of score.

Outputs: top15 JSONL + summary statistics
"""

import json
import sys
import os
import yaml
from typing import List, Dict


def load_config():
    """Load keywords.yaml for top_n and threshold settings."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "..", "config", "keywords.yaml")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    # Fallback defaults
    return {"top_n": 15, "hard_score_threshold": 0}


def filter_papers(scored_data: List[Dict], config: Dict) -> List[Dict]:
    """
    Filter papers: Top N by score + force-include intersection papers.

    Args:
        scored_data: List of scored paper dicts (with score, intersection fields)
        config: YAML configuration

    Returns:
        Filtered list of papers
    """
    top_n = config.get("top_n", 15)
    threshold = config.get("hard_score_threshold", 0)

    # Separate intersection and non-intersection papers
    intersection_papers = []
    normal_papers = []

    for item in scored_data:
        score = item.get("score", 0)
        is_intersection = item.get("intersection", False)

        # Skip papers below hard threshold (unless intersection)
        if not is_intersection and score <= threshold:
            continue

        if is_intersection:
            intersection_papers.append(item)
        else:
            normal_papers.append(item)

    # Sort normal papers by score descending
    normal_papers.sort(key=lambda x: -x.get("score", 0))

    # Take top N normal papers
    top_normal = normal_papers[:top_n]

    # Combine: all intersection + top N normal (deduplicated by id)
    seen_ids = set()
    result = []

    # Intersection papers first (guaranteed inclusion)
    for p in intersection_papers:
        pid = p["id"]
        if pid not in seen_ids:
            seen_ids.add(pid)
            result.append(p)

    # Then top N normal papers
    for p in top_normal:
        pid = p["id"]
        if pid not in seen_ids:
            seen_ids.add(pid)
            result.append(p)

    # Sort final output by score descending
    result.sort(key=lambda x: -x.get("score", 0))

    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: python filter.py <scored.jsonl> [output.jsonl]", file=sys.stderr)
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else input_path.replace("_scored.jsonl", "_top15.jsonl")

    # Read scored JSONL
    data = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))

    config = load_config()
    filtered = filter_papers(data, config)

    # Write output
    with open(output_path, "w", encoding="utf-8") as f:
        for item in filtered:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    # Summary
    intersection_count = sum(1 for p in filtered if p.get("intersection"))
    normal_count = len(filtered) - intersection_count
    scores = [p.get("score", 0) for p in filtered]
    max_score = max(scores) if scores else 0
    min_score = min(scores) if scores else 0

    print(f"Filter: {len(data)} → {len(filtered)} papers", file=sys.stderr)
    print(f"  Intersection (force-included): {intersection_count}", file=sys.stderr)
    print(f"  Top-N normal: {normal_count}", file=sys.stderr)
    print(f"  Score range: {min_score:.1f} - {max_score:.1f}", file=sys.stderr)


if __name__ == "__main__":
    main()
