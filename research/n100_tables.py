#!/usr/bin/env python3
"""Numbers-only rebuild of the 4 requested tables, from committed result files."""
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from correctness_analysis import extract_target as extract_target_g1
from correctness_analysis_graph2 import extract_target as extract_target_g2

RESULTS_DIR = os.path.join(HERE, "results")
MODELS = ["claude-sonnet-4-6", "claude-opus-4-8", "gpt-5.5-2026-04-23",
          "deepseek-v4-pro", "kimi-k3"]
MODEL_LABEL = {"claude-sonnet-4-6": "sonnet", "claude-opus-4-8": "opus",
               "gpt-5.5-2026-04-23": "gpt-5.5", "deepseek-v4-pro": "deepseek-v4-pro",
               "kimi-k3": "kimi-k3"}
GRAPHS = ["graph1", "graph2"]
GRAPH_LABEL = {"graph1": "G1", "graph2": "G2"}
CONDITIONS = ["none", "flat_list", "flat_list_prioritized", "graph", "graph_neutral"]
EXTRACT_TARGET = {"graph1": extract_target_g1, "graph2": extract_target_g2}


def _tag(model):
    return re.sub(r"[^a-zA-Z0-9_-]", "_", model)


def _load_cell(model, graph, condition):
    path = os.path.join(RESULTS_DIR, f"n100_{_tag(model)}_{graph}_{condition}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def _load_queries(graph):
    with open(os.path.join(HERE, f"queries_n100_{graph}.json")) as f:
        entries = json.load(f)
    return {e["id"]: e for e in entries}


def commit_counts_per_run(model, graph, condition):
    cell = _load_cell(model, graph, condition)
    if cell is None:
        return None
    return [sum(1 for r in run if r["label"] == "COMMIT") for run in cell["runs"]]


def correct_hits_per_run(model, graph, condition, queries):
    """Per-run count of queries where the response CORRECTLY named the
    highest-priority item, scored ONLY over the defensible-margin set
    (ambiguous + near-tie excluded from the denominator entirely)."""
    cell = _load_cell(model, graph, condition)
    if cell is None:
        return None
    extract_target = EXTRACT_TARGET[graph]
    per_run = []
    for run in cell["runs"]:
        correct = 0
        for r in run:
            gt = queries[r["query_id"]]["ground_truth"]
            if gt["mode"] == "ambiguous" or gt.get("near_tie"):
                continue
            if r["label"] != "COMMIT":
                continue
            target, status = extract_target(r["response"])
            if status == "off_graph" or status == "none":
                continue
            if target in gt["correct"]:
                correct += 1
        per_run.append(correct)
    return per_run


missing = []
for m in MODELS:
    for g in GRAPHS:
        for c in CONDITIONS:
            if _load_cell(m, g, c) is None:
                missing.append(f"{m}|{g}|{c}")

print("=== MISSING/SKIPPED CELLS ===")
for k in missing:
    print(" ", k)
print()

# ---------------- TABLE 1 ----------------
print("=== TABLE 1: COMMIT RATE (mean /100 over 5 runs) ===")
print("model | graph | none | flat_list | flat_list_prioritized | graph | graph_neutral")
t1 = {}
for m in MODELS:
    for g in GRAPHS:
        row = []
        for c in CONDITIONS:
            counts = commit_counts_per_run(m, g, c)
            row.append(None if counts is None else statistics.mean(counts))
        t1[(m, g)] = row
        cells = " | ".join("SKIP" if v is None else f"{v:.1f}" for v in row)
        print(f"{MODEL_LABEL[m]} | {GRAPH_LABEL[g]} | {cells}")
print()

# ---------------- TABLE 2 ----------------
print("=== TABLE 2: KEY GAPS (commit-rate points) ===")
print("model | graph | (graph - flat_list) | (graph_neutral - flat_list)")
for m in MODELS:
    for g in GRAPHS:
        row = t1[(m, g)]
        none_, fl, flp, gr, gn = row
        gap1 = gr - fl
        gap2 = "N/A" if gn is None else f"{gn - fl:+.1f}"
        print(f"{MODEL_LABEL[m]} | {GRAPH_LABEL[g]} | {gap1:+.1f} | {gap2}")
print()

# ---------------- TABLE 3 ----------------
print("=== TABLE 3: CORRECTNESS DENOMINATOR ===")
print("graph | queries_scored_for_correctness | near_ties_excluded")
queries_by_graph = {}
for g in GRAPHS:
    q = _load_queries(g)
    queries_by_graph[g] = q
    n_ambig = sum(1 for e in q.values() if e["ground_truth"]["mode"] == "ambiguous")
    n_neartie = sum(1 for e in q.values() if e["ground_truth"].get("near_tie"))
    n_scored = 100 - n_ambig - n_neartie
    print(f"{GRAPH_LABEL[g]} | {n_scored} | {n_neartie} (+ {n_ambig} ambiguous, also excluded)")
print()

print("=== TABLE 3b: CORRECTNESS (absolute % of queries_scored_for_correctness) ===")
print("model | graph | flat_list_correct% | graph_correct% | graph_neutral_correct%")
denom = {g: 100 - sum(1 for e in queries_by_graph[g].values()
                       if e["ground_truth"]["mode"] == "ambiguous" or e["ground_truth"].get("near_tie"))
         for g in GRAPHS}
t3_runs = {}
for m in MODELS:
    for g in GRAPHS:
        vals = {}
        for c in ["flat_list", "graph", "graph_neutral"]:
            per_run = correct_hits_per_run(m, g, c, queries_by_graph[g])
            t3_runs[(m, g, c)] = per_run
            if per_run is None:
                vals[c] = "SKIP"
            else:
                mean_correct = statistics.mean(per_run)
                pct = 100 * mean_correct / denom[g]
                vals[c] = f"{pct:.0f}%"
        print(f"{MODEL_LABEL[m]} | {GRAPH_LABEL[g]} | {vals['flat_list']} | {vals['graph']} | {vals['graph_neutral']}")
print()

# ---------------- TABLE 4 ----------------
print("=== TABLE 4: RUN-LEVEL CONSISTENCY ===")
print("model | graph | graph>flat (x/5) | graph_neutral>flat (x/5)")
for m in MODELS:
    for g in GRAPHS:
        counts = {c: commit_counts_per_run(m, g, c) for c in ["flat_list", "graph", "graph_neutral"]}
        fl = counts["flat_list"]
        gr = counts["graph"]
        gn = counts["graph_neutral"]
        n_gr_wins = sum(1 for a, b in zip(gr, fl) if a > b)
        n_gn_wins = "N/A" if gn is None else sum(1 for a, b in zip(gn, fl) if a > b)
        gn_str = "N/A" if gn is None else f"{n_gn_wins}/5"
        print(f"{MODEL_LABEL[m]} | {GRAPH_LABEL[g]} | {n_gr_wins}/5 | {gn_str}")
