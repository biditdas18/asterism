#!/usr/bin/env python3
"""
Phase C analysis: N=100 campaign, 5 models x 2 graphs x 5 conditions x 5 runs.

Finding 1 (decisiveness): COMMIT/HEDGE labels are read directly from the
already-collected result files - they were scored live during collection by
poc_compare_v2's frozen classify_commit_or_hedge (imported unchanged, same
as every prior phase), not rescored here. validate() is re-run once at the
top as a pre-flight check, matching the standing convention.

Finding 2 (correctness): scored ONLY on the defensible-margin query set -
each query's own ground_truth (embedded in queries_n100_graph{1,2}.json)
carries a query-local near_tie flag from the corrected margin detector
(margin = ground-truth weight vs the query's OWN relevant runner-up, not a
global figure). Ambiguous and near-tie queries are excluded from
correctness, not force-scored or interpolated. They remain fully present in
Finding 1.

Finding 3 (structure-only): graph_neutral vs flat_list. deepseek-v4-pro is
missing graph1/graph_neutral (disclosed skip after 2 attempts both showed
recurring empty-but-token-consuming responses - see
n100_skipped_cells.json and n100_empty_response_events.jsonl). Its
structure-only signal is reported as graph2-only, explicitly flagged as
missing for graph1, never interpolated or averaged over a placeholder.

Usage: python research/n100_analysis.py
"""
import glob
import json
import os
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
GRAPHS = ["graph1", "graph2"]
CONDITIONS = ["graph", "flat_list_prioritized", "flat_list", "graph_neutral", "none"]
EXTRACT_TARGET = {"graph1": extract_target_g1, "graph2": extract_target_g2}


def _tag(model: str) -> str:
    import re
    return re.sub(r"[^a-zA-Z0-9_-]", "_", model)


def _cell_path(model: str, graph: str, condition: str) -> str:
    return os.path.join(RESULTS_DIR, f"n100_{_tag(model)}_{graph}_{condition}.json")


def _load_cell(model: str, graph: str, condition: str):
    path = _cell_path(model, graph, condition)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def _load_queries(graph: str) -> dict:
    with open(os.path.join(HERE, f"queries_n100_{graph}.json")) as f:
        entries = json.load(f)
    return {e["id"]: e for e in entries}


def classify_correctness_n100(gt: dict, target, status: str) -> str:
    if gt["mode"] == "ambiguous":
        return "N/A"
    if gt.get("near_tie"):
        return "NEAR_TIE_EXCLUDED"
    if status == "none":
        return "UNRESOLVABLE"
    if status == "off_graph":
        return "WRONG"
    return "CORRECT" if target in gt["correct"] else "WRONG"


def commit_rates(model: str, graph: str) -> dict:
    """condition -> (mean, min, max) COMMIT rate over 5 runs, out of 100.
    Returns None for a condition with no data (the deepseek skip)."""
    out = {}
    for cond in CONDITIONS:
        cell = _load_cell(model, graph, cond)
        if cell is None:
            out[cond] = None
            continue
        per_run = []
        for run in cell["runs"]:
            n_commit = sum(1 for r in run if r["label"] == "COMMIT")
            per_run.append(n_commit)
        out[cond] = {"mean": statistics.mean(per_run), "min": min(per_run), "max": max(per_run),
                     "per_run": per_run}
    return out


def correctness_for_cell(model: str, graph: str, condition: str, queries: dict) -> dict:
    """Among COMMIT-labeled responses in the defensible-margin set only:
    n, correct, wrong, unresolvable counts (absolute numbers)."""
    cell = _load_cell(model, graph, condition)
    if cell is None:
        return None
    extract_target = EXTRACT_TARGET[graph]
    n = correct = wrong = unresolvable = 0
    for run in cell["runs"]:
        for r in run:
            if r["label"] != "COMMIT":
                continue
            gt = queries[r["query_id"]]["ground_truth"]
            if gt["mode"] == "ambiguous" or gt.get("near_tie"):
                continue  # excluded from correctness, but was still counted in Finding 1 above
            target, status = extract_target(r["response"])
            verdict = classify_correctness_n100(gt, target, status)
            n += 1
            if verdict == "CORRECT":
                correct += 1
            elif verdict == "WRONG":
                wrong += 1
            elif verdict == "UNRESOLVABLE":
                unresolvable += 1
    return {"n": n, "correct": correct, "wrong": wrong, "unresolvable": unresolvable}


