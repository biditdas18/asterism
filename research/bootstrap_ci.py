"""Paired bootstrap confidence intervals on the N=100 commit-rate gaps.

Re-analysis only: reads the committed per-cell result files and counts the
labels the FROZEN scorer already assigned. No model calls, no re-scoring, no
relabelling. Regenerates results/n100_bootstrap_ci.csv byte-identically.

Pairing is over QUERIES, not runs: under pinned decoding the five runs are
exchangeable draws for a given (model, graph, condition), while the query is
the unit the two conditions share. Each query is reduced to its commit rate
across the five runs; the per-query difference against flat_list is then
resampled with replacement 10,000 times under a fixed seed. Reported
intervals are 95% percentile intervals; p is the two-sided bootstrap
proportion of resamples on the far side of zero.

Usage:  python research/bootstrap_ci.py
"""

import csv
import glob
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
OUT = os.path.join(RESULTS, "n100_bootstrap_ci.csv")

CONDS = ["none", "flat_list", "flat_list_prioritized", "graph", "graph_neutral"]
MODELS = [
    "claude-sonnet-4-6",
    "claude-opus-4-8",
    "gpt-5_5-2026-04-23",
    "deepseek-v4-pro",
    "kimi-k3",
]
LABEL = {
    "claude-sonnet-4-6": "Sonnet",
    "claude-opus-4-8": "Opus",
    "gpt-5_5-2026-04-23": "GPT",
    "deepseek-v4-pro": "DeepSeek",
    "kimi-k3": "Kimi",
}
GRAPHS = ["graph1", "graph2"]
CONTRASTS = [
    ("graph", "graph - flat_list (deployed)"),
    ("graph_neutral", "graph_neutral - flat_list (structure-only)"),
]

SEED = 20260902
B = 10000


def load_cells():
    """(model, graph, cond) -> list of runs, each a list of query records."""
    cells = {}
    for path in sorted(glob.glob(os.path.join(RESULTS, "n100_*.json"))):
        stem = os.path.basename(path)[len("n100_"): -len(".json")]
        # longest-suffix match so flat_list_prioritized is not read as flat_list
        for cond in sorted(CONDS, key=len, reverse=True):
            if stem.endswith("_" + cond):
                head = stem[: -(len(cond) + 1)]
                break
        else:
            continue  # ledgers / status / skipped-cell bookkeeping files
        model, graph = head.rsplit("_", 1)
        cells[(model, graph, cond)] = json.load(open(path))["runs"]
    return cells


def commit_matrix(runs):
    """rows = runs, cols = queries, 1.0 = COMMIT. Asserts query order is shared."""
    ids = [q["query_id"] for q in runs[0]]
    for r in runs:
        assert [q["query_id"] for q in r] == ids, "query order differs across runs"
    return np.array(
        [[1.0 if q["label"] == "COMMIT" else 0.0 for q in r] for r in runs]
    ), ids


def paired_bootstrap(cond_mat, base_mat, rng):
    a = cond_mat.mean(axis=0) * 100.0        # per-query commit rate, condition
    b = base_mat.mean(axis=0) * 100.0        # per-query commit rate, flat_list
    d = a - b
    n = d.size
    draws = d[rng.integers(0, n, size=(B, n))].mean(axis=1)
    lo, hi = np.percentile(draws, [2.5, 97.5])
    # a bootstrap p is not resolvable below 1/B; floor rather than report 0
    tail = max(min((draws <= 0).mean(), (draws >= 0).mean()), 0.5 / B)
    per_run = (cond_mat.mean(axis=1) - base_mat.mean(axis=1)) * 100.0
    return dict(
        mean=float(d.mean()),
        lo=float(lo),
        hi=float(hi),
        p=float(min(1.0, 2 * tail)),
        wins=int((per_run > 0).sum()),
        n_runs=int(per_run.size),
        run_sd=float(per_run.std(ddof=1)),
    )


def main():
    cells = load_cells()
    rng = np.random.default_rng(SEED)
    rows = []
    for model in MODELS:
        for graph in GRAPHS:
            base = cells.get((model, graph, "flat_list"))
            if base is None:
                continue
            base_mat, base_ids = commit_matrix(base)
            for cond, name in CONTRASTS:
                runs = cells.get((model, graph, cond))
                row = dict(
                    model=LABEL[model], graph="G" + graph[-1], contrast=name,
                    mean_gap_pp=None, ci95_lo=None, ci95_hi=None,
                    p_two_sided=None, runs_positive=None, n_runs=None,
                    run_sd_pp=None, excludes_zero="not measured",
                )
                if runs is not None:
                    mat, ids = commit_matrix(runs)
                    assert ids == base_ids, "query sets differ between conditions"
                    st = paired_bootstrap(mat, base_mat, rng)
                    row.update(
                        mean_gap_pp=round(st["mean"], 2),
                        ci95_lo=round(st["lo"], 2),
                        ci95_hi=round(st["hi"], 2),
                        p_two_sided=round(st["p"], 4),
                        runs_positive=st["wins"],
                        n_runs=st["n_runs"],
                        run_sd_pp=round(st["run_sd"], 2),
                        excludes_zero="yes" if (st["lo"] > 0 or st["hi"] < 0) else "no",
                    )
                rows.append(row)

    with open(OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    meas = [r for r in rows if r["excludes_zero"] != "not measured"]
    for _, name in CONTRASTS:
        sub = [r for r in meas if r["contrast"] == name]
        sep = sum(r["excludes_zero"] == "yes" for r in sub)
        pos = sum(r["mean_gap_pp"] > 0 for r in sub)
        print(f"{name}: {pos}/{len(sub)} positive, {sep}/{len(sub)} exclude zero")
    print("wrote", os.path.relpath(OUT, HERE))


if __name__ == "__main__":
    main()
