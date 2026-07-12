"""
arXiv Paper Scoring Engine  (research_focus.yaml driven)

Reads raw JSONL from crawler, scores each paper based on config/research_focus.yaml,
and outputs JSONL with:
  - score
  - category_tag  (display name: A-测量与瓶颈 / B-通信与调度 / C-容错与弹性 /
                   Infra-推理引擎 / Arch-体系结构 / Space-场景延伸 / Background-支撑)
  - cat_code      (short code: A/B/C/Infra/Arch/Space/Background)
  - sub_tags      (list of secondary category codes)
  - intersection  (True if P0 concept-intersection hit -> force-include)
  - matched_keywords, matched_layers, _score_breakdown

Scoring principles (per RESEARCH_FOCUS.md):
  * P0 concept-intersection: standalone broad words do NOT count; only valid
    co-occurrence patterns count, and at most once (+8, force-include).
  * P1 (B/C mechanisms) +5 each; P2 (infra) +2 each; P3 (arch, gated) +2 each;
    P4 (space) only scores when combined with a system layer.
  * Strong systems (vLLM/SGLang/NCCL/Megatron/Ray) +4 each.
  * Bonuses: open-source +2, explicit hardware/benchmark +3, explicit results +2,
    core arXiv category +1.
  * Downweight: pure VLA/robotics/training/precision/offloading/survey are penalised,
    UNLESS a system-contribution keyword also appears (exception).
  * Keyword stacking is capped (score_caps).
"""

import json
import sys
import os
import re
import yaml
from typing import Dict, List, Set, Tuple

CONFIG_NAME = "research_focus.yaml"


