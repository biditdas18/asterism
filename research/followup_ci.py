#!/usr/bin/env python3
"""Paired bootstrap intervals on the contrasts that bootstrap_ci.py does not cover.

Re-analysis only. Reads the committed per-cell result files, the frozen
COMMIT/HEDGE labels already in them, and the committed per-graph ground truth.
No model calls, no re-scoring, no relabelling. The commit/hedge scorer is not
imported, invoked, or adjusted here: its labels are read as data.

Three families of contrast, all paired by query identifier and resampled with
replacement 10,000 times:

  commit_rate   flat_list_prioritized - flat_list  (the instruction-only gap;
                the deployed and structure-only gaps are in bootstrap_ci.py)
  correct_rate  correct answers per scorable query, each condition - flat_list
  precision     correct answers per committed answer, structure-only minus
                instruction-only, and deployed minus flat

commit_rate is computed over all 100 queries, matching bootstrap_ci.py.
correct_rate and precision are computed over the defensible-margin set only
(graph1 96/100, graph2 69/100), matching n100_analysis.py: ambiguous and
near-tie queries are excluded, never force-scored.

precision is a ratio of sums, not a mean of per-query ratios, because a query
with no committed answer in a condition has no defined precision. Each
resample therefore recomputes sum(correct)/sum(commit) over the resampled
queries -- a ratio estimator. Resamples in which a condition has no committed
answer at all are dropped and counted, not silently treated as zero.

Every row draws from its OWN generator, seeded from (SEED, model, graph,
metric, contrast). This is deliberate: a single shared stream would make each
row's interval depend on how many rows were computed before it, so adding a
contrast later would silently move intervals already published. Row-local
seeding makes each interval a function of its own cell only.

Usage:  python research/followup_ci.py
"""

import csv
import glob
import hashlib
import json
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from correctness_analysis import extract_target as extract_target_g1
from correctness_analysis_graph2 import extract_target as extract_target_g2

RESULTS = os.path.join(HERE, "results")
OUT = os.path.join(RESULTS, "n100_followup_ci.csv")

MODELS = ["claude-sonnet-4-6", "claude-opus-4-8", "gpt-5.5-2026-04-23",
          "deepseek-v4-pro", "kimi-k3"]
LABEL = {"claude-sonnet-4-6": "Sonnet", "claude-opus-4-8": "Opus",
         "gpt-5.5-2026-04-23": "GPT", "deepseek-v4-pro": "DeepSeek",
         "kimi-k3": "Kimi"}
GRAPHS = ["graph1", "graph2"]
EXTRACT = {"graph1": extract_target_g1, "graph2": extract_target_g2}

SEED = 20260902
B = 10000


def _tag(model):
    return re.sub(r"[^a-zA-Z0-9_-]", "_", model)


def _rng(*parts):
    """Row-local generator: independent of evaluation order."""
    key = "|".join(str(p) for p in (SEED,) + parts).encode()
    return np.random.default_rng(int(hashlib.sha256(key).hexdigest()[:16], 16))


def load_cell(model, graph, cond):
    path = os.path.join(RESULTS, f"n100_{_tag(model)}_{graph}_{cond}.json")
    if not os.path.exists(path):
        return None
    with open(path) as fh:
        return json.load(fh)["runs"]


def load_queries(graph):
    with open(os.path.join(HERE, f"queries_n100_{graph}.json")) as fh:
        return {e["id"]: e for e in json.load(fh)}


