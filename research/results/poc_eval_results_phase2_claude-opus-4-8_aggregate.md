# Asterism PoC Phase 2 (instruction vs. structure): Aggregate — `claude-opus-4-8`

_Generated 2026-08-10T23:53:39_

5 independent run(s), 12 PRIORITY queries x 5 conditions each, assistant model `claude-opus-4-8` held fixed, temperature=1.0 pinned, reseed-per-call, universal truncation/empty-response guard active throughout (zero truncated or empty responses in this data - `converse()` raises rather than allowing one through). Scorer: `poc_compare_v2`'s pre-registered COMMIT/HEDGE classifier, imported unchanged, validated 11/11 on its held-out set once before this model's first run.

## Per-run counts

| Run | graph | flat_list_prioritized | flat_list | graph_neutral | none |
|---|---|---|---|---|---|
| 1 | 6/12 | 2/12 | 3/12 | 4/12 | 1/12 |
| 2 | 5/12 | 3/12 | 2/12 | 8/12 | 2/12 |
| 3 | 7/12 | 4/12 | 0/12 | 7/12 | 0/12 |
| 4 | 9/12 | 5/12 | 1/12 | 5/12 | 0/12 |
| 5 | 4/12 | 4/12 | 2/12 | 5/12 | 2/12 |

## Aggregate across runs (mean [min-max])

| Condition | mean | min | max |
|---|---|---|---|
| graph | 6.2/12 | 4/12 | 9/12 |
| flat_list_prioritized | 3.6/12 | 2/12 | 5/12 |
| flat_list | 1.6/12 | 0/12 | 3/12 |
| graph_neutral | 5.8/12 | 4/12 | 8/12 |
| none | 1.0/12 | 0/12 | 2/12 |

## Verdict comparisons (mean COMMIT count over 5 runs)

- graph vs flat_list_prioritized: 6.2 vs 3.6  (graph wins -> structural signal)
- flat_list_prioritized vs flat_list: 3.6 vs 1.6  (flat_list_prioritized wins -> instructional signal)
- graph_neutral vs flat_list (structure alone, no instruction): 5.8 vs 1.6  (graph_neutral wins -> structure helps even without the instruction)

**Verdict for `claude-opus-4-8`: MIXED**