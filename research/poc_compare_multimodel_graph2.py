#!/usr/bin/env python3
"""
Phase A: graph-2 ("Priya") replication check for the Phase 2 5-condition x
multi-model eval. Structurally identical to poc_compare_multimodel.py -
same 5 conditions, same temperature pin, same reseed-per-call (E-fix)
invariant, same universal truncation/empty-response guard, same frozen v2
scorer imported unchanged - with only the seed graph and query set swapped
for seed_graph_2's DEMO_GRAPH_2 / PRIORITY_QUERIES_2 (Priya persona,
approved design: different domain mix, different weight shape, defensible
6-7pt top-of-graph margin). poc_compare.py / poc_compare_multimodel.py and
their output files are untouched by this script.

Usage: python research/poc_compare_multimodel_graph2.py <model-string> [n_runs]
Output files (research/results/, "_graph2_" tagged, never clobbers graph-1's
poc_results_phase2_*/poc_eval_results_phase2_* files):
  poc_results_phase2_graph2_<tag>_run<i>.md / .json
  poc_eval_results_phase2_graph2_<tag>_run<i>.md
  poc_eval_results_phase2_graph2_<tag>_aggregate.md
"""
import datetime
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from seed_graph_2 import _seed_demo_graph_2, PRIORITY_QUERIES_2, EVAL_DB_PATH_2
from poc_compare_v2 import validate, classify_commit_or_hedge, VALIDATION_SET
from llm import converse
from db import get_connection

RESULTS_DIR = os.path.join(HERE, "results")
TEMPERATURE = 1.0
CONDITIONS = ["graph", "flat_list_prioritized", "flat_list", "graph_neutral", "none"]


