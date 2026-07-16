"""
arXiv Paper Scoring Engine  (research_focus.yaml driven — Four Pillars)

Reads raw JSONL from crawler, scores each paper based on config/research_focus.yaml,
and outputs JSONL with:
  - score
  - category_tag  (display name, e.g. "Memory-统一内存/KV" / "B-通信与调度" / ...)
  - cat_code      (short code: A/B/C/Memory/MoE/Spec/Energy/Infra/Arch/Space/Background)
  - sub_tags      (list of secondary tag codes)
  - pillar        (rule-derived: P1/P2/P3/P4/"Cross"/"Background")
  - intersection  (True if P1 concept-intersection hit -> force-include)
  - matched_keywords, matched_layers, _score_breakdown

Scoring principles (per RESEARCH_FOCUS.md / spec section 8):
  * P1 concept-intersection: standalone broad words do NOT count; only valid
    co-occurrence patterns count, and at most once (+8, force-include).
  * P2 (comm optimization OR fault tolerance): +5 each keyword group.
  * Strong systems (vLLM/SGLang/NCCL/Megatron/Ray): +4 each (capped).
  * Explicit hardware + interconnect + benchmark: +3 (once).
  * MoE/MTP AND multi-node comm/sched: +3 (once).
  * Open-source +2; credible system quant result +2; arch+LLM +2; energy w/ power+perf +2.
  * Space-only (no system mechanism): 0.
  * Downweight: pure VLA/robotics -6, precision -5, training -4, offload -3, survey -2,
    UNLESS a system-contribution keyword also appears (exception).
  * Keyword stacking is capped (score_caps).

Main tag (one of 11) chosen by tag priority in config; pillar derived from the
main tag's owning pillar (Cross/Background for Infra/Arch/Space/Background).
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


def concept_intersection(text: str, patterns: List[List[str]]) -> bool:
    """Return True if any valid co-occurrence pattern is present.

    A 'broad' token hit alone never counts; only full pattern groups count.
    """
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

    pillars = cfg.get("pillars", {})
    p1 = pillars.get("P1", {})
    p2 = pillars.get("P2", {})
    p3 = pillars.get("P3", {})
    p4 = pillars.get("P4", {})

    tags = cfg.get("tags", {})
    t_mem = tags.get("memory_signals", [])
    t_moe = tags.get("moe_signals", [])
    t_spec = tags.get("spec_signals", [])
    t_energy = tags.get("energy_signals", [])
    t_space = tags.get("space_keywords", [])
    t_arch = tags.get("arch_keywords", [])
    t_infra = tags.get("infra_keywords", [])
    t_a = tags.get("A_signals", [])
    tag_priority = tags.get("priority",
                            ["Memory", "MoE", "Spec", "Energy", "C", "B", "A",
                             "Arch", "Infra", "Space", "Background"])

    scoring = cfg.get("scoring", {})
    caps = cfg.get("score_caps", {})
    cap_comm = caps.get("max_comm_hits", 4)
    cap_fault = caps.get("max_fault_hits", 4)
    cap_strong = caps.get("max_strong_system_hits", 2)
    cap_moe = caps.get("max_moe_hits", 3)
    cap_spec = caps.get("max_spec_hits", 3)
    cap_total = caps.get("max_total_keyword_score", 45)

    strong_cfg = cfg.get("strong_systems", {})
    strong_kw = strong_cfg.get("keywords", [])
    bonuses = cfg.get("bonuses", {})

    breakdown: Dict[str, float] = {}
    matched_layers: Set[str] = set()
    matched_keywords: List[str] = []

    # ---- P1 concept intersection (+8, force-include) ----
    p1_hit = concept_intersection(text, p1.get("intersection_patterns", []))
    if p1_hit:
        breakdown["p1_intersection"] = scoring.get("pillar1_intersection", 8)
        matched_layers.add("p1")
        matched_keywords.append("P1:intersection")
    else:
        breakdown["p1_intersection"] = 0.0

    # ---- P2: comm / fault (+5 each group) ----
    n_comm, comm_hits = _count_hits(text, p2.get("comm_keywords", []), cap_comm)
    n_fault, fault_hits = _count_hits(text, p2.get("fault_keywords", []), cap_fault)
    p2_score = (n_comm + n_fault) * scoring.get("pillar2_comm_or_fault", 5)
    breakdown["p2_comm_fault"] = p2_score
    if n_comm:
        matched_layers.add("p2_comm")
        matched_keywords += [f"P2:{k}" for k in comm_hits]
    if n_fault:
        matched_layers.add("p2_fault")
        matched_keywords += [f"P2:{k}" for k in fault_hits]

    # ---- strong systems (+4 each, capped) ----
    n_strong, strong_hits = _count_hits(text, strong_kw, cap_strong)
    strong_score = n_strong * strong_cfg.get("weight", 4)
    breakdown["strong_systems"] = strong_score
    if n_strong:
        matched_keywords += [f"STRONG:{k}" for k in strong_hits]

    # ---- hardware + interconnect + benchmark (+3 once) ----
    hw_score = scoring.get("hw_benchmark", 3) if _has_any(text, bonuses.get("hw_indicators", [])) else 0.0
    breakdown["hw_benchmark"] = hw_score
    if hw_score:
        matched_keywords.append("BONUS:hw_benchmark")

    # ---- MoE/MTP with multi-node comm/sched (+3 once) ----
    n_moe, moe_hits = _count_hits(text, p3.get("moe_keywords", []), cap_moe)
    n_spec, spec_hits = _count_hits(text, p3.get("spec_keywords", []), cap_spec)
    net_sched = (p2.get("comm_keywords", []) + ["communication", "scheduling",
                 "network", "distributed", "multi-node", "partitioning", "low-bandwidth"])
    moe_mtp_net = (n_moe > 0 or n_spec > 0) and _has_any(text, net_sched)
    moe_score = scoring.get("moe_mtp_net_sched", 3) if moe_mtp_net else 0.0
    breakdown["moe_mtp"] = moe_score
    if n_moe:
        matched_layers.add("p3_moe")
        matched_keywords += [f"P3:{k}" for k in moe_hits]
    if n_spec:
        matched_layers.add("p3_spec")
        matched_keywords += [f"P3:{k}" for k in spec_hits]

    # ---- open source (+2) ----
    open_score = scoring.get("open_source", 2) if _has_any(text, bonuses.get("open_indicators", [])) else 0.0
    breakdown["open_source"] = open_score

    # ---- credible system quant result (+2) ----
    res_score = scoring.get("quant_result", 2) if _has_any(text, bonuses.get("result_indicators", [])) else 0.0
    breakdown["quant_result"] = res_score

    # ---- arch + LLM (+2, gated) ----
    arch_pass = _has_any(text, bonuses.get("arch_gate", []))
    n_arch = 1 if (t_arch and _has_any(text, t_arch)) else 0
    arch_score = scoring.get("arch_llm", 2) if (n_arch and arch_pass) else 0.0
    breakdown["arch_llm"] = arch_score
    if n_arch and arch_pass:
        matched_layers.add("arch")

    # ---- energy with power + perf (+2) ----
    energy_power = _has_any(text, p4.get("power_indicators", []))
    energy_perf = _has_any(text, p4.get("perf_indicators", []))
    energy_score = scoring.get("energy_power_perf", 2) if (energy_power and energy_perf) else 0.0
    breakdown["energy"] = energy_score
    if energy_score:
        matched_layers.add("p4")

    # ---- keyword subtotal (capped) ----
    keyword_score = (
        breakdown["p1_intersection"] + breakdown["p2_comm_fault"] + strong_score
        + hw_score + moe_score + open_score + res_score + arch_score + energy_score
    )
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
    weak_buckets = set()
    for w in weak:
        lw = _lower(w)
        if lw in text:
            if w in ("VLA", "vision-language-action", "embodied intelligence",
                     "robot manipulation", "pure robotics", "autonomous driving perception",
                     "pure multimodal benchmark", "ROS 2", "robot control", "real-time coordination"):
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
        down_score = min(weak_pen_map[b] for b in weak_buckets)
    breakdown["downweight"] = down_score

    score = keyword_score + down_score
    score = round(score, 2)

    # ---- classification (main tag + sub tags) ----
    display = tags.get("display_names", {})

    # signal flags
    sig_memory = _has_any(text, t_mem)
    sig_moe = n_moe > 0
    sig_spec = n_spec > 0
    sig_energy = energy_score > 0 or _has_any(text, t_energy)
    sig_fault = n_fault > 0
    sig_comm = n_comm > 0
    sig_a = _has_any(text, t_a)
    sig_arch = (n_arch and arch_pass)
    sig_infra = _has_any(text, t_infra)
    sig_space = _has_any(text, t_space) and not (
        sig_memory or sig_moe or sig_spec or sig_energy or sig_fault or sig_comm or sig_a or sig_arch or sig_infra
    )

    flags = {
        "Memory": sig_memory,
        "MoE": sig_moe,
        "Spec": sig_spec,
        "Energy": sig_energy,
        "C": sig_fault,
        "B": sig_comm,
        "A": sig_a,
        "Arch": sig_arch,
        "Infra": sig_infra,
        "Space": sig_space,
        "Background": False,
    }

    code = "Background"
    for t in tag_priority:
        if flags.get(t):
            code = t
            break

    # sub tags = all other matched codes (in taxonomy order)
    all_matched = [t for t in tag_priority if flags.get(t)]
    sub_tags = [t for t in all_matched if t != code]

    # ---- pillar (rule-derived from main tag's owning pillar) ----
    pillar_of = {}
    for pkey, pval in pillars.items():
        for t in pval.get("tags", []):
            pillar_of[t] = pkey
    pillar = pillar_of.get(code, "Cross" if code in ("Infra", "Arch", "Space") else "Background")

    item["score"] = score
    item["category_tag"] = display.get(code, code)
    item["cat_code"] = code
    item["sub_tags"] = sub_tags
    item["pillar"] = pillar
    item["intersection"] = p1_hit
    item["matched_keywords"] = matched_keywords
    item["matched_layers"] = sorted(matched_layers)
    item["open_source_hit"] = open_score > 0
    item["system_or_lowbw_hit"] = bool(
        p1_hit or sig_comm or sig_fault
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
    print(f"  P1 intersection (force-include): {intersection_count}", file=sys.stderr)


if __name__ == "__main__":
    main()