def matrices(runs, graph, queries, scorable_only):
    """Return (commit, correct, ids): runs x queries indicator matrices.

    commit[i][j] = 1 if run i committed on query j.
    correct[i][j] = 1 if run i committed AND the committed answer is correct.
    Correctness verdicts use the committed per-graph extractor and the query's
    own ground truth, exactly as n100_analysis.py does.
    """
    ids = [q["query_id"] for q in runs[0]]
    for r in runs:
        assert [q["query_id"] for q in r] == ids, "query order differs across runs"
    extract_target = EXTRACT[graph]
    keep = []
    for j, qid in enumerate(ids):
        gt = queries[qid]["ground_truth"]
        ok = not (gt["mode"] == "ambiguous" or gt.get("near_tie"))
        if ok or not scorable_only:
            keep.append(j)
    commit = np.zeros((len(runs), len(keep)))
    correct = np.zeros((len(runs), len(keep)))
    for i, run in enumerate(runs):
        for jj, j in enumerate(keep):
            rec = run[j]
            if rec["label"] != "COMMIT":
                continue
            commit[i, jj] = 1.0
            if not scorable_only:
                continue
            gt = queries[rec["query_id"]]["ground_truth"]
            target, status = extract_target(rec["response"])
            if status not in ("none", "off_graph") and target in gt["correct"]:
                correct[i, jj] = 1.0
    return commit, correct, [ids[j] for j in keep]


def boot_mean_diff(a_mat, b_mat, rng):
    """Paired bootstrap on a difference of per-query rates (percentage points)."""
    d = (a_mat.mean(axis=0) - b_mat.mean(axis=0)) * 100.0
    n = d.size
    draws = d[rng.integers(0, n, size=(B, n))].mean(axis=1)
    lo, hi = np.percentile(draws, [2.5, 97.5])
    tail = max(min((draws <= 0).mean(), (draws >= 0).mean()), 0.5 / B)
    per_run = (a_mat.mean(axis=1) - b_mat.mean(axis=1)) * 100.0
    return dict(mean=float(d.mean()), lo=float(lo), hi=float(hi),
                p=float(min(1.0, 2 * tail)), dropped=0,
                runs_pos=int((per_run > 0).sum()), n_runs=int(per_run.size),
                sd_runs=float(per_run.std(ddof=1)))


def boot_ratio_diff(ma, mb, rng):
    """Paired bootstrap on a difference of ratios of sums (percentage points).

    ma and mb are (commit, correct, ids) triples. Each resample recomputes
    sum(correct)/sum(commit) per condition over the resampled queries.
    Run consistency is the per-run precision difference, using only that run's
    committed answers; a run in which either condition committed to nothing
    has no defined precision and is not counted.
    """
    a_c, a_n = ma[1].sum(axis=0), ma[0].sum(axis=0)
    b_c, b_n = mb[1].sum(axis=0), mb[0].sum(axis=0)
    ra_c, ra_n = ma[1].sum(axis=1), ma[0].sum(axis=1)
    rb_c, rb_n = mb[1].sum(axis=1), mb[0].sum(axis=1)
    ok = (ra_n > 0) & (rb_n > 0)
    per_run = (ra_c[ok] / ra_n[ok] - rb_c[ok] / rb_n[ok]) * 100.0
    n = a_c.size
    idx = rng.integers(0, n, size=(B, n))
    ac, an = a_c[idx].sum(axis=1), a_n[idx].sum(axis=1)
    bc, bn = b_c[idx].sum(axis=1), b_n[idx].sum(axis=1)
    good = (an > 0) & (bn > 0)
    draws = (ac[good] / an[good] - bc[good] / bn[good]) * 100.0
    point = (a_c.sum() / a_n.sum() - b_c.sum() / b_n.sum()) * 100.0
    lo, hi = np.percentile(draws, [2.5, 97.5])
    tail = max(min((draws <= 0).mean(), (draws >= 0).mean()), 0.5 / B)
    return dict(mean=float(point), lo=float(lo), hi=float(hi),
                p=float(min(1.0, 2 * tail)), dropped=int((~good).sum()),
                runs_pos=int((per_run > 0).sum()), n_runs=int(per_run.size),
                sd_runs=float(per_run.std(ddof=1)) if per_run.size > 1 else None)