def render_report() -> str:
    lines = ["# Phase C (N=100) Analysis", ""]
    lines.append("Scorer: frozen v2 `classify_commit_or_hedge`, validated 11/11 pre-flight, "
                  "labels read from already-collected data (scored live during collection, not "
                  "rescored here). Correctness scored only on the defensible-margin query set "
                  "(graph1: 96/100, graph2: 69/100) using each query's own query-local margin, "
                  "not a global figure. deepseek-v4-pro is missing graph1/graph_neutral "
                  "(disclosed skip, not interpolated) - see notes per model.")
    lines.append("")

    queries_by_graph = {g: _load_queries(g) for g in GRAPHS}

    for model in MODELS:
        lines.append(f"## {model}")
        for graph in GRAPHS:
            lines.append(f"\n### {graph}")
            rates = commit_rates(model, graph)

            missing = [c for c in CONDITIONS if rates[c] is None]
            if missing:
                lines.append(f"**MISSING DATA: {', '.join(missing)} (disclosed skip, not interpolated)**")

            lines.append("\n| Condition | mean COMMIT/100 | min | max |")
            lines.append("|---|---|---|---|")
            for cond in CONDITIONS:
                r = rates[cond]
                if r is None:
                    lines.append(f"| {cond} | **MISSING** | - | - |")
                else:
                    lines.append(f"| {cond} | {r['mean']:.1f} | {r['min']} | {r['max']} |")

            g_r = rates["graph"]
            fl_r = rates["flat_list"]
            gn_r = rates["graph_neutral"]

            lines.append("")
            if g_r and fl_r:
                gap = g_r["mean"] - fl_r["mean"]
                lines.append(f"- **graph vs flat_list gap (deployed benefit): {gap:+.1f}** "
                             f"({g_r['mean']:.1f} vs {fl_r['mean']:.1f})")
            else:
                lines.append("- graph vs flat_list gap: N/A (missing data)")

            if gn_r and fl_r:
                gap2 = gn_r["mean"] - fl_r["mean"]
                lines.append(f"- **graph_neutral vs flat_list gap (structure-only, Finding 3): {gap2:+.1f}** "
                             f"({gn_r['mean']:.1f} vs {fl_r['mean']:.1f})")
            else:
                lines.append(f"- graph_neutral vs flat_list gap (structure-only, Finding 3): "
                             f"**N/A - graph_neutral missing for this graph, not computed**")

            # correctness, graph-like vs flat/none-like, absolute numbers
            lines.append("\n**Correctness (Finding 2, defensible-margin set only, absolute numbers):**")
            lines.append("| Condition | n COMMIT-in-set | correct | wrong | unresolvable | correct-rate |")
            lines.append("|---|---|---|---|---|---|")
            graphy_n = graphy_c = flatty_n = flatty_c = 0
            for cond in CONDITIONS:
                stats = correctness_for_cell(model, graph, cond, queries_by_graph[graph])
                if stats is None:
                    lines.append(f"| {cond} | **MISSING** | - | - | - | - |")
                    continue
                n, c, w, u = stats["n"], stats["correct"], stats["wrong"], stats["unresolvable"]
                rate = f"{c/n:.0%}" if n else "n=0"
                lines.append(f"| {cond} | {n} | {c} | {w} | {u} | {rate} |")
                if cond in ("graph", "graph_neutral"):
                    graphy_n += n; graphy_c += c
                else:
                    flatty_n += n; flatty_c += c

            g_rate = f"{graphy_c}/{graphy_n} ({graphy_c/graphy_n:.0%})" if graphy_n else "n=0"
            f_rate = f"{flatty_c}/{flatty_n} ({flatty_c/flatty_n:.0%})" if flatty_n else "n=0"
            lines.append(f"\n- graph-like (graph+graph_neutral) correct: **{g_rate}**")
            lines.append(f"- flat/none-like correct: **{f_rate}**")

        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    report = render_report()
    print(report)
    out_path = os.path.join(RESULTS_DIR, "n100_analysis.md")
    with open(out_path, "w") as f:
        f.write(report)
    print(f"\nWrote {out_path}")
