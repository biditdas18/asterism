#!/usr/bin/env python3
"""Generate every LaTeX table body in the paper from the committed result files.

Writes results/paper_tables.tex. Nothing here re-scores or relabels: commit and
hedge labels are read from the frozen per-cell files, correctness verdicts are
recomputed with the committed per-graph extractors, and interval estimates are
read from n100_bootstrap_ci.csv (existing contrasts) and n100_followup_ci.csv
(new contrasts). Regenerating this file after either CSV changes keeps the
manuscript numerically consistent with the data by construction.

Usage:  python research/make_paper_tables.py
"""

import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from followup_ci import (GRAPHS, LABEL, MODELS, RESULTS, _tag, load_cell,
                         load_queries, matrices)

OUT = os.path.join(RESULTS, "paper_tables.tex")
CONDS = ["none", "flat_list", "flat_list_prioritized", "graph_neutral", "graph"]
CELLS = [(m, g) for m in MODELS for g in GRAPHS]


def num(x, dec=1, sign=True):
    """LaTeX-safe signed number with a real minus sign."""
    if x is None:
        return "---"
    s = f"{abs(x):.{dec}f}"
    if x < 0:
        return "$-$" + s
    return ("+" + s) if sign else s


def bold_if(txt, flag):
    return r"\textbf{" + txt + "}" if flag else txt


def load_ci(path, keycols):
    out = {}
    with open(path) as fh:
        for r in csv.DictReader(fh):
            out[tuple(r[c] for c in keycols)] = r
    return out