def main():
    rows = []
    for model in MODELS:
        for graph in GRAPHS:
            queries = load_queries(graph)
            cells = {c: load_cell(model, graph, c) for c in
                     ("flat_list", "flat_list_prioritized", "graph", "graph_neutral")}

            # --- commit rate, all 100 queries, instruction-only gap ---
            base_all = matrices(cells["flat_list"], graph, queries, False)
            fi_all = matrices(cells["flat_list_prioritized"], graph, queries, False)
            assert base_all[2] == fi_all[2], "query sets differ"
            st = boot_mean_diff(fi_all[0], base_all[0],
                                _rng(model, graph, "commit", "fi-f"))
            rows.append(dict(model=LABEL[model], graph="G" + graph[-1],
                             metric="commit_rate_all_queries",
                             contrast="flat_list_prioritized - flat_list (instruction-only)",
                             n_queries=len(base_all[2]), **_fmt(st)))

            # --- correctness per scorable query, each condition vs flat ---
            base = matrices(cells["flat_list"], graph, queries, True)
            scorable = len(base[2])
            per_cond = {}
            for cond, name in (("flat_list_prioritized", "instruction-only"),
                               ("graph_neutral", "structure-only"),
                               ("graph", "deployed")):
                if cells[cond] is None:
                    rows.append(dict(model=LABEL[model], graph="G" + graph[-1],
                                     metric="correct_per_scorable",
                                     contrast=f"{cond} - flat_list ({name})",
                                     n_queries=scorable, gap_pp=None, ci95_lo=None, runs_positive=None,
                                     ci95_hi=None, p_two_sided=None, n_runs=None, sd_across_runs=None,
                                     excludes_zero="not measured", resamples_dropped=None))
                    continue
                m = matrices(cells[cond], graph, queries, True)
                assert m[2] == base[2], "scorable query sets differ"
                per_cond[cond] = m
                st = boot_mean_diff(m[1], base[1],
                                    _rng(model, graph, "correct", cond))
                rows.append(dict(model=LABEL[model], graph="G" + graph[-1],
                                 metric="correct_per_scorable",
                                 contrast=f"{cond} - flat_list ({name})",
                                 n_queries=scorable, **_fmt(st)))

            # --- precision among committed answers ---
            prec_pairs = [
                ("graph_neutral", "flat_list_prioritized",
                 "graph_neutral - flat_list_prioritized (structure vs instruction)"),
                ("graph", "flat_list", "graph - flat_list (deployed)"),
            ]
            for a, b, name in prec_pairs:
                ma = per_cond.get(a) if a != "flat_list" else base
                mb = per_cond.get(b) if b != "flat_list" else base
                if ma is None or mb is None:
                    rows.append(dict(model=LABEL[model], graph="G" + graph[-1],
                                     metric="precision_among_commits", contrast=name,
                                     n_queries=scorable, gap_pp=None, ci95_lo=None, runs_positive=None,
                                     ci95_hi=None, p_two_sided=None, n_runs=None, sd_across_runs=None,
                                     excludes_zero="not measured", resamples_dropped=None))
                    continue
                st = boot_ratio_diff(ma, mb, _rng(model, graph, "precision", a, b))
                rows.append(dict(model=LABEL[model], graph="G" + graph[-1],
                                 metric="precision_among_commits", contrast=name,
                                 n_queries=scorable, **_fmt(st)))

    with open(OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    for metric in ("commit_rate_all_queries", "correct_per_scorable",
                   "precision_among_commits"):
        sub = [r for r in rows if r["metric"] == metric
               and r["excludes_zero"] != "not measured"]
        for contrast in sorted({r["contrast"] for r in sub}):
            s = [r for r in sub if r["contrast"] == contrast]
            pos = sum(r["gap_pp"] > 0 for r in s)
            sep = sum(r["excludes_zero"] == "yes" for r in s)
            print(f"{metric:26s} {contrast[:52]:52s} "
                  f"{pos}/{len(s)} positive, {sep}/{len(s)} exclude zero")
    print("wrote", os.path.relpath(OUT, HERE))


def _fmt(st):
    return dict(gap_pp=round(st["mean"], 2), ci95_lo=round(st["lo"], 2),
                ci95_hi=round(st["hi"], 2), p_two_sided=round(st["p"], 4),
                excludes_zero="yes" if (st["lo"] > 0 or st["hi"] < 0) else "no",
                runs_positive=st["runs_pos"], n_runs=st["n_runs"],
                sd_across_runs=None if st["sd_runs"] is None else round(st["sd_runs"], 2),
                resamples_dropped=st["dropped"])


if __name__ == "__main__":
    main()