def _tag(model: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", model)


def _seed_node_edge_count() -> tuple[int, int]:
    with get_connection() as conn:
        n = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        e = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    return n, e


def run_once(model: str) -> list[dict]:
    """One full 60-call pass against graph 2: 12 PRIORITY queries x 5
    conditions, scored. Reseeds before every call (E-fix) and asserts the
    seed constant across the run."""
    results = []
    baseline: tuple[int, int] | None = None
    for q in PRIORITY_QUERIES_2:
        by_mode = {}
        for mode in CONDITIONS:
            _seed_demo_graph_2()
            counts = _seed_node_edge_count()
            if baseline is None:
                baseline = counts
                print(f"[{model}][graph2] seed baseline established: {counts[0]} nodes, {counts[1]} edges")
            elif counts != baseline:
                raise RuntimeError(
                    f"E-FIX INVARIANT VIOLATED at query={q!r} mode={mode!r}: "
                    f"seed graph was {counts} (nodes, edges), expected constant "
                    f"baseline {baseline}. Aborting before the API call - do not "
                    f"trust any data from this run."
                )
            print(f"[{model}][graph2] seed OK {counts} temp={TEMPERATURE} | "
                  f"Querying (inject_mode={mode}): {q!r}")
            out = converse(q, [], inject_mode=mode, model=model, temperature=TEMPERATURE)
            label = classify_commit_or_hedge(out["response"])
            by_mode[mode] = {
                "response": out["response"],
                "tokens_used": out["tokens_used"],
                "label": label,
            }
        results.append({"query": q, **by_mode})

    print(f"[{model}][graph2] E-FIX invariant confirmed: all {len(PRIORITY_QUERIES_2) * len(CONDITIONS)} "
          f"calls this run started from an identical seed {baseline} (nodes, edges). "
          f"temperature={TEMPERATURE} sent on every call. Zero truncated/empty responses "
          f"(converse() would have raised otherwise).")
    return results


def _counts(results: list[dict]) -> dict:
    c = {mode: sum(1 for r in results if r[mode]["label"] == "COMMIT") for mode in CONDITIONS}
    c["gap_graph_vs_flat_list"] = c["graph"] - c["flat_list"]
    return c


def render_eval_markdown(model: str, run_idx: int, n_runs: int, results: list[dict]) -> str:
    counts = _counts(results)
    lines = [
        f"# Asterism PoC Phase 2 / Graph 2 (Priya): `{model}` (run {run_idx}/{n_runs})",
        "",
        f"_Generated {datetime.datetime.now().isoformat(timespec='seconds')}_",
        "",
        f"Assistant model under test: **`{model}`**, run {run_idx} of {n_runs}, against "
        "seed_graph_2's Priya persona (freelance designer/studio owner). "
        f"temperature={TEMPERATURE} pinned, reseed-per-call (E-fix), universal "
        "truncation/empty-response guard active. Same 12 graph-2 PRIORITY queries, "
        "same pre-registered COMMIT/HEDGE scorer (imported unchanged from "
        "`poc_compare_v2.py`, validated 11/11 on its held-out set once before this "
        "model's first run).",
        "",
        "## COMMIT rate this run (PRIORITY, n=12)",
        "",
        "| Condition | COMMIT rate |",
        "|---|---|",
    ]
    for mode in CONDITIONS:
        lines.append(f"| {mode} | {counts[mode]}/12 |")
    lines += ["", "## Raw per-query labels (auditable)", "",
              "| # | Query | " + " | ".join(CONDITIONS) + " |",
              "|---|---|" + "---|" * len(CONDITIONS)]
    for i, r in enumerate(results, 1):
        q_short = r["query"] if len(r["query"]) <= 60 else r["query"][:57] + "..."
        row = " | ".join(r[mode]["label"] for mode in CONDITIONS)
        lines.append(f"| {i} | {q_short} | {row} |")
    return "\n".join(lines)


def render_full_markdown(model: str, run_idx: int, n_runs: int, results: list[dict]) -> str:
    lines = [
        f"# Asterism PoC Phase 2 / Graph 2 (Priya): Full Responses — `{model}` (run {run_idx}/{n_runs})",
        "",
        f"_Generated {datetime.datetime.now().isoformat(timespec='seconds')}_",
        "",
        f"Full side-by-side responses backing `poc_eval_results_phase2_graph2_{_tag(model)}_run{run_idx}.md`.",
        "",
    ]
    for i, r in enumerate(results, 1):
        lines += [f"### {i}. {r['query']}", ""]
        for mode in CONDITIONS:
            lines += [
                f"**{mode}:** `{r[mode]['label']}`",
                "",
                "> " + r[mode]["response"].replace("\n", "\n> "),
                "",
                f"_tokens: {r[mode]['tokens_used']}_",
                "",
            ]
    return "\n".join(lines)


def _verdict(means: dict) -> str:
    structural = means["graph"] > means["flat_list_prioritized"]
    instructional = means["flat_list_prioritized"] > means["flat_list"]
    if structural and instructional:
        return "MIXED"
    if structural:
        return "STRUCTURAL"
    if instructional:
        return "INSTRUCTIONAL"
    return "MIXED"


def render_aggregate_markdown(model: str, per_run: list[dict]) -> str:
    n = len(per_run)
    means = {mode: statistics.mean([r[mode] for r in per_run]) for mode in CONDITIONS}
    mins = {mode: min(r[mode] for r in per_run) for mode in CONDITIONS}
    maxs = {mode: max(r[mode] for r in per_run) for mode in CONDITIONS}
    verdict = _verdict(means)

    lines = [
        f"# Asterism PoC Phase 2 / Graph 2 (Priya): Aggregate — `{model}`",
        "",
        f"_Generated {datetime.datetime.now().isoformat(timespec='seconds')}_",
        "",
        f"{n} independent run(s) against seed_graph_2 (Priya persona), 12 PRIORITY "
        f"queries x 5 conditions each, assistant model `{model}` held fixed, "
        f"temperature={TEMPERATURE} pinned, reseed-per-call, universal truncation/"
        "empty-response guard active throughout. Scorer: `poc_compare_v2`'s "
        "pre-registered COMMIT/HEDGE classifier, imported unchanged, validated "
        "11/11 on its held-out set once before this model's first run.",
        "",
        "## Per-run counts",
        "",
        "| Run | " + " | ".join(CONDITIONS) + " |",
        "|---|" + "---|" * len(CONDITIONS),
    ]
    for r in per_run:
        row = " | ".join(f"{r[mode]}/12" for mode in CONDITIONS)
        lines.append(f"| {r['run']} | {row} |")

    lines += ["", "## Aggregate across runs (mean [min-max])", "",
              "| Condition | mean | min | max |", "|---|---|---|---|"]
    for mode in CONDITIONS:
        lines.append(f"| {mode} | {means[mode]:.1f}/12 | {mins[mode]}/12 | {maxs[mode]}/12 |")

    g, flp, fl, gn = means["graph"], means["flat_list_prioritized"], means["flat_list"], means["graph_neutral"]
    lines += [
        "",
        "## Verdict comparisons (mean COMMIT count over runs)",
        "",
        f"- graph vs flat_list_prioritized: {g:.1f} vs {flp:.1f}  "
        f"({'graph wins -> structural signal' if g > flp else ('tie' if g == flp else 'flat_list_prioritized wins -> no structural signal')})",
        f"- flat_list_prioritized vs flat_list: {flp:.1f} vs {fl:.1f}  "
        f"({'flat_list_prioritized wins -> instructional signal' if flp > fl else ('tie' if flp == fl else 'flat_list wins -> no instructional signal')})",
        f"- graph_neutral vs flat_list (structure alone, no instruction): {gn:.1f} vs {fl:.1f}  "
        f"({'graph_neutral wins -> structure helps even without the instruction' if gn > fl else ('tie' if gn == fl else 'flat_list wins -> structure alone does not help')})",
        f"- graph_neutral vs graph (does the instruction add anything on top of structure): {gn:.1f} vs {g:.1f}  "
        f"({'graph_neutral wins' if gn > g else ('tie' if gn == g else 'graph wins')})",
        "",
        f"**Verdict for `{model}` on graph 2: {verdict}**",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python research/poc_compare_multimodel_graph2.py <model-string> [n_runs] [start_run]")
        sys.exit(1)
    model = sys.argv[1]
    n_runs = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    start_run = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    tag = _tag(model)

    if not validate():
        print("\nValidation FAILED against the v2 held-out set - aborting before spending "
              "API budget.")
        sys.exit(1)

    n_ok = sum(1 for e in VALIDATION_SET if classify_commit_or_hedge(e["text"]) == e["expected"])
    print(f"\nValidation clean ({n_ok}/{len(VALIDATION_SET)}). "
          f"Proceeding to run(s) {start_run}..{n_runs} x {len(PRIORITY_QUERIES_2) * len(CONDITIONS)} "
          f"calls for model={model!r} against graph 2, temperature={TEMPERATURE}.\n")

    os.makedirs(RESULTS_DIR, exist_ok=True)

    per_run = []
    for prior_run in range(1, start_run):
        prior_path = os.path.join(RESULTS_DIR, f"poc_results_phase2_graph2_{tag}_run{prior_run}.json")
        with open(prior_path) as f:
            prior_data = json.load(f)
        prior_counts = _counts(prior_data["results"])
        prior_counts["run"] = prior_run
        per_run.append(prior_counts)
        print(f"[{model}][graph2] loaded existing run {prior_run} from {prior_path} (not re-run)")

    for run_idx in range(start_run, n_runs + 1):
        print(f"\n{'=' * 70}\n[{model}][graph2] RUN {run_idx}/{n_runs}\n{'=' * 70}")
        results = run_once(model)
        counts = _counts(results)
        counts["run"] = run_idx
        per_run.append(counts)

        with open(os.path.join(RESULTS_DIR, f"poc_results_phase2_graph2_{tag}_run{run_idx}.json"), "w") as f:
            json.dump({"model": model, "graph": "graph2_priya", "run": run_idx, "n_runs": n_runs,
                       "temperature": TEMPERATURE, "conditions": CONDITIONS,
                       "results": results}, f, indent=2)
        with open(os.path.join(RESULTS_DIR, f"poc_results_phase2_graph2_{tag}_run{run_idx}.md"), "w") as f:
            f.write(render_full_markdown(model, run_idx, n_runs, results))
        with open(os.path.join(RESULTS_DIR, f"poc_eval_results_phase2_graph2_{tag}_run{run_idx}.md"), "w") as f:
            f.write(render_eval_markdown(model, run_idx, n_runs, results))

        print(f"[{model}][graph2] run {run_idx}/{n_runs}: " +
              "  ".join(f"{mode}={counts[mode]}/12" for mode in CONDITIONS))

        if os.path.exists(EVAL_DB_PATH_2):
            os.remove(EVAL_DB_PATH_2)

    agg_md = render_aggregate_markdown(model, per_run)
    with open(os.path.join(RESULTS_DIR, f"poc_eval_results_phase2_graph2_{tag}_aggregate.md"), "w") as f:
        f.write(agg_md)

    print(f"\n{'=' * 70}")
    print(agg_md)
    print(f"\nWrote per-run files (poc_results_phase2_graph2_{tag}_run*.md/.json, "
          f"poc_eval_results_phase2_graph2_{tag}_run*.md) and "
          f"poc_eval_results_phase2_graph2_{tag}_aggregate.md in {RESULTS_DIR}")
