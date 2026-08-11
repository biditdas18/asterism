# Asterism PoC Phase 2 (instruction vs. structure): Aggregate — `claude-sonnet-4-6`

_Generated 2026-08-10T18:31:01_

5 independent run(s), 12 PRIORITY queries x 5 conditions each, assistant model `claude-sonnet-4-6` held fixed, temperature=1.0 pinned, reseed-per-call, universal truncation/empty-response guard active throughout (zero truncated or empty responses in this data - `converse()` raises rather than allowing one through). Scorer: `poc_compare_v2`'s pre-registered COMMIT/HEDGE classifier, imported unchanged, validated 11/11 on its held-out set once before this model's first run.

## Per-run counts

| Run | graph | flat_list_prioritized | flat_list | graph_neutral | none |
|---|---|---|---|---|---|
| 1 | 7/12 | 3/12 | 5/12 | 9/12 | 0/12 |
| 2 | 3/12 | 4/12 | 3/12 | 11/12 | 0/12 |
| 3 | 8/12 | 4/12 | 4/12 | 7/12 | 0/12 |
| 4 | 6/12 | 3/12 | 3/12 | 10/12 | 0/12 |
| 5 | 3/12 | 4/12 | 3/12 | 7/12 | 0/12 |

## Aggregate across runs (mean [min-max])

| Condition | mean | min | max |
|---|---|---|---|
| graph | 5.4/12 | 3/12 | 8/12 |
| flat_list_prioritized | 3.6/12 | 3/12 | 4/12 |
| flat_list | 3.6/12 | 3/12 | 5/12 |
| graph_neutral | 8.8/12 | 7/12 | 11/12 |
| none | 0.0/12 | 0/12 | 0/12 |

## Verdict comparisons (mean COMMIT count over 5 runs)

- graph vs flat_list_prioritized: 5.4 vs 3.6  (graph wins -> structural signal)
- flat_list_prioritized vs flat_list: 3.6 vs 3.6  (tie)
- graph_neutral vs flat_list (structure alone, no instruction): 8.8 vs 3.6  (graph_neutral wins -> structure helps even without the instruction)

**Verdict for `claude-sonnet-4-6`: STRUCTURAL**