def main():
    commit, correct, precision, ncommit = {}, {}, {}, {}
    for model in MODELS:
        for graph in GRAPHS:
            queries = load_queries(graph)
            for cond in CONDS:
                runs = load_cell(model, graph, cond)
                if runs is None:
                    continue
                key = (LABEL[model], "G" + graph[-1], cond)
                allq = matrices(runs, graph, queries, False)
                commit[key] = allq[0].mean() * 100.0
                sc = matrices(runs, graph, queries, True)
                correct[key] = sc[1].mean() * 100.0
                n_c = sc[0].sum()
                ncommit[key] = int(n_c)
                precision[key] = (sc[1].sum() / n_c * 100.0) if n_c else None

    old = load_ci(os.path.join(RESULTS, "n100_bootstrap_ci.csv"),
                  ["model", "graph", "contrast"])
    new = load_ci(os.path.join(RESULTS, "n100_followup_ci.csv"),
                  ["model", "graph", "metric", "contrast"])

    def old_sig(mo, gr, contrast):
        r = old.get((mo, gr, contrast))
        return (r is not None and r.get("excludes_zero") == "yes")

    def new_row(mo, gr, metric, contrast):
        for k, r in new.items():
            if k[0] == mo and k[1] == gr and k[2] == metric and contrast in k[3]:
                return r
        return None

    def new_sig(mo, gr, metric, contrast):
        r = new_row(mo, gr, metric, contrast)
        return (r is not None and r.get("excludes_zero") == "yes")

    L = []
    A = L.append

    # ---------- Table 1: commit rates + both metrics' gaps ----------
    A("% ===== TABLE 1 BODY: commit rates and gaps (auto-generated) =====")
    for mo, gr in [(LABEL[m], "G" + g[-1]) for m in MODELS for g in GRAPHS]:
        c = {cd: commit.get((mo, gr, cd)) for cd in CONDS}
        k = {cd: correct.get((mo, gr, cd)) for cd in CONDS}
        cells = [mo, gr] + [("---" if c[cd] is None else f"{c[cd]:.1f}") for cd in CONDS]
        gaps = []
        for cd, oldc, newc in (
                ("flat_list_prioritized", None, "instruction-only"),
                ("graph_neutral", "graph_neutral - flat_list", None),
                ("graph", "graph - flat_list", None)):
            if c[cd] is None:
                gaps.append("---")
                continue
            g_ = c[cd] - c["flat_list"]
            sig = (old_sig(mo, gr, oldc) if oldc else
                   new_sig(mo, gr, "commit_rate_all_queries", newc))
            gaps.append(bold_if(num(g_), sig))
        kgaps = []
        for cd, name in (("flat_list_prioritized", "instruction-only"),
                         ("graph_neutral", "structure-only"),
                         ("graph", "deployed")):
            if k[cd] is None:
                kgaps.append("---")
                continue
            kgaps.append(bold_if(num(k[cd] - k["flat_list"]),
                                 new_sig(mo, gr, "correct_per_scorable", name)))
        A(" & ".join(cells + gaps + kgaps) + r" \\")

    # ---------- Appendix: absolute correctness and precision ----------
    A("")
    A("% ===== APPENDIX TABLE: correctness and precision absolutes =====")
    for mo, gr in [(LABEL[m], "G" + g[-1]) for m in MODELS for g in GRAPHS]:
        row = [mo, gr]
        for cd in CONDS:
            v = correct.get((mo, gr, cd))
            row.append("---" if v is None else f"{v:.1f}")
        for cd in CONDS:
            v = precision.get((mo, gr, cd))
            n = ncommit.get((mo, gr, cd))
            row.append("---" if v is None else
                       f"{v:.1f}\\,\\tiny{{({n})}}")
        A(" & ".join(row) + r" \\")

    # ---------- Appendix: follow-up intervals ----------
    A("")
    A("% ===== APPENDIX TABLE: follow-up bootstrap intervals =====")
    blocks = [("commit_rate_all_queries", "instruction-only",
               r"Commit rate: flat\_list\_prioritized $-$ flat\_list (instruction-only)"),
              ("correct_per_scorable", "instruction-only",
               r"Correct per scorable query: flat\_list\_prioritized $-$ flat\_list"),
              ("correct_per_scorable", "structure-only",
               r"Correct per scorable query: graph\_neutral $-$ flat\_list"),
              ("correct_per_scorable", "deployed",
               r"Correct per scorable query: graph $-$ flat\_list"),
              ("precision_among_commits", "structure vs instruction",
               r"Precision among commits: graph\_neutral $-$ flat\_list\_prioritized")]
    for metric, contrast, title in blocks:
        A(r"\multicolumn{7}{@{}l}{\textit{" + title + r"}} \\")
        for mo, gr in [(LABEL[m], "G" + g[-1]) for m in MODELS for g in GRAPHS]:
            r = new_row(mo, gr, metric, contrast)
            if r is None or r["excludes_zero"] == "not measured" or r["gap_pp"] == "":
                A(f"{mo} & {gr} & --- & --- & --- & --- & --- " + r"\\")
                continue
            gap = num(float(r["gap_pp"]))
            ci = f"[{num(float(r['ci95_lo']), sign=False) if float(r['ci95_lo'])>=0 else num(float(r['ci95_lo']))}, " \
                 f"{num(float(r['ci95_hi']), sign=False) if float(r['ci95_hi'])>=0 else num(float(r['ci95_hi']))}]"
            p = float(r["p_two_sided"])
            ps = r"$<$0.001" if p < 0.001 else f"{p:.3f}"
            rp = r["runs_positive"]
            nr = r["n_runs"]
            runs = "---" if rp in ("", None) else f"{int(float(rp))}/{int(float(nr))}"
            sd = r["sd_across_runs"]
            sds = "---" if sd in ("", None) else f"{float(sd):.1f}"
            A(f"{mo} & {gr} & {bold_if(gap, r['excludes_zero']=='yes')} & {ci} & {ps} & {runs} & {sds} " + r"\\")
        if (metric, contrast) != blocks[-1][:2]:
            A(r"\addlinespace")

    with open(OUT, "w") as fh:
        fh.write("\n".join(L) + "\n")
    print("wrote", os.path.relpath(OUT, HERE), f"({len(L)} lines)")

    # ---------- complete appendix section, spliced into the manuscript ----------
    def ci_block(metric, contrast):
        rows = []
        for mo, gr in [(LABEL[m], "G" + g[-1]) for m in MODELS for g in GRAPHS]:
            r = new_row(mo, gr, metric, contrast)
            if r is None or not r["gap_pp"]:
                rows.append(f"{mo} & {gr} & --- & --- & --- & --- & --- " + r"\\")
                continue
            lo, hi = float(r["ci95_lo"]), float(r["ci95_hi"])
            ci = f"[{num(lo, sign=False) if lo >= 0 else num(lo)}, " \
                 f"{num(hi, sign=False) if hi >= 0 else num(hi)}]"
            p = float(r["p_two_sided"])
            ps = r"$<$0.001" if p < 0.001 else f"{p:.3f}"
            rp, nr, sd = r["runs_positive"], r["n_runs"], r["sd_across_runs"]
            runs = "---" if not rp else f"{int(float(rp))}/{int(float(nr))}"
            sds = "---" if not sd else f"{float(sd):.1f}"
            rows.append(f"{mo} & {gr} & {bold_if(num(float(r['gap_pp'])), r['excludes_zero']=='yes')} "
                        f"& {ci} & {ps} & {runs} & {sds} " + r"\\")
        return rows

    HDR = (r"\textbf{Model} & \textbf{Gr} & Gap & 95\% CI & $p$ & Runs$>$0 & SD \\")
    S = []
    B_ = S.append
    B_(r"\section{Absolute Correctness, Precision, and Follow-up Intervals}")
    B_(r"\label{app:followup}")
    B_("")
    B_(r"""Table~\ref{tab:commit} reports gaps; this section reports the absolute
levels those gaps are computed from, and the interval estimates behind every
bolded and unbolded entry. Correctness is the fraction of \emph{scorable}
queries (ground-truth weight margin exceeding one decay step: 96 of 100 on
graph 1, 69 of 100 on graph 2) on which the condition committed to the
actually-highest-priority node. Precision is the fraction of \emph{committed}
answers that were correct, with the number of committed answers in
parentheses; it is the metric that separates the structural from the
instructional component, and its denominators vary widely across conditions,
so we print them. The \textsc{None} column's precision rests on single-digit
denominators in most cells and should not be read as an estimate.
Interval estimates use the same procedure as Appendix~\ref{app:ci} --- paired
by query over $10{,}000$ resamples of the frozen labels, no additional model
calls, no relabelling --- computed by \texttt{research/followup\_ci.py}. That
script draws its randomness from a generator seeded per row from the cell's
own identifiers, so adding a contrast cannot perturb an interval already
published in Table~\ref{tab:ci}. Table~\ref{tab:fci1} covers the
instruction-only contrast on both metrics together with the structure-only
correctness gap; Table~\ref{tab:fci2} covers the deployed correctness gap and
the precision difference between the two single components. Every table body
in this paper is emitted from the committed result files by
\texttt{research/make\_paper\_tables.py} rather than transcribed.""")
    B_("")
    B_(r"\begin{table*}[t]")
    B_(r"\centering")
    B_(r"\footnotesize")
    B_(r"\setlength{\tabcolsep}{3.2pt}")
    B_(r"\begin{tabular}{@{}ll|ccccc|ccccc@{}}")
    B_(r"\toprule")
    B_(r" & & \multicolumn{5}{c|}{\textbf{Correct per scorable query (\%)}} & "
       r"\multicolumn{5}{c}{\textbf{Precision among commits (\%), (n committed)}} \\")
    B_(r"\textbf{Model} & \textbf{Gr} & None & Flat & Fl+in & Gr,neut & Graph "
       r"& None & Flat & Fl+in & Gr,neut & Graph \\")
    B_(r"\midrule")
    for mo, gr in [(LABEL[m], "G" + g[-1]) for m in MODELS for g in GRAPHS]:
        row = [mo, gr]
        for cd in CONDS:
            v = correct.get((mo, gr, cd))
            row.append("---" if v is None else f"{v:.1f}")
        for cd in CONDS:
            v, n = precision.get((mo, gr, cd)), ncommit.get((mo, gr, cd))
            row.append("---" if v is None else f"{v:.1f}\\,\\tiny{{({n})}}")
        B_(" & ".join(row) + r" \\")
    B_(r"\bottomrule")
    B_(r"\end{tabular}")
    B_(r"""\caption{Absolute correctness and precision by model, graph, and
condition, the levels underlying the correctness gaps in
Table~\ref{tab:commit}. Correctness is over scorable queries (96 on graph 1,
69 on graph 2); precision is over committed answers only, with committed
counts in parentheses, pooled over the five runs. Absolute correctness is low
throughout --- the best cell is GPT graph 2 at 42.0\% --- which is the ceiling
we report rather than the relative gap alone. Precision is where the
structure-only condition separates from the instruction-only condition: it is
higher in all nine measured cells. \textsc{None}-column precision rests on
denominators as small as one and is reported only for completeness.}""")
    B_(r"\label{tab:correct}")
    B_(r"\end{table*}")
    B_("")

    groups = [("tab:fci1", r"Commit-rate and correctness gaps for the instruction-only "
                           r"contrast, and the correctness gap for the structure-only contrast",
               [("commit_rate_all_queries", "instruction-only",
                 r"Commit rate: \textsc{Fl+in} $-$ \textsc{Flat} (instruction only)"),
                ("correct_per_scorable", "instruction-only",
                 r"Correct per scorable query: \textsc{Fl+in} $-$ \textsc{Flat} (instruction only)"),
                ("correct_per_scorable", "structure-only",
                 r"Correct per scorable query: \textsc{Gr,neut} $-$ \textsc{Flat} (structure only)")]),
              ("tab:fci2", r"Correctness gap for the deployed system, and the precision "
                           r"contrast between the two single components",
               [("correct_per_scorable", "deployed",
                 r"Correct per scorable query: \textsc{Graph} $-$ \textsc{Flat} (deployed)"),
                ("precision_among_commits", "structure vs instruction",
                 r"Precision among commits: \textsc{Gr,neut} $-$ \textsc{Fl+in}")])]
    caps = {
        "tab:fci1": r"""Paired bootstrap intervals, in percentage points, for the
instruction-only contrast on both metrics and the structure-only contrast on
correctness. \textsc{Runs}$>$0 counts how many of the five runs show a positive
gap; SD is the standard deviation across runs. \textbf{Bold} marks an interval
excluding zero. The instruction alone raises the commit rate in all ten cells
(eight separably), matching the structure-only commit gap of
Table~\ref{tab:ci} in magnitude --- which is why decisiveness cannot attribute
the effect to structure. On correctness the instruction alone is separable in
only five of ten cells, against seven of nine for the structure.""",
        "tab:fci2": r"""Paired bootstrap intervals, in percentage points, for the
deployed correctness gap and for the precision difference between the two
single components. The deployed correctness gap excludes zero in nine of ten
cells, more than either component alone. The precision contrast is positive in
all nine measured cells but separable in four, with run consistency between
2/5 and 5/5: the direction is unanimous while individual cells are
underpowered, so we report the sign pattern and not per-cell effect sizes. No
pooled statistic is given because cells share query sets across models and are
therefore not independent.""",
    }
    for lab, _desc, blocks_ in groups:
        B_(r"\begin{table}[t]")
        B_(r"\centering")
        B_(r"\footnotesize")
        B_(r"\setlength{\tabcolsep}{3.0pt}")
        B_(r"\begin{tabular}{@{}llccccc@{}}")
        B_(r"\toprule")
        B_(HDR)
        for i, (metric, contrast, title) in enumerate(blocks_):
            B_(r"\midrule" if i == 0 else r"\addlinespace")
            B_(r"\multicolumn{7}{@{}l}{\textit{" + title + r"}} \\")
            S.extend(ci_block(metric, contrast))
        B_(r"\bottomrule")
        B_(r"\end{tabular}")
        B_(r"\caption{" + caps[lab] + r"}")
        B_(r"\label{" + lab + r"}")
        B_(r"\end{table}")
        B_("")

    app = os.path.join(RESULTS, "appendix_followup.tex")
    with open(app, "w") as fh:
        fh.write("\n".join(S) + "\n")
    print("wrote", os.path.relpath(app, HERE), f"({len(S)} lines)")

    # console cross-check of the claims made in the prose
    ic = [commit[(LABEL[m], "G" + g[-1], "flat_list_prioritized")]
          - commit[(LABEL[m], "G" + g[-1], "flat_list")] for m in MODELS for g in GRAPHS]
    sc = [commit[(LABEL[m], "G" + g[-1], "graph_neutral")]
          - commit[(LABEL[m], "G" + g[-1], "flat_list")]
          for m in MODELS for g in GRAPHS
          if (LABEL[m], "G" + g[-1], "graph_neutral") in commit]
    print(f"instruction-only commit gap: {sum(v>0 for v in ic)}/{len(ic)} positive, "
          f"mean {sum(ic)/len(ic):+.1f}pp, range {min(ic):+.1f} to {max(ic):+.1f}")
    print(f"structure-only  commit gap: {sum(v>0 for v in sc)}/{len(sc)} positive, "
          f"mean {sum(sc)/len(sc):+.1f}pp")
    pg = [(LABEL[m], "G" + g[-1]) for m in MODELS for g in GRAPHS
          if precision.get((LABEL[m], "G" + g[-1], "graph_neutral")) is not None]
    dp = [precision[(mo, gr, "graph_neutral")] - precision[(mo, gr, "flat_list_prioritized")]
          for mo, gr in pg]
    print(f"precision structure-only $-$ instruction-only: {sum(v>0 for v in dp)}/{len(dp)} "
          f"positive, range {min(dp):+.1f} to {max(dp):+.1f}pp")
    dep = [correct[(LABEL[m], "G" + g[-1], "graph")] - correct[(LABEL[m], "G" + g[-1], "flat_list")]
           for m in MODELS for g in GRAPHS]
    best_single = []
    for m in MODELS:
        for g in GRAPHS:
            mo, gr = LABEL[m], "G" + g[-1]
            comp = [correct[(mo, gr, "flat_list_prioritized")] - correct[(mo, gr, "flat_list")]]
            if (mo, gr, "graph_neutral") in correct:
                comp.append(correct[(mo, gr, "graph_neutral")] - correct[(mo, gr, "flat_list")])
            best_single.append(max(comp))
    ge = sum(d >= b - 1e-9 for d, b in zip(dep, best_single))
    gt = sum(d > b + 1e-9 for d, b in zip(dep, best_single))
    print(f"deployed correctness gain >= best single component in {ge}/10 cells, "
          f"strictly greater in {gt}/10")


if __name__ == "__main__":
    main()
