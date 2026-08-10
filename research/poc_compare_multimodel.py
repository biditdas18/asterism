#!/usr/bin/env python3
"""
Cross-model robustness run for the v2 COMMIT/HEDGE priority eval, aggregated
across multiple independent runs per model.

Reuses poc_compare_v2's scorer, held-out VALIDATION_SET, and validate()
UNCHANGED (imported, not copied) - they are pre-registered and locked, and
are never modified or re-tuned based on what comes out of this script,
including when this script's own output looks like it undercounts commits.
Only the ASSISTANT model varies; the seeded graph, the 12 PRIORITY queries,
the 3 inject conditions, and the scoring rule are all held fixed, same as
poc_compare_v2.py. extract_triples()'s own model (graph maintenance) is
untouched - see llm.converse()'s model docstring.

A single 36-call run is a noisy, small-n sample of the model's behavior -
response phrasing (and therefore the deterministic keyword scorer's label)
varies run to run even for the same model on the same queries. Rather than
chase a single-run target, this script runs the full 36-call eval N times
per model (each against a freshly reseeded isolated DB) and reports the
across-run distribution: mean/min/max per condition, and the graph-vs-
flat_list gap per run. There is no target number; whatever the distribution
turns out to be is reported as-is.

Usage: python research/poc_compare_multimodel.py <model-string> [n_runs]
  n_runs defaults to 1.
  e.g. python research/poc_compare_multimodel.py claude-sonnet-4-6 5
       python research/poc_compare_multimodel.py claude-opus-4-8 5
       python research/poc_compare_multimodel.py gpt-5.5-2026-04-23 5

Requires ANTHROPIC_API_KEY for claude-* models, OPENAI_API_KEY for
gpt-*/o1-*/o3-*/o4-* models (see .env.example).

Outputs (model+run-tagged, in research/results/ - never clobbers
poc_compare_v2's own poc_*_v2.* files or another model's/run's files):
  poc_results_<tag>_run<i>.md / .json     - full responses, per run
  poc_eval_results_<tag>_run<i>.md        - per-run commit table + labels
  poc_eval_results_<tag>_aggregate.md     - mean/min/max across all runs
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

from poc_compare import _seed_demo_graph, PRIORITY_QUERIES, MODES, EVAL_DB_PATH
from poc_compare_v2 import validate, classify_commit_or_hedge, VALIDATION_SET
from llm import converse

RESULTS_DIR = os.path.join(HERE, "results")


def _tag(model: str) -> str:
    """Filesystem-safe tag for a model string, e.g. gpt-5.5-2026-04-23 -> gpt-5_5-2026-04-23"""
    return re.sub(r"[^a-zA-Z0-9_-]", "_", model)


def run_once(model: str) -> list[dict]:
    """One full 36-call pass: reseed the isolated eval DB, run all 12
    PRIORITY queries x 3 conditions, score each response."""
    _seed_demo_graph()
    results = []
    for q in PRIORITY_QUERIES:
        by_mode = {}
        for mode in MODES:
            print(f"[{model}] Querying (inject_mode={mode}): {q!r}")
            out = converse(q, [], inject_mode=mode, model=model)
            label = classify_commit_or_hedge(out["response"])
            by_mode[mode] = {
                "response": out["response"],
                "tokens_used": out["tokens_used"],
                "label": label,
            }
        results.append({"query": q, **by_mode})
    return results


def _counts(results: list[dict]) -> dict:
    graph_c = sum(1 for r in results if r["graph"]["label"] == "COMMIT")
    flat_c = sum(1 for r in results if r["flat_list"]["label"] == "COMMIT")
    none_c = sum(1 for r in results if r["none"]["label"] == "COMMIT")
    return {"graph": graph_c, "flat_list": flat_c, "none": none_c, "gap": graph_c - flat_c}


def render_eval_markdown(model: str, run_idx: int, n_runs: int, results: list[dict]) -> str:
    counts = _counts(results)
    lines = [
        f"# Asterism PoC (cross-model): Commit-vs-Hedge Evaluation — `{model}` (run {run_idx}/{n_runs})",
        "",
        f"_Generated {datetime.datetime.now().isoformat(timespec='seconds')}_",
        "",
        f"Assistant model under test: **`{model}`**, run {run_idx} of {n_runs} independent "
        "runs. Everything else held fixed: same seeded demo graph (freshly reseeded this "
        "run), same 12 PRIORITY queries, same 3 inject conditions (graph/flat_list/none), "
        "same pre-registered COMMIT/HEDGE scorer (imported unchanged from "
        "`poc_compare_v2.py`, validated 11/11 on its held-out set once before this model's "
        "first run). No per-run target — see the aggregate file for the across-run "
        "distribution this run contributes to.",
        "",
        "## COMMIT rate this run (PRIORITY, n=12)",
        "",
        "| Condition | COMMIT rate |",
        "|---|---|",
        f"| graph | {counts['graph']}/12 |",
        f"| flat_list | {counts['flat_list']}/12 |",
        f"| none | {counts['none']}/12 |",
        "",
        f"graph-flat_list gap this run: **{counts['gap']:+d}**",
        "",
        "## Raw per-query labels (auditable)", "",
        "| # | Query | graph | flat_list | none |",
        "|---|---|---|---|---|",
    ]
    for i, r in enumerate(results, 1):
        q_short = r["query"] if len(r["query"]) <= 75 else r["query"][:72] + "..."
        lines.append(f"| {i} | {q_short} | {r['graph']['label']} | {r['flat_list']['label']} | {r['none']['label']} |")
    return "\n".join(lines)


def render_full_markdown(model: str, run_idx: int, n_runs: int, results: list[dict]) -> str:
    lines = [
        f"# Asterism PoC (cross-model): Full Responses — `{model}` (run {run_idx}/{n_runs})",
        "",
        f"_Generated {datetime.datetime.now().isoformat(timespec='seconds')}_",
        "",
        f"Full side-by-side responses backing `poc_eval_results_{_tag(model)}_run{run_idx}.md`.",
        "",
    ]
    for i, r in enumerate(results, 1):
        lines += [f"### {i}. {r['query']}", ""]
        for mode in MODES:
            lines += [
                f"**{mode}:** `{r[mode]['label']}`",
                "",
                "> " + r[mode]["response"].replace("\n", "\n> "),
                "",
                f"_tokens: {r[mode]['tokens_used']}_",
                "",
            ]
    return "\n".join(lines)


def render_aggregate_markdown(model: str, per_run: list[dict]) -> str:
    n = len(per_run)
    lines = [
        f"# Asterism PoC (cross-model, multi-run): Aggregate — `{model}`",
        "",
        f"_Generated {datetime.datetime.now().isoformat(timespec='seconds')}_",
        "",
        f"{n} independent run(s) of the full 36-call eval (12 PRIORITY queries x 3 "
        "conditions), each against a freshly reseeded isolated DB, assistant model "
        f"`{model}` held fixed. Scorer: `poc_compare_v2`'s pre-registered COMMIT/HEDGE "
        "classifier, imported unchanged, validated 11/11 on its held-out set once before "
        "this model's first run. There is no per-run target number — this reports the "
        "across-run distribution as measured, not a comparison against an expected value.",
        "",
        "## Per-run counts",
        "",
        "| Run | graph | flat_list | none | gap (graph-flat_list) |",
        "|---|---|---|---|---|",
    ]
    for r in per_run:
        lines.append(f"| {r['run']} | {r['graph']}/12 | {r['flat_list']}/12 | {r['none']}/12 | {r['gap']:+d} |")

    lines += ["", "## Aggregate across runs", "",
              "| Condition | mean | min | max |", "|---|---|---|---|"]
    for cond in ("graph", "flat_list", "none"):
        vals = [r[cond] for r in per_run]
        mean = statistics.mean(vals)
        lines.append(f"| {cond} | {mean:.1f}/12 | {min(vals)}/12 | {max(vals)}/12 |")

    gaps = [r["gap"] for r in per_run]
    gap_mean = statistics.mean(gaps)
    lines += ["", f"**graph-flat_list gap across runs:** mean {gap_mean:+.1f}, "
                  f"range [{min(gaps):+d}, {max(gaps):+d}]", ""]
    if min(gaps) <= 0:
        lines.append(
            f"**Flag:** the graph-flat_list gap is zero or negative in at least one run "
            f"for `{model}` — graph did not beat flat_list in every run."
        )
    else:
        lines.append(f"graph beat flat_list in every run for `{model}` (gap > 0 in all {n} runs).")

    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python research/poc_compare_multimodel.py <model-string> [n_runs]")
        sys.exit(1)
    model = sys.argv[1]
    n_runs = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    tag = _tag(model)

    if not validate():
        print("\nValidation FAILED against the v2 held-out set - aborting before spending "
              "API budget. This means something broke the pre-registered scorer; do not "
              "proceed without investigating.")
        sys.exit(1)

    n_ok = sum(1 for e in VALIDATION_SET if classify_commit_or_hedge(e["text"]) == e["expected"])
    print(f"\nValidation clean ({n_ok}/{len(VALIDATION_SET)}). "
          f"Proceeding to {n_runs} run(s) x 36 calls for model={model!r}.\n")

    os.makedirs(RESULTS_DIR, exist_ok=True)

    per_run = []
    for run_idx in range(1, n_runs + 1):
        print(f"\n{'=' * 70}\n[{model}] RUN {run_idx}/{n_runs}\n{'=' * 70}")
        results = run_once(model)
        counts = _counts(results)
        counts["run"] = run_idx
        per_run.append(counts)

        with open(os.path.join(RESULTS_DIR, f"poc_results_{tag}_run{run_idx}.json"), "w") as f:
            json.dump({"model": model, "run": run_idx, "n_runs": n_runs, "results": results}, f, indent=2)
        with open(os.path.join(RESULTS_DIR, f"poc_results_{tag}_run{run_idx}.md"), "w") as f:
            f.write(render_full_markdown(model, run_idx, n_runs, results))
        with open(os.path.join(RESULTS_DIR, f"poc_eval_results_{tag}_run{run_idx}.md"), "w") as f:
            f.write(render_eval_markdown(model, run_idx, n_runs, results))

        print(f"[{model}] run {run_idx}/{n_runs}: graph={counts['graph']}/12 "
              f"flat_list={counts['flat_list']}/12 none={counts['none']}/12 gap={counts['gap']:+d}")

        if os.path.exists(EVAL_DB_PATH):
            os.remove(EVAL_DB_PATH)

    agg_md = render_aggregate_markdown(model, per_run)
    with open(os.path.join(RESULTS_DIR, f"poc_eval_results_{tag}_aggregate.md"), "w") as f:
        f.write(agg_md)

    print(f"\n{'=' * 70}")
    print(agg_md)
    print(f"\nWrote per-run files (poc_results_{tag}_run*.md/.json, "
          f"poc_eval_results_{tag}_run*.md) and poc_eval_results_{tag}_aggregate.md in {RESULTS_DIR}")
