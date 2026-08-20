#!/usr/bin/env python3
"""
Correctness metric for graph 2 (Priya persona) - the same "commit != correct"
check as correctness_analysis.py, applied to seed_graph_2's Phase A results.

Reuses poc_compare_multimodel_graph2's already-written result files
(research/results/poc_results_phase2_graph2_*.json) - makes ZERO new API
calls. Does NOT touch, call, or modify the v2 scorer; COMMIT/HEDGE labels
here are exactly what's already stored in those files.

Ground truth is derived directly from seed_graph_2.DEMO_GRAPH_2's own weight
formula, same rule as graph 1's TOP_PATH_LABELS approach: any node on the
single highest-weight root-to-leaf path counts as CORRECT for general
priority queries. Two forced-choice queries (#4, #11) are scored against a
narrower, query-specific subtree ground truth instead. Q8 ("What's holding
me back...") is excluded as N/A, identical treatment to graph 1 - obstacle
framing has no highest-weight-node ground truth.

Target extraction (alias table, bolded-span/heading/commit-sentence window
detection) mirrors correctness_analysis.py's method exactly, built once from
the graph-2 node labels and plausible paraphrases before this script's first
live run against real graph-2 output, not adjusted afterward based on what
the results looked like.

Usage: python research/correctness_analysis_graph2.py
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from seed_graph_2 import DEMO_GRAPH_2, DEMO_USER_2, PRIORITY_QUERIES_2

RESULTS_DIR = os.path.join(HERE, "results")
MODELS = [
    ("claude-sonnet-4-6", "claude-sonnet-4-6"),
    ("claude-opus-4-8", "claude-opus-4-8"),
    ("gpt-5.5-2026-04-23", "gpt-5_5-2026-04-23"),
]
CONDITIONS = ["graph", "flat_list_prioritized", "flat_list", "graph_neutral", "none"]
N_RUNS = 5

# ============================================================
# Ground truth - top path per the approved graph-2 design (defensible
# 6-7pt margin at the top of the graph):
#   Client Design Work (78.0, domain)
#     -> Active Client Projects (74.0, theme)
#       -> Brand identity project deadline for local bakery (74.0, concept)
#
# Q4 and Q11 are forced-choice queries, scored against a narrower,
# query-specific subtree ground truth instead of the global top path:
#   Q4  "Between the bakery brand identity project and my mom's care
#         coordination..." - bakery/Active Client Projects (78/74) vs
#         Parent's Care Coordination (72/67) -> bakery side wins clearly.
#   Q11 "...client work or my ceramics practice first?" - Client Design
#         Work (78) vs Creative Practice/Ceramics Hobby (55/50) -> client
#         work wins clearly (23pt domain gap, not a close call).
#
# Q8 ("What's holding me back...") excluded as N/A, same reasoning as
# graph 1: obstacle framing has no highest-weight-node ground truth.
# ============================================================

TOP_PATH_LABELS_2 = [
    "Client Design Work",
    "Active Client Projects",
    "Brand identity project deadline for local bakery",
]

QUERY_GROUND_TRUTH_2 = {
    "What's my top priority right now?": ("top_path", None),
    "What should I focus on next?": ("top_path", None),
    "If I could only work on one thing this week, what should it be?": ("top_path", None),
    "Between the bakery brand identity project and my mom's care coordination, which should I prioritize?":
        ("subtree", {"correct": ["Client Design Work", "Active Client Projects",
                                  "Brand identity project deadline for local bakery"],
                      "wrong": ["Family & Caregiving", "Parent's Care Coordination",
                                "Mom's cardiology appointment follow-up", "In-home care aide search",
                                "Medicare paperwork review", "Family caregiving schedule coordination",
                                "Mom's medication management system"]}),
    "What's the single most important thing I should be doing today?": ("top_path", None),
    "Rank my current projects from most to least urgent.": ("top_path", None),
    "I only have a few free hours this weekend - what should I spend them on?": ("top_path", None),
    "What's holding me back the most right now?": ("ambiguous", None),
    "Which of my interests deserves the most attention this month?": ("top_path", None),
    "What's the one thing that, if I finished it, would unlock the most progress?": ("top_path", None),
    "Should I focus on client work or my ceramics practice first?":
        ("subtree", {"correct": ["Client Design Work", "Active Client Projects", "Design Skill Development"],
                      "wrong": ["Creative Practice", "Ceramics Hobby", "Wheel-throwing technique practice",
                                "Glaze chemistry experimentation", "Community studio membership renewal"]}),
    "What's the highest-leverage use of my time this week?": ("top_path", None),
}
assert set(QUERY_GROUND_TRUTH_2) == set(PRIORITY_QUERIES_2), "ground truth must cover exactly the 12 graph-2 PRIORITY_QUERIES_2"


def print_ground_truth_ranking():
    rows = [(DEMO_USER_2, 100.0, "user", None)]
    for d in DEMO_GRAPH_2:
        rows.append((d["domain"], float(d["domain_weight"]), "domain", None))
        for t in d["themes"]:
            rows.append((t["name"], float(t["weight"]), "theme", d["domain"]))
            base = t["weight"]
            for i, title in enumerate(t["chain"]):
                w = round(base * (1 - 0.05 * i), 1)
                rows.append((title, w, "concept", t["name"]))
    rows.sort(key=lambda r: -r[1])
    print(f"{'label':52s} {'weight':>7s}  {'type':9s} parent")
    for label, w, typ, parent in rows:
        marker = " <== TOP PATH" if label in TOP_PATH_LABELS_2 else ""
        print(f"{label:52s} {w:7.1f}  {typ:9s} {parent or '':30s}{marker}")
    return rows


# ============================================================
# Node label / alias table - built once, before any live graph-2 run, from
# the node labels themselves plus plausible paraphrases (not from observed
# transcripts, since none exist yet for this graph). Not adjusted after
# seeing results.
# ============================================================

def _all_node_labels() -> list[str]:
    labels = []
    for d in DEMO_GRAPH_2:
        labels.append(d["domain"])
        for t in d["themes"]:
            labels.append(t["name"])
            labels.extend(t["chain"])
    return labels


ALL_NODE_LABELS_2 = _all_node_labels()

ALIASES_2 = {
    # Client Design Work cluster
    "client work": "Client Design Work",
    "design work": "Client Design Work",
    "client design": "Client Design Work",
    "client projects": "Active Client Projects",
    "active client work": "Active Client Projects",
    "brand identity project": "Brand identity project deadline for local bakery",
    "bakery brand identity": "Brand identity project deadline for local bakery",
    "the bakery project": "Brand identity project deadline for local bakery",
    "bakery project": "Brand identity project deadline for local bakery",
    "brand identity": "Brand identity project deadline for local bakery",
    "nonprofit website": "Website redesign for nonprofit client",
    "nonprofit redesign": "Website redesign for nonprofit client",
    "client onboarding": "New client onboarding backlog",
    "onboarding backlog": "New client onboarding backlog",
    "client feedback": "Client feedback revision round",
    "overdue invoice": "Invoice follow-up for overdue client",
    "portfolio case study": "Portfolio case study writeup",
    "referral outreach": "Referral outreach to past clients",
    "figma course": "Figma advanced prototyping course",
    "prototyping course": "Figma advanced prototyping course",
    "typography study": "Typography study deep dive",
    "motion design": "Motion design experimentation",
    "accessibility research": "Accessibility in UI design research",
    "skill development": "Design Skill Development",
    # Family & Caregiving cluster
    "caregiving": "Family & Caregiving",
    "family caregiving": "Family & Caregiving",
    "mom's care coordination": "Parent's Care Coordination",
    "care coordination": "Parent's Care Coordination",
    "caring for mom": "Parent's Care Coordination",
    "mom's cardiology appointment": "Mom's cardiology appointment follow-up",
    "cardiology appointment": "Mom's cardiology appointment follow-up",
    "care aide search": "In-home care aide search",
    "home care aide": "In-home care aide search",
    "medicare paperwork": "Medicare paperwork review",
    "caregiving schedule": "Family caregiving schedule coordination",
    "medication management": "Mom's medication management system",
    "school transition": "Kids' School Transition",
    "kids school": "Kids' School Transition",
    "middle school enrollment": "Middle school enrollment research",
    "after school program": "After-school program evaluation",
    "reading tutor": "Kid's reading tutor search",
    "parent teacher conference": "Parent-teacher conference prep",
    # Studio Business Operations cluster
    "studio business": "Studio Business Operations",
    "business operations": "Studio Business Operations",
    "financial planning": "Financial Planning",
    "tax estimate": "Quarterly tax estimate prep",
    "pricing strategy": "Studio pricing strategy revision",
    "savings buffer": "Business savings buffer goal",
    "expense tracking": "Expense tracking system cleanup",
    "studio growth": "Studio Growth",
    "part time contractor": "Hiring a part-time contractor",
    "hiring a contractor": "Hiring a part-time contractor",
    "intake automation": "Client intake process automation",
    "studio seo": "Studio website SEO improvement",
    "networking events": "Local business networking events",
    # Creative Practice / Ceramics cluster
    "creative practice": "Creative Practice",
    "ceramics practice": "Ceramics Hobby",
    "ceramics hobby": "Ceramics Hobby",
    "ceramics": "Ceramics Hobby",
    "pottery": "Ceramics Hobby",
    "wheel throwing": "Wheel-throwing technique practice",
    "glaze chemistry": "Glaze chemistry experimentation",
    "studio membership": "Community studio membership renewal",
    # Personal Health cluster
    "health and recovery": "Health & Recovery",
    "wrist strain": "Physical therapy for wrist strain",
    "physical therapy": "Physical therapy for wrist strain",
    "sleep schedule": "Sleep schedule regularization",
    "physical checkup": "Annual physical checkup scheduling",
    "annual checkup": "Annual physical checkup scheduling",
}


def _normalize(text: str) -> str:
    text = text.replace("-", " ")
    return re.sub(r"\s+", " ", text.lower()).strip()


_NODE_PATTERNS_2 = None


def _node_patterns():
    global _NODE_PATTERNS_2
    if _NODE_PATTERNS_2 is not None:
        return _NODE_PATTERNS_2
    entries = [(label, label) for label in ALL_NODE_LABELS_2] + list(ALIASES_2.items())
    entries.sort(key=lambda e: -len(e[0]))
    compiled = []
    for surface, canonical in entries:
        pat = re.compile(r"\b" + re.escape(_normalize(surface)) + r"\b")
        compiled.append((pat, canonical))
    _NODE_PATTERNS_2 = compiled
    return _NODE_PATTERNS_2


def _high_confidence_windows(text: str) -> list[str]:
    from poc_compare_v2 import COMMIT_PATTERNS

    windows = []
    windows += re.findall(r"\*\*(.+?)\*\*", text)
    windows += re.findall(r"^#{1,4}\s*(.+)$", text, re.MULTILINE)
    for sent in re.split(r"(?<=[.!?])\s+|\n+", text):
        if any(re.search(p, sent, re.I) for p in COMMIT_PATTERNS):
            windows.append(sent)
    return windows


def extract_target(response_text: str) -> tuple[str | None, str]:
    norm_full = _normalize(response_text)
    patterns = _node_patterns()

    windows = _high_confidence_windows(response_text)
    window_hits = []
    for w in windows:
        nw = _normalize(w)
        for pat, canonical in patterns:
            if pat.search(nw):
                window_hits.append(canonical)
                break
    if window_hits:
        seen_order = list(dict.fromkeys(window_hits))
        counts = {c: window_hits.count(c) for c in seen_order}
        best = max(seen_order, key=lambda c: counts[c])
        return best, "high"

    if windows:
        snippet = windows[0].strip()
        return (snippet[:80] + "...") if len(snippet) > 80 else snippet, "off_graph"

    for pat, canonical in patterns:
        if pat.search(norm_full):
            return canonical, "low"

    return None, "none"


def classify_correctness(query: str, target: str | None, status: str) -> str:
    mode, spec = QUERY_GROUND_TRUTH_2[query]
    if mode == "ambiguous":
        return "N/A"
    if status == "none":
        return "UNRESOLVABLE"
    if status == "off_graph":
        return "WRONG"
    if mode == "top_path":
        return "CORRECT" if target in TOP_PATH_LABELS_2 else "WRONG"
    if mode == "subtree":
        if target in spec["correct"]:
            return "CORRECT"
        return "WRONG"
    raise AssertionError(mode)


def load_all_commits() -> list[dict]:
    rows = []
    for model, tag in MODELS:
        for run in range(1, N_RUNS + 1):
            path = os.path.join(RESULTS_DIR, f"poc_results_phase2_graph2_{tag}_run{run}.json")
            with open(path) as f:
                data = json.load(f)
            for r in data["results"]:
                query = r["query"]
                for cond in CONDITIONS:
                    cell = r[cond]
                    if cell["label"] != "COMMIT":
                        continue
                    target, status = extract_target(cell["response"])
                    verdict = classify_correctness(query, target, status)
                    rows.append({
                        "model": model, "run": run, "condition": cond, "query": query,
                        "target": target, "extract_status": status, "verdict": verdict,
                    })
    return rows


def render_report(rows: list[dict]) -> str:
    lines = ["# Graph 2 (Priya): Correctness of COMMIT-labeled responses", "",
             f"{len(rows)} COMMIT-labeled responses across all graph-2 Phase A data (3 models x "
             "5 conditions x 5 runs x 12 queries). Ground truth and extraction method are in "
             "`research/correctness_analysis_graph2.py`. Q8 ('What's holding me back...') "
             "excluded as ambiguous ground truth (N/A), same as graph 1.", ""]

    lines += ["## Per model / per condition (among COMMITs)", "",
              "| Model | Condition | n | correct | wrong | unresolvable | correct-rate | wrong-rate | unresolvable-rate |",
              "|---|---|---|---|---|---|---|---|---|"]
    for model, _ in MODELS:
        for cond in CONDITIONS:
            sub = [r for r in rows if r["model"] == model and r["condition"] == cond and r["verdict"] != "N/A"]
            n = len(sub)
            if n == 0:
                lines.append(f"| {model} | {cond} | 0 | - | - | - | - | - | - |")
                continue
            c = sum(1 for r in sub if r["verdict"] == "CORRECT")
            w = sum(1 for r in sub if r["verdict"] == "WRONG")
            u = sum(1 for r in sub if r["verdict"] == "UNRESOLVABLE")
            lines.append(f"| {model} | {cond} | {n} | {c} | {w} | {u} | "
                          f"{c/n:.0%} | {w/n:.0%} | {u/n:.0%} |")

    lines += ["", "## Off-graph sub-count (within WRONG, for auditability)", "",
              "| Model | Condition | off_graph | wrong_on_graph |", "|---|---|---|---|"]
    for model, _ in MODELS:
        for cond in CONDITIONS:
            sub = [r for r in rows if r["model"] == model and r["condition"] == cond and r["verdict"] == "WRONG"]
            og = sum(1 for r in sub if r["extract_status"] == "off_graph")
            lines.append(f"| {model} | {cond} | {og} | {len(sub) - og} |")

    lines += ["", "## Extraction confidence breakdown", "",
              "| Model | high | low | off_graph | none(unresolvable) |", "|---|---|---|---|---|"]
    for model, _ in MODELS:
        sub = [r for r in rows if r["model"] == model and r["verdict"] != "N/A"]
        counts = {s: sum(1 for r in sub if r["extract_status"] == s) for s in ("high", "low", "off_graph", "none")}
        lines.append(f"| {model} | {counts['high']} | {counts['low']} | {counts['off_graph']} | {counts['none']} |")

    lines += ["", "## Decisive comparison: accurate decisiveness, or just confident noise?", "",
              "graph-like = graph + graph_neutral (both see the weighted structure). "
              "flat/none-like = flat_list + flat_list_prioritized + none (no weighting).", "",
              "| Model | graph-like correct-rate (n) | flat/none-like correct-rate (n) | verdict |",
              "|---|---|---|---|"]
    graphy, flatty = ["graph", "graph_neutral"], ["flat_list", "flat_list_prioritized", "none"]
    for model, _ in MODELS:
        g = [r for r in rows if r["model"] == model and r["condition"] in graphy and r["verdict"] != "N/A"]
        f = [r for r in rows if r["model"] == model and r["condition"] in flatty and r["verdict"] != "N/A"]
        gn, fn = len(g), len(f)
        gc = sum(1 for r in g if r["verdict"] == "CORRECT")
        fc = sum(1 for r in f if r["verdict"] == "CORRECT")
        g_rate = gc / gn if gn else 0.0
        f_rate = fc / fn if fn else 0.0
        verdict = ("ACCURATE - graph-like commits are correct meaningfully more often"
                   if g_rate > f_rate + 0.05 else
                   "NOT CLEARLY ACCURATE - correct-rates are close or reversed")
        lines.append(f"| {model} | {gc}/{gn} ({g_rate:.0%}) | {fc}/{fn} ({f_rate:.0%}) | {verdict} |")

    lines += ["", "## Honest flag: absolute wrong-rate within the pure graph condition", "",
              "| Model | graph condition: correct | wrong | wrong-rate |", "|---|---|---|---|"]
    for model, _ in MODELS:
        g = [r for r in rows if r["model"] == model and r["condition"] == "graph" and r["verdict"] != "N/A"]
        n = len(g)
        c = sum(1 for r in g if r["verdict"] == "CORRECT")
        w = sum(1 for r in g if r["verdict"] == "WRONG")
        flag = "  <-- WRONG more than half the time" if n and w / n > 0.5 else ""
        lines.append(f"| {model} | {c} | {w} | {w/n:.0%}{flag} |" if n else f"| {model} | - | - | n=0 |")

    return "\n".join(lines)


if __name__ == "__main__":
    print("=" * 100)
    print("GROUND TRUTH RANKING (graph 2 / Priya, by weight)")
    print("=" * 100)
    print_ground_truth_ranking()
    print()
    print("Top path used for general priority queries:", " -> ".join(TOP_PATH_LABELS_2))
    print()
    print("Flagged: Q8 ('What's holding me back...') scored N/A - obstacle framing")
    print("doesn't map cleanly onto 'highest-weight node'. Same as graph 1.")
    print()

    rows = load_all_commits()
    report = render_report(rows)
    print(report)

    out_path = os.path.join(RESULTS_DIR, "correctness_analysis_graph2.md")
    with open(out_path, "w") as f:
        f.write(report)
    raw_path = os.path.join(RESULTS_DIR, "correctness_analysis_graph2_raw.json")
    with open(raw_path, "w") as f:
        json.dump(rows, f, indent=2)
    print(f"\nWrote {out_path} and {raw_path}")
