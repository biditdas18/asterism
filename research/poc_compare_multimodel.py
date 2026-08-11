#!/usr/bin/env python3
"""
Cross-model robustness run for the v2 COMMIT/HEDGE priority eval, aggregated
across multiple independent runs per model.

Reuses poc_compare_v2's scorer, held-out VALIDATION_SET, and validate()
UNCHANGED (imported, not copied) - they are pre-registered and locked, and
are never modified or re-tuned based on what comes out of this script,
including when this script's own output looks like it undercounts commits.
Only the ASSISTANT model varies; the seeded graph, the 12 PRIORITY queries,
and the scoring rule are all held fixed, same as poc_compare_v2.py.
extract_triples()'s own model (graph maintenance) is untouched - see
llm.converse()'s model docstring.

Phase 2: instruction-vs-structure isolation. Five conditions, not three:
  graph                  - weighted structure + prioritize/commit instruction
  flat_list_prioritized  - unweighted list + SAME prioritize/commit instruction
  flat_list               - unweighted list + neutral instruction
  graph_neutral           - weighted structure + neutral instruction
  none                     - no context at all
graph/flat_list/none are unchanged from Phase 1. CONDITIONS here is a local
constant - it does NOT mutate poc_compare.py's/poc_compare_v2.py's own
MODES, so poc_compare_v2.py's already-locked 3-condition eval is untouched.

A single 36-call run (now 60: 12 queries x 5 conditions) is a noisy,
small-n sample of model behavior - response phrasing (and therefore the
deterministic keyword scorer's label) varies run to run even for the same
model. Rather than chase a single-run target, this script runs the full
eval N times per model (each against a freshly reseeded isolated DB) and
reports the across-run distribution: mean/min/max per condition. There is
no target number; whatever the distribution turns out to be is reported.

E-FIX: the eval DB is reseeded from the pristine seed immediately before
EVERY individual call (not once per run), with a fail-fast invariant check
that the seed's (node, edge) count never drifts within a run.

Truncation guard: llm.converse() itself now raises if a response is empty
or was truncated at the token ceiling on either backend, for any model -
this script never sees or scores a truncated/empty response; it either
gets real data or the run crashes loudly.

Usage: python research/poc_compare_multimodel.py <model-string> [n_runs]
  n_runs defaults to 1.
  e.g. python research/poc_compare_multimodel.py claude-sonnet-4-6 5

Requires ANTHROPIC_API_KEY for claude-* models, OPENAI_API_KEY for
gpt-*/o1-*/o3-*/o4-* models (see .env.example).

Outputs (model+run-tagged, in research/results/ - never clobbers
poc_compare_v2's or Phase 1's own files):
  poc_results_phase2_<tag>_run<i>.md / .json     - full responses, per run
  poc_eval_results_phase2_<tag>_run<i>.md        - per-run commit table + labels
  poc_eval_results_phase2_<tag>_aggregate.md     - mean/min/max + verdict across runs
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

from poc_compare import _seed_demo_graph, PRIORITY_QUERIES, EVAL_DB_PATH
from poc_compare_v2 import validate, classify_commit_or_hedge, VALIDATION_SET
from llm import converse
from db import get_connection

RESULTS_DIR = os.path.join(HERE, "results")
TEMPERATURE = 1.0
CONDITIONS = ["graph", "flat_list_prioritized", "flat_list", "graph_neutral", "none"]


def _tag(model: str) -> str:
    """Filesystem-safe tag for a model string, e.g. gpt-5.5-2026-04-23 -> gpt-5_5-2026-04-23"""
    return re.sub(r"[^a-zA-Z0-9_-]", "_", model)


def _seed_node_edge_count() -> tuple[int, int]:
    with get_connection() as conn:
        n = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        e = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    return n, e


def run_once(model: str) -> list[dict]:
    """One full 60-call pass: 12 PRIORITY queries x 5 conditions, scored.

    Reseeds before every call (E-fix) and asserts the seed constant across
    the run. temperature=1.0 sent explicitly on every call. Truncation/
    empty-response guarding happens inside llm.converse() itself - if this
    function returns normally, every response in it is real, complete data.
    """
    results = []
    baseline: tuple[int, int] | None = None
    for q in PRIORITY_QUERIES:
        by_mode = {}
        for mode in CONDITIONS:
            _seed_demo_graph()
            counts = _seed_node_edge_count()
            if baseline is None:
                baseline = counts
                print(f"[{model}] seed baseline established: {counts[0]} nodes, {counts[1]} edges")
            elif counts != baseline:
                raise RuntimeError(
                    f"E-FIX INVARIANT VIOLATED at query={q!r} mode={mode!r}: "
                    f"seed graph was {counts} (nodes, edges), expected constant "
                    f"baseline {baseline}. Aborting before the API call - do not "
                    f"trust any data from this run."
                )
            print(f"[{model}] seed OK {counts} temp={TEMPERATURE} | "
                  f"Querying (inject_mode={mode}): {q!r}")
            out = converse(q, [], inject_mode=mode, model=model, temperature=TEMPERATURE)
            label = classify_commit_or_hedge(out["response"])
            by_mode[mode] = {
                "response": out["response"],
                "tokens_used": out["tokens_used"],
                "label": label,
            }
        results.append({"query": q, **by_mode})

    print(f"[{model}] E-FIX invariant confirmed: all {len(PRIORITY_QUERIES) * len(CONDITIONS)} "
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
        f"# Asterism PoC Phase 2 (instruction vs. structure): `{model}` (run {run_idx}/{n_runs})",
        "",
        f"_Generated {datetime.datetime.now().isoformat(timespec='seconds')}_",
        "",
        f"Assistant model under test: **`{model}`**, run {run_idx} of {n_runs}. "
        f"temperature={TEMPERATURE} pinned, reseed-per-call (E-fix), universal "
        "truncation/empty-response guard active. Same seeded demo graph, same 12 "
        "PRIORITY queries, same pre-registered COMMIT/HEDGE scorer (imported unchanged "
        "from `poc_compare_v2.py`, validated 11/11 on its held-out set once before this "
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
        f"# Asterism PoC Phase 2: Full Responses — `{model}` (run {run_idx}/{n_runs})",
        "",
        f"_Generated {datetime.datetime.now().isoformat(timespec='seconds')}_",
        "",
        f"Full side-by-side responses backing `poc_eval_results_phase2_{_tag(model)}_run{run_idx}.md`.",
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
    """
    graph vs flat_list_prioritized: graph wins -> structural signal
      (structure adds value ON TOP of the instruction the two conditions share)
    flat_list_prioritized vs flat_list: this wins -> instructional signal
      (the instruction alone, with no structure, already lifts commitment)
    """
    structural = means["graph"] > means["flat_list_prioritized"]
    instructional = means["flat_list_prioritized"] > means["flat_list"]
    if structural and instructional:
        return "MIXED"
    if structural:
        return "STRUCTURAL"
    if instructional:
        return "INSTRUCTIONAL"
    return "MIXED"  # neither comparison shows a clear positive signal


def render_aggregate_markdown(model: str, per_run: list[dict]) -> str:
    n = len(per_run)
    means = {mode: statistics.mean([r[mode] for r in per_run]) for mode in CONDITIONS}
    mins = {mode: min(r[mode] for r in per_run) for mode in CONDITIONS}
    maxs = {mode: max(r[mode] for r in per_run) for mode in CONDITIONS}
    verdict = _verdict(means)

    lines = [
        f"# Asterism PoC Phase 2 (instruction vs. structure): Aggregate — `{model}`",
        "",
        f"_Generated {datetime.datetime.now().isoformat(timespec='seconds')}_",
        "",
        f"{n} independent run(s), 12 PRIORITY queries x 5 conditions each, assistant "
        f"model `{model}` held fixed, temperature={TEMPERATURE} pinned, reseed-per-call, "
        "universal truncation/empty-response guard active throughout (zero truncated or "
        "empty responses in this data - `converse()` raises rather than allowing one "
        "through). Scorer: `poc_compare_v2`'s pre-registered COMMIT/HEDGE classifier, "
        "imported unchanged, validated 11/11 on its held-out set once before this "
        "model's first run.",
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
        "## Verdict comparisons (mean COMMIT count over 5 runs)",
        "",
        f"- graph vs flat_list_prioritized: {g:.1f} vs {flp:.1f}  "
        f"({'graph wins -> structural signal' if g > flp else ('tie' if g == flp else 'flat_list_prioritized wins -> no structural signal')})",
        f"- flat_list_prioritized vs flat_list: {flp:.1f} vs {fl:.1f}  "
        f"({'flat_list_prioritized wins -> instructional signal' if flp > fl else ('tie' if flp == fl else 'flat_list wins -> no instructional signal')})",
        f"- graph_neutral vs flat_list (structure alone, no instruction): {gn:.1f} vs {fl:.1f}  "
        f"({'graph_neutral wins -> structure helps even without the instruction' if gn > fl else ('tie' if gn == fl else 'flat_list wins -> structure alone does not help')})",
        "",
        f"**Verdict for `{model}`: {verdict}**",
    ]
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
          f"Proceeding to {n_runs} run(s) x {len(PRIORITY_QUERIES) * len(CONDITIONS)} "
          f"calls for model={model!r}, temperature={TEMPERATURE}.\n")

    os.makedirs(RESULTS_DIR, exist_ok=True)

    per_run = []
    for run_idx in range(1, n_runs + 1):
        print(f"\n{'=' * 70}\n[{model}] RUN {run_idx}/{n_runs}\n{'=' * 70}")
        results = run_once(model)
        counts = _counts(results)
        counts["run"] = run_idx
        per_run.append(counts)

        with open(os.path.join(RESULTS_DIR, f"poc_results_phase2_{tag}_run{run_idx}.json"), "w") as f:
            json.dump({"model": model, "run": run_idx, "n_runs": n_runs,
                       "temperature": TEMPERATURE, "conditions": CONDITIONS,
                       "results": results}, f, indent=2)
        with open(os.path.join(RESULTS_DIR, f"poc_results_phase2_{tag}_run{run_idx}.md"), "w") as f:
            f.write(render_full_markdown(model, run_idx, n_runs, results))
        with open(os.path.join(RESULTS_DIR, f"poc_eval_results_phase2_{tag}_run{run_idx}.md"), "w") as f:
            f.write(render_eval_markdown(model, run_idx, n_runs, results))

        print(f"[{model}] run {run_idx}/{n_runs}: " +
              "  ".join(f"{mode}={counts[mode]}/12" for mode in CONDITIONS))

        if os.path.exists(EVAL_DB_PATH):
            os.remove(EVAL_DB_PATH)

    agg_md = render_aggregate_markdown(model, per_run)
    with open(os.path.join(RESULTS_DIR, f"poc_eval_results_phase2_{tag}_aggregate.md"), "w") as f:
        f.write(agg_md)

    print(f"\n{'=' * 70}")
    print(agg_md)
    print(f"\nWrote per-run files (poc_results_phase2_{tag}_run*.md/.json, "
          f"poc_eval_results_phase2_{tag}_run*.md) and "
          f"poc_eval_results_phase2_{tag}_aggregate.md in {RESULTS_DIR}")
