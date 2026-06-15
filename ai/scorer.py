"""
arXiv Paper Scoring Engine

Reads raw JSONL from crawler, scores each paper based on config/keywords.yaml,
and outputs JSONL with score, category_tag, intersection flag, and matched_keywords.
"""

import json
import sys
import os
import re
import yaml
from typing import List, Dict, Set, Tuple


def load_config(config_path: str) -> Dict:
    """Load keywords.yaml configuration."""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_keyword_index(config: Dict) -> Dict[str, Tuple[str, float]]:
    """
    Build a flat index: keyword_lower -> (layer_name, weight)
    For faster matching.
    """
    index = {}
    for layer_name, layer_config in config["layers"].items():
        weight = layer_config["weight"]
        for kw in layer_config["keywords"]:
            kw_lower = kw.lower()
            # Keep the highest weight if keyword appears in multiple layers
            if kw_lower not in index or weight > index[kw_lower][1]:
                index[kw_lower] = (layer_name, weight)
    return index


def compute_score(
    item: Dict,
    keyword_index: Dict,
    config: Dict,
) -> Dict:
    """
    Score a single paper and return enriched item.

    Args:
        item: Raw paper dict with title, summary, categories, etc.
        keyword_index: Flat keyword -> (layer, weight) index
        config: Full YAML config

    Returns:
        Enriched item with score, category_tag, intersection, matched_keywords
    """
    title = (item.get("title") or "").lower()
    summary = (item.get("summary") or "").lower()
    text = f"{title} {summary}"
    categories = set(item.get("categories", []))

    # Track matched layers and keywords
    matched_layers: Set[str] = set()
    matched_keywords: List[str] = []
    keyword_score = 0.0

    for kw_lower, (layer_name, weight) in keyword_index.items():
        if kw_lower in text:
            matched_layers.add(layer_name)
            matched_keywords.append(kw_lower)
            keyword_score += weight

    # Category bonus
    core_cats = set(config["categories"]["core"])
    category_bonus = config["categories"]["weight"] if categories & core_cats else 0.0

    # Reproducibility bonus
    reproducibility_bonus = 0.0
    repro_indicators = config["reproducibility_indicators"]
    for indicator in repro_indicators:
        if indicator.lower() in text:
            reproducibility_bonus = config["reproducibility_bonus"]
            break

    # Venue bonus: check title and comment for top venue mentions
    venue_bonus = 0.0
    comment = (item.get("comment") or "").upper()
    title_upper = title.upper()
    for venue in config["venues"]:
        if venue.upper() in comment or venue.upper() in title_upper:
            venue_bonus = config["venue_bonus"]
            break

    score = keyword_score + category_bonus + reproducibility_bonus + venue_bonus
    score = round(score, 2)

    # Determine category_tag
    tag_priority = config["category_tag_priority"]
    tag_names = config.get("category_tag_names", {
        "intersection": "Intersection",
        "core_arch": "Arch-Infra",
        "core_embodied": "Embodied",
        "support": "Support",
    })
    category_tag = tag_names.get("support", "Support")
    for tag in tag_priority:
        if tag in matched_layers:
            category_tag = tag_names.get(tag, "Support")
            break

    is_intersection = "intersection" in matched_layers

    # Enrich item
    item["score"] = score
    item["category_tag"] = category_tag
    item["intersection"] = is_intersection
    item["matched_keywords"] = matched_keywords
    item["_score_breakdown"] = {
        "keyword_score": keyword_score,
        "category_bonus": category_bonus,
        "reproducibility_bonus": reproducibility_bonus,
        "venue_bonus": venue_bonus,
    }

    return item


def main():
    if len(sys.argv) < 2:
        print("Usage: python scorer.py <input.jsonl> [output.jsonl]", file=sys.stderr)
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else input_path.replace(".jsonl", "_scored.jsonl")

    # Locate config
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "..", "config", "keywords.yaml")
    if not os.path.exists(config_path):
        print(f"Config not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    config = load_config(config_path)
    keyword_index = build_keyword_index(config)

    # Read raw JSONL
    data = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))

    print(f"Scoring {len(data)} papers...", file=sys.stderr)

    # Score all papers
    scored = []
    intersection_count = 0
    max_score = 0
    min_score = float("inf")

    for item in data:
        enriched = compute_score(item, keyword_index, config)
        scored.append(enriched)
        if enriched["intersection"]:
            intersection_count += 1
        s = enriched["score"]
        if s > max_score:
            max_score = s
        if s < min_score:
            min_score = s

    # Write output
    with open(output_path, "w", encoding="utf-8") as f:
        for item in scored:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"Scored: {len(scored)} papers → {output_path}", file=sys.stderr)
    print(f"  Score range: {min_score:.1f} - {max_score:.1f}", file=sys.stderr)
    print(f"  Intersection papers: {intersection_count}", file=sys.stderr)


if __name__ == "__main__":
    main()
