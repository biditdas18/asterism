#!/usr/bin/env python3
"""
Task 1 (correctness metric): among responses ALREADY LABELED COMMIT by the
frozen v2 scorer, does the named target match the seed graph's actual
highest-weight node ("correct"), a lower-weight node or something off-graph
("wrong"), or is the target not determinable from the text ("unresolvable")?

Reuses existing Phase 2 result files (research/results/poc_results_phase2_
*.json) - makes ZERO new API calls. Does NOT touch, call, or modify the v2
scorer or VALIDATION_SET; COMMIT/HEDGE labels here are exactly what's
already stored in those files. This script only asks a second, independent
question about responses already labeled COMMIT: is the committed answer
actually the priority-weighted one?

Ground truth is derived directly from poc_compare.DEMO_GRAPH's own weight
formula - see GROUND_TRUTH_NOTES below for the exact rule and the two
queries flagged as ambiguous.

Target extraction is deterministic string/label matching against the seed
graph's node labels (plus a small, explicit alias table for common
paraphrases observed in this project's own prior transcripts) - not an LLM
judge, not a relabeling of COMMIT/HEDGE.

Usage: python research/correctness_analysis.py
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from poc_compare import DEMO_GRAPH, DEMO_USER, PRIORITY_QUERIES

RESULTS_DIR = os.path.join(HERE, "results")
MODELS = [
    ("claude-sonnet-4-6", "claude-sonnet-4-6"),
    ("claude-opus-4-8", "claude-opus-4-8"),
    ("gpt-5.5-2026-04-23", "gpt-5_5-2026-04-23"),
]
CONDITIONS = ["graph", "flat_list_prioritized", "flat_list", "graph_neutral", "none"]
N_RUNS = 5

# ============================================================
# Ground truth (ready for user confirmation before this is treated as final)
# ============================================================
#
# Rule: for a general priority query, "correct" = the single highest-weight
# node in the seed graph (excluding the user's own node, "Alex", which is
# never a sensible answer to "what should I prioritize"). Because Asterism's
# injected context shows nodes at every level (domain/theme/concept) and
# real responses reasonably drill from the top domain into its top theme
# and top concept - which are the SAME underlying priority thread, just
# named at a different level of the hierarchy - "correct" is defined as
# any node on the single highest-weight root-to-leaf PATH, not only the
# single highest-weight node in isolation. That path, computed from
# DEMO_GRAPH's own weight formula, is:
#
#   Open Source Development (85.0, domain)
#     -> AI Memory Tools (80.0, theme)
#       -> LLM context window limitations (80.0, concept - tied with its
#          parent theme; the chain formula is base_weight * (1 - 0.05*i),
#          so the first chain item keeps its parent theme's exact weight)
#
# Two queries explicitly compare two named sub-areas rather than asking
# generally, and are scored against a narrower, query-specific ground
# truth instead of the global top path:
#   Q4  "Between my open source project and my academic paper..."
#         open source (Open Source Development domain, 85 / AI Memory
#         Tools theme, 80) vs academic paper (Research Identity theme /
#         First academic paper idea concept, both 70) -> open source wins
#         clearly (85/80 vs 70).
#   Q11 "...shipping the CLI tool or writing the paper first?"
#         CLI Tools (72) vs paper (Research Identity / First academic
#         paper idea, 70) -> CLI Tools wins, but by only 2 points - this
#         is the closest call in the query set and is flagged as
#         lower-confidence ground truth, not withheld.
#
# One query is flagged as AMBIGUOUS ground truth and is EXCLUDED from
# scoring rather than forced:
#   Q8  "What's holding me back the most right now?" asks about an
#         obstacle/blocker, not a positive priority. Mapping "highest-
#         weight node" onto "what's blocking you" is a real stretch -
#         the top-weight node represents what the user engages with
#         MOST, which is not obviously the same thing as what's holding
#         them back. Scored as N/A below, not force-mapped.

TOP_PATH_LABELS = [
    "Open Source Development",
    "AI Memory Tools",
    "LLM context window limitations",
]

QUERY_GROUND_TRUTH = {
    "What's my top priority right now?": ("top_path", None),
    "What should I focus on next?": ("top_path", None),
    "If I could only work on one thing this week, what should it be?": ("top_path", None),
    "Between my open source project and my academic paper, which should I prioritize?":
        ("subtree", {"correct": ["Open Source Development", "AI Memory Tools"],
                      "wrong": ["Research Identity", "First academic paper idea",
                                "Career Growth", "arXiv submission process",
                                "Peer review participation", "Conference paper planning",
                                "Citation building strategy"]}),
    "What's the single most important thing I should be doing today?": ("top_path", None),
    "Rank my current projects from most to least urgent.": ("top_path", None),
    "I only have a few free hours this weekend - what should I spend them on?": ("top_path", None),
    "What's holding me back the most right now?": ("ambiguous", None),
    "Which of my interests deserves the most attention this month?": ("top_path", None),
    "What's the one thing that, if I finished it, would unlock the most progress?": ("top_path", None),
    "Should I focus on shipping the CLI tool or writing the paper first?":
        ("subtree", {"correct": ["CLI Tools"],
                      "wrong": ["Research Identity", "First academic paper idea",
                                "AI Memory Tools", "Open Source Development"]}),
    "What's the highest-leverage use of my time this week?": ("top_path", None),
}
assert set(QUERY_GROUND_TRUTH) == set(PRIORITY_QUERIES), "ground truth must cover exactly the 12 PRIORITY_QUERIES"


def print_ground_truth_ranking():
    rows = [(DEMO_USER, 100.0, "user", None)]
    for d in DEMO_GRAPH:
        rows.append((d["domain"], float(d["domain_weight"]), "domain", None))
        for t in d["themes"]:
            rows.append((t["name"], float(t["weight"]), "theme", d["domain"]))
            base = t["weight"]
            for i, title in enumerate(t["chain"]):
                w = round(base * (1 - 0.05 * i), 1)
                rows.append((title, w, "concept", t["name"]))
    rows.sort(key=lambda r: -r[1])
    print(f"{'label':42s} {'weight':>7s}  {'type':9s} parent")
    for label, w, typ, parent in rows:
        marker = " <== TOP PATH" if label in TOP_PATH_LABELS else ""
        print(f"{label:42s} {w:7.1f}  {typ:9s} {parent or '':30s}{marker}")
    return rows


# ============================================================
# Node label / alias table for deterministic target extraction.
# Every entry maps a normalized surface form to a canonical DEMO_GRAPH
# node label. Built from paraphrases actually observed in this project's
# own prior transcripts (not invented), kept explicit and inspectable.
# ============================================================

def _all_node_labels() -> list[str]:
    labels = []
    for d in DEMO_GRAPH:
        labels.append(d["domain"])
        for t in d["themes"]:
            labels.append(t["name"])
            labels.extend(t["chain"])
    return labels


ALL_NODE_LABELS = _all_node_labels()

ALIASES = {
    # Open Source Development / AI Memory Tools cluster
    "open source project": "Open Source Development",
    "open source work": "Open Source Development",
    "the open source side": "Open Source Development",
    "open source launch": "Open Source Development",
    "open source": "Open Source Development",  # bare - unambiguous, no other node contains this phrase
    "ai memory tool": "AI Memory Tools",
    "ai memory tooling": "AI Memory Tools",
    "the memory tool": "AI Memory Tools",
    "ai memory": "AI Memory Tools",  # bare - found via spot-check ("AI memory / knowledge
    # graph tool" as a heading didn't match "ai memory tool" because of the inserted words)
    "memory tool": "AI Memory Tools",
    "context window": "LLM context window limitations",
    "context limitations": "LLM context window limitations",
    "knowledge graph architecture": "Knowledge graph architecture research",
    "the graph architecture": "Knowledge graph architecture research",
    "hebbian decay": "Hebbian decay design",
    "retrieval index insight": "Graph as retrieval index insight",
    "graph as retrieval index": "Graph as retrieval index insight",
    "constellation visualization": "Constellation visualization build",
    "pypi packaging": "PyPI packaging strategy",
    "reddit launch": "Reddit launch preparation",
    # CLI Tools cluster
    "the cli tool": "CLI Tools",
    "cli tool": "CLI Tools",
    "shipping the cli": "CLI Tools",
    "click framework": "Click framework exploration",
    "package structure": "Package structure design",
    "user adoption": "User adoption optimization",
    "python project": "Python project ideation",
    # Research Identity / academic cluster
    "the paper": "First academic paper idea",
    "writing the paper": "First academic paper idea",
    "academic paper": "First academic paper idea",
    "first paper": "First academic paper idea",
    "arxiv submission": "arXiv submission process",
    "peer review": "Peer review participation",
    "conference paper": "Conference paper planning",
    "citation building": "Citation building strategy",
    "research identity": "Research Identity",
    # Technical Skills cluster
    "distributed systems": "Distributed systems fundamentals",
    "data intensive applications": "Data intensive applications reading",
    "b-tree index": "B-tree index deep dive",
    "system design": "System design patterns",
    # Stoicism cluster
    "marcus aurelius": "Marcus Aurelius introduction",
    "meditations": "Meditations first reading",
    "stoic principles": "Stoic principles for career",
    "daily practice": "Daily practice implementation",
    # Fitness cluster
    "gym routine": "Gym routine design",
    "nutrition": "Nutrition basics",
}


def _normalize(text: str) -> str:
    # hyphens treated as spaces ("open-source" == "open source") - found via
    # spot-check that this was silently causing off-graph misses (e.g. "the
    # open-source launch thread" not matching the "open source project" alias)
    text = text.replace("-", " ")
    return re.sub(r"\s+", " ", text.lower()).strip()


_NODE_PATTERNS = None


def _node_patterns():
    """(compiled regex, canonical_label) pairs, longest label first so
    'AI Memory Tools' matches before a shorter substring could."""
    global _NODE_PATTERNS
    if _NODE_PATTERNS is not None:
        return _NODE_PATTERNS
    entries = [(label, label) for label in ALL_NODE_LABELS] + list(ALIASES.items())
    entries.sort(key=lambda e: -len(e[0]))
    compiled = []
    for surface, canonical in entries:
        pat = re.compile(r"\b" + re.escape(_normalize(surface)) + r"\b")
        compiled.append((pat, canonical))
    _NODE_PATTERNS = compiled
    return _NODE_PATTERNS


def _high_confidence_windows(text: str) -> list[str]:
    """Bolded spans, markdown headings, and sentences containing a COMMIT_PATTERNS
    trigger - the text regions where a decisive answer is actually stated, as
    opposed to the many node labels a graph-mode response mentions in passing
    as supporting context."""
    from poc_compare_v2 import COMMIT_PATTERNS

    windows = []
    windows += re.findall(r"\*\*(.+?)\*\*", text)
    windows += re.findall(r"^#{1,4}\s*(.+)$", text, re.MULTILINE)
    for sent in re.split(r"(?<=[.!?])\s+|\n+", text):
        if any(re.search(p, sent, re.I) for p in COMMIT_PATTERNS):
            windows.append(sent)
    return windows


def extract_target(response_text: str) -> tuple[str | None, str]:
    """
    Returns (target, status).
      status == "high":      target is a canonical node label, found inside
                              a bolded span / heading / commit-pattern
                              sentence - the strongest signal that this is
                              the actual stated answer.
      status == "low":       target is a canonical node label, found only
                              via a whole-response fallback scan (no
                              bolded/heading/commit-sentence match) - a
                              real but weaker signal.
      status == "off_graph": a bolded span / heading / commit-pattern
                              sentence exists (the response clearly states
                              a specific decisive answer) but it names
                              nothing in ALL_NODE_LABELS/ALIASES - target
                              is the raw snippet, for auditability.
      status == "none":      no high-confidence window AND no whole-text
                              match either - genuinely can't tell what,
                              if anything, was named. Caller must not force
                              a classification for this case.
    """
    norm_full = _normalize(response_text)
    patterns = _node_patterns()

    windows = _high_confidence_windows(response_text)
    window_hits = []
    for w in windows:
        nw = _normalize(w)
        for pat, canonical in patterns:
            if pat.search(nw):
                window_hits.append(canonical)
                break  # first (longest) match in this window is enough
    if window_hits:
        # most frequent hit among high-confidence windows; ties broken by
        # first occurrence order
        seen_order = list(dict.fromkeys(window_hits))
        counts = {c: window_hits.count(c) for c in seen_order}
        best = max(seen_order, key=lambda c: counts[c])
        return best, "high"

    if windows:
        # a decisive-sounding window exists but names no graph node
        snippet = windows[0].strip()
        return (snippet[:80] + "...") if len(snippet) > 80 else snippet, "off_graph"

    # fallback: whole-text scan, first match only, low confidence
    for pat, canonical in patterns:
        if pat.search(norm_full):
            return canonical, "low"

    return None, "none"


def classify_correctness(query: str, target: str | None, status: str) -> str:
    """CORRECT / WRONG / UNRESOLVABLE / N_A(mbiguous query). off_graph folds
    into WRONG per task spec (1c), but is tracked separately upstream for
    auditability - see the 'off_graph' sub-count in the report."""
    mode, spec = QUERY_GROUND_TRUTH[query]
    if mode == "ambiguous":
        return "N/A"
    if status == "none":
        return "UNRESOLVABLE"
    if status == "off_graph":
        return "WRONG"
    if mode == "top_path":
        return "CORRECT" if target in TOP_PATH_LABELS else "WRONG"
    if mode == "subtree":
        if target in spec["correct"]:
            return "CORRECT"
        return "WRONG"  # in spec["wrong"], or some other graph node outside either named side
    raise AssertionError(mode)


# ============================================================
# Full pass over existing Phase 2 result files. Zero API calls - reads
# already-committed research/results/poc_results_phase2_*.json.
# ============================================================

def load_all_commits() -> list[dict]:
    """One row per COMMIT-labeled response across all 3 models x 5
    conditions x 5 runs x 12 queries. HEDGE-labeled responses are skipped
    entirely - this task only asks a second question of things already
    labeled COMMIT by the frozen scorer."""
    rows = []
    for model, tag in MODELS:
        for run in range(1, N_RUNS + 1):
            path = os.path.join(RESULTS_DIR, f"poc_results_phase2_{tag}_run{run}.json")
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
    lines = ["# Task 1: Correctness of COMMIT-labeled responses", "",
             f"{len(rows)} COMMIT-labeled responses across all Phase 2 data (3 models x "
             "5 conditions x 5 runs x 12 queries). Ground truth and extraction method "
             "are in `research/correctness_analysis.py`. Q8 ('What's holding me back...') "
             "excluded as ambiguous ground truth (N/A), not force-scored.", ""]

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
              "flat/none-like = flat_list + flat_list_prioritized + none (no weighting). "
              "If graph-like's correct-rate isn't clearly higher, the graph's added "
              "commit rate from Phase 2 would be confidence without accuracy.", "",
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
              "Even where graph-like beats flat/none on correctness, the ABSOLUTE wrong-rate "
              "when graph itself commits is reported here without spin - a model can be more "
              "accurate than the alternative while still being wrong most of the time in "
              "absolute terms.", "",
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
    print("GROUND TRUTH RANKING (seed graph, by weight)")
    print("=" * 100)
    print_ground_truth_ranking()
    print()
    print("Top path used for general priority queries:", " -> ".join(TOP_PATH_LABELS))
    print()
    print("Flagged: Q8 ('What's holding me back...') scored N/A - obstacle framing")
    print("doesn't map cleanly onto 'highest-weight node'.")
    print("Flagged: Q11 (CLI Tools 72 vs paper 70) is a narrow 2-point ground-truth margin.")
    print()

    rows = load_all_commits()
    report = render_report(rows)
    print(report)

    out_path = os.path.join(RESULTS_DIR, "correctness_analysis.md")
    with open(out_path, "w") as f:
        f.write(report)
    raw_path = os.path.join(RESULTS_DIR, "correctness_analysis_raw.json")
    with open(raw_path, "w") as f:
        json.dump(rows, f, indent=2)
    print(f"\nWrote {out_path} and {raw_path}")