def load_config() -> Dict:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "..", "config", CONFIG_NAME)
    if not os.path.exists(config_path):
        raise SystemExit(f"Config not found: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _lower(text: str) -> str:
    return (text or "").lower()


def p0_intersection(text: str, p0_cfg: Dict) -> bool:
    """Return True if any valid co-occurrence pattern is present.

    A 'broad' token hit alone never counts; only full pattern groups count.
    """
    patterns = p0_cfg.get("patterns", [])
    for group in patterns:
        if all(_lower(term) in text for term in group):
            return True
    return False


def _count_hits(text: str, keywords: List[str], cap: int) -> Tuple[int, List[str]]:
    """Count distinct keyword hits (case-insensitive substring), capped."""
    hits = []
    for kw in keywords:
        if _lower(kw) in text and kw not in hits:
            hits.append(kw)
            if len(hits) >= cap:
                break
    return len(hits), hits


def _has_any(text: str, keywords: List[str]) -> bool:
    return any(_lower(kw) in text for kw in keywords)


def compute_score(item: Dict, cfg: Dict) -> Dict:
    title = _lower(item.get("title"))
    summary = _lower(item.get("summary"))
    text = f"{title} {summary}"
    categories = set(item.get("categories", []) or [])

    kw = cfg["keywords"]
    p0 = kw.get("p0_intersection", {})
    p1 = kw.get("p1_bc", {})
    p2 = kw.get("p2_infra", {})
    p3 = kw.get("p3_arch", {})
    p4 = kw.get("p4_space", {})

    caps = cfg.get("score_caps", {})
    cap_p1 = caps.get("max_p1_hits", 8)
    cap_p2 = caps.get("max_p2_hits", 6)
    cap_p3 = caps.get("max_p3_hits", 4)
    cap_p4 = caps.get("max_p4_hits", 2)
    cap_strong = caps.get("max_strong_system_hits", 2)
    cap_total = caps.get("max_total_keyword_score", 45)

    breakdown: Dict[str, float] = {}
    matched_layers: Set[str] = set()
    matched_keywords: List[str] = []

    # ---- P0 concept intersection ----
    p0_hit = p0_intersection(text, p0)
    if p0_hit:
        breakdown["p0"] = p0.get("weight", 8)
        matched_layers.add("p0")
        matched_keywords.append("P0:intersection")
    else:
        breakdown["p0"] = 0.0

    # ---- P1: B/C mechanisms ----
    comm_kw = p1.get("comm_scheduling", [])
    fault_kw = p1.get("fault_tolerance", [])
    n_comm, comm_hits = _count_hits(text, comm_kw, cap_p1)
    n_fault, fault_hits = _count_hits(text, fault_kw, cap_p1)
    p1_score = (n_comm + n_fault) * p1.get("weight", 5)
    breakdown["p1"] = p1_score
    if n_comm:
        matched_layers.add("p1_comm")
        matched_keywords += [f"P1:{k}" for k in comm_hits]
    if n_fault:
        matched_layers.add("p1_fault")
        matched_keywords += [f"P1:{k}" for k in fault_hits]

    # ---- P2: infra (exclude strong-system keywords to avoid double count) ----
    strong_cfg = cfg.get("strong_systems", {})
    strong_kw = strong_cfg.get("keywords", [])
    p2_eff = [k for k in p2.get("keywords", []) if k not in set(strong_kw)]
    n_p2, p2_hits = _count_hits(text, p2_eff, cap_p2)
    p2_score = n_p2 * p2.get("weight", 2)
    breakdown["p2"] = p2_score
    if n_p2:
        matched_layers.add("p2")
        matched_keywords += [f"P2:{k}" for k in p2_hits]

    # ---- P3: arch (gated by arch_llm_gate) ----
    gate = cfg.get("arch_llm_gate", [])
    p3_pass = _has_any(text, gate)
    n_p3, p3_hits = _count_hits(text, p3.get("keywords", []), cap_p3)
    p3_score = n_p3 * p3.get("weight", 2) if p3_pass else 0.0
    breakdown["p3"] = p3_score
    if n_p3 and p3_pass:
        matched_layers.add("p3")
        matched_keywords += [f"P3:{k}" for k in p3_hits]

    # ---- P4: space (only scores when combined with a system layer) ----
    n_p4, p4_hits = _count_hits(text, p4.get("keywords", []), cap_p4)
    has_system_layer = bool({"p0", "p1_comm", "p1_fault", "p2", "p3"} & matched_layers)
    p4_score = n_p4 * p4.get("weight", 1) if (n_p4 and has_system_layer) else 0.0
    breakdown["p4"] = p4_score
    if n_p4:
        matched_layers.add("p4")
        matched_keywords += [f"P4:{k}" for k in p4_hits]

    # ---- strong systems ----
    n_strong, strong_hits = _count_hits(text, strong_kw, cap_strong)
    strong_score = n_strong * strong_cfg.get("weight", 4)
    breakdown["strong_systems"] = strong_score
    if n_strong:
        matched_keywords += [f"STRONG:{k}" for k in strong_hits]

    # ---- keyword subtotal (capped) ----
    keyword_score = (
        breakdown["p0"] + breakdown["p1"] + breakdown["p2"]
        + breakdown["p3"] + breakdown["p4"] + strong_score
    )
    # downweight (see below) is part of keyword_score too
    keyword_score = max(keyword_score, 0.0)
    if keyword_score > cap_total:
        keyword_score = float(cap_total)
    breakdown["keyword_subtotal"] = keyword_score

    # ---- downweight / exclusion ----
    dw = cfg.get("downweight", {})
    weak = dw.get("weak_keywords", [])
    pen = dw.get("penalties", {})
    exceptions = dw.get("system_exception_keywords", [])
    weak_pen_map = {
        "pure_vla_robotics": pen.get("pure_vla_robotics", -6),
        "pure_training_optimization": pen.get("pure_training_optimization", -4),
        "pure_model_precision": pen.get("pure_model_precision", -5),
        "pure_task_offloading": pen.get("pure_task_offloading", -3),
        "survey": pen.get("survey", -2),
    }
    # which weak buckets are hit
    weak_buckets = set()
    for w in weak:
        if _lower(w) in text:
            if w in ("VLA", "vision-language-action", "embodied intelligence",
                     "robot manipulation", "pure robotics", "autonomous driving perception",
                     "pure multimodal benchmark"):
                weak_buckets.add("pure_vla_robotics")
            elif w in ("pure training optimization", "pure distributed training",
                       "pure federated learning", "pure fine-tuning"):
                weak_buckets.add("pure_training_optimization")
            elif w in ("pure model architecture",):
                weak_buckets.add("pure_model_precision")
            elif w == "pure task offloading":
                weak_buckets.add("pure_task_offloading")
            elif w == "survey":
                weak_buckets.add("survey")
    has_exception = _has_any(text, exceptions)
    down_score = 0.0
    if weak_buckets and not has_exception:
        # apply the single most-severe penalty (avoid stacking multiple negatives)
        down_score = min(weak_pen_map[b] for b in weak_buckets)
    breakdown["downweight"] = down_score

    # ---- bonuses (not capped by keyword cap) ----
    bonuses = cfg.get("bonuses", {})
    open_cfg = bonuses.get("open_source", {})
    hw_cfg = bonuses.get("hardware_benchmark", {})
    res_cfg = bonuses.get("explicit_result", {})
    open_score = open_cfg.get("weight", 2) if _has_any(text, open_cfg.get("indicators", [])) else 0.0
    hw_score = hw_cfg.get("weight", 3) if _has_any(text, hw_cfg.get("indicators", [])) else 0.0
    res_score = res_cfg.get("weight", 2) if _has_any(text, res_cfg.get("indicators", [])) else 0.0
    breakdown["bonus_open_source"] = open_score
    breakdown["bonus_hardware"] = hw_score
    breakdown["bonus_result"] = res_score

    # ---- core arXiv category bonus ----
    core_cats = set(cfg.get("categories", {}).get("core", []))
    cat_bonus = 1.0 if (categories & core_cats) else 0.0
    breakdown["category_bonus"] = cat_bonus

    score = keyword_score + down_score + open_score + hw_score + res_score + cat_bonus
    score = round(score, 2)

    # ---- classification (main category + sub tags) ----
    cls = cfg.get("classification", {})
    display = cls.get("display_names", {})
    rules = cls.get("rules", {})
    a_kw = rules.get("A", [])
    infra_kw = rules.get("Infra", [])
    # matched sets
    matched_fault = n_fault > 0
    matched_comm = n_comm > 0
    matched_A = _has_any(text, a_kw)
    matched_Infra = n_p2 > 0
    matched_Arch = (n_p3 > 0 and p3_pass)
    matched_Space = (n_p4 > 0 and not has_system_layer)

    if matched_fault:
        code = "C"
    elif matched_comm:
        code = "B"
    elif matched_A:
        code = "A"
    elif matched_Infra:
        code = "Infra"
    elif matched_Arch:
        code = "Arch"
    elif matched_Space:
        code = "Space"
    else:
        code = "Background"

    # sub tags = all other matched category codes
    all_matched = []
    if matched_fault:
        all_matched.append("C")
    if matched_comm:
        all_matched.append("B")
    if matched_A:
        all_matched.append("A")
    if matched_Infra:
        all_matched.append("Infra")
    if matched_Arch:
        all_matched.append("Arch")
    if matched_Space:
        all_matched.append("Space")
    sub_tags = [c for c in all_matched if c != code]

    item["score"] = score
    item["category_tag"] = display.get(code, code)
    item["cat_code"] = code
    item["sub_tags"] = sub_tags
    item["intersection"] = p0_hit
    item["matched_keywords"] = matched_keywords
    item["matched_layers"] = sorted(matched_layers)
    item["open_source_hit"] = open_score > 0
    item["system_or_lowbw_hit"] = bool(
        p0_hit or matched_comm or matched_fault
        or _has_any(text, ["low-bandwidth", "multi-node", "bandwidth"])
    )
    item["_score_breakdown"] = {k: round(v, 2) for k, v in breakdown.items()}
    return item


def main():
    if len(sys.argv) < 2:
        print("Usage: python scorer.py <input.jsonl> [output.jsonl]", file=sys.stderr)
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else input_path.replace(".jsonl", "_scored.jsonl")

    config = load_config()
    data = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))

    print(f"Scoring {len(data)} papers...", file=sys.stderr)
    scored = []
    intersection_count = 0
    max_score = -1e9
    min_score = 1e9
    for item in data:
        enriched = compute_score(item, config)
        scored.append(enriched)
        if enriched["intersection"]:
            intersection_count += 1
        s = enriched["score"]
        if s > max_score:
            max_score = s
        if s < min_score:
            min_score = s

    with open(output_path, "w", encoding="utf-8") as f:
        for item in scored:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"Scored: {len(scored)} papers -> {output_path}", file=sys.stderr)
    print(f"  Score range: {min_score:.1f} - {max_score:.1f}", file=sys.stderr)
    print(f"  P0 intersection (force-include): {intersection_count}", file=sys.stderr)


if __name__ == "__main__":
    main()
