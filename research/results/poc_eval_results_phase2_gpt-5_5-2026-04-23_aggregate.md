# Asterism PoC Phase 2 (instruction vs. structure): Aggregate — `gpt-5.5-2026-04-23`

_Generated 2026-08-11T00:49:29_

5 independent run(s), 12 PRIORITY queries x 5 conditions each, assistant model `gpt-5.5-2026-04-23` held fixed, temperature=1.0 pinned, reseed-per-call, universal truncation/empty-response guard active throughout (zero truncated or empty responses in this data - `converse()` raises rather than allowing one through). Scorer: `poc_compare_v2`'s pre-registered COMMIT/HEDGE classifier, imported unchanged, validated 11/11 on its held-out set once before this model's first run.

## Per-run counts

| Run | graph | flat_list_prioritized | flat_list | graph_neutral | none |
|---|---|---|---|---|---|
| 1 | 7/12 | 10/12 | 6/12 | 5/12 | 1/12 |
| 2 | 9/12 | 6/12 | 7/12 | 8/12 | 4/12 |
| 3 | 3/12 | 7/12 | 7/12 | 9/12 | 1/12 |
| 4 | 7/12 | 3/12 | 8/12 | 6/12 | 2/12 |
| 5 | 7/12 | 7/12 | 7/12 | 5/12 | 3/12 |

## Aggregate across runs (mean [min-max])

| Condition | mean | min | max |
|---|---|---|---|
| graph | 6.6/12 | 3/12 | 9/12 |
| flat_list_prioritized | 6.6/12 | 3/12 | 10/12 |
| flat_list | 7.0/12 | 6/12 | 8/12 |
| graph_neutral | 6.6/12 | 5/12 | 9/12 |
| none | 2.2/12 | 1/12 | 4/12 |

## Verdict comparisons (mean COMMIT count over 5 runs)

- graph vs flat_list_prioritized: 6.6 vs 6.6  (tie)
- flat_list_prioritized vs flat_list: 6.6 vs 7.0  (flat_list wins -> no instructional signal)
- graph_neutral vs flat_list (structure alone, no instruction): 6.6 vs 7.0  (flat_list wins -> structure alone does not help)

**Verdict for `gpt-5.5-2026-04-23`: MIXED**