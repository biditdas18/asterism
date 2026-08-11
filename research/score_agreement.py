#!/usr/bin/env python3
"""
Cohen's kappa between the frozen v2 scorer's labels and a human rater's
labels, on a 36-row sheet (query, condition, response_text, scorer_label,
human_label).

This script does NOT fill in human_label - it only reads an already-filled
sheet and reports agreement. Does not touch or re-run the scorer.

Two sheets currently exist in research/results/:
  sonnet_phase2_run1_human_eval.csv  - CURRENT: sonnet Phase 2 run 1
                                        (temperature=1.0, reseed-per-call,
                                        truncation guard), graph/flat_list/
                                        none. This is the default.
  sonnet_run1_human_eval.csv         - older, pre-Phase-2 sonnet run;
                                        still present and untouched, not
                                        deleted, usable via an explicit path.

Usage: python research/score_agreement.py [path/to/filled.csv]
  Defaults to research/results/sonnet_phase2_run1_human_eval.csv
"""
import csv
import os
import sys

DEFAULT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "results", "sonnet_phase2_run1_human_eval.csv"
)


def cohens_kappa(labels_a: list[str], labels_b: list[str]) -> float:
    assert len(labels_a) == len(labels_b) and len(labels_a) > 0
    n = len(labels_a)
    categories = sorted(set(labels_a) | set(labels_b))

    po = sum(1 for a, b in zip(labels_a, labels_b) if a == b) / n

    pa = {c: labels_a.count(c) / n for c in categories}
    pb = {c: labels_b.count(c) / n for c in categories}
    pe = sum(pa[c] * pb[c] for c in categories)

    if pe == 1.0:
        return 1.0 if po == 1.0 else 0.0
    return (po - pe) / (1 - pe)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))

    missing = [i for i, r in enumerate(rows) if not r.get("human_label", "").strip()]
    if missing:
        print(f"{len(missing)}/{len(rows)} rows have an empty human_label - fill in "
              f"every row (COMMIT or HEDGE) before running this.")
        sys.exit(1)

    scorer = [r["scorer_label"].strip().upper() for r in rows]
    human = [r["human_label"].strip().upper() for r in rows]

    bad = [h for h in human if h not in ("COMMIT", "HEDGE")]
    if bad:
        print(f"human_label must be exactly COMMIT or HEDGE; found unexpected value(s): {set(bad)}")
        sys.exit(1)

    n = len(rows)
    agree = sum(1 for s, h in zip(scorer, human) if s == h)
    kappa = cohens_kappa(scorer, human)

    print(f"n = {n}")
    print(f"raw agreement = {agree}/{n} = {agree/n:.1%}")
    print(f"Cohen's kappa = {kappa:.3f}")

    # confusion breakdown
    print("\nConfusion (scorer -> human):")
    for s_label in ("COMMIT", "HEDGE"):
        for h_label in ("COMMIT", "HEDGE"):
            c = sum(1 for s, h in zip(scorer, human) if s == s_label and h == h_label)
            print(f"  scorer={s_label:7s} human={h_label:7s}: {c}")


if __name__ == "__main__":
    main()
