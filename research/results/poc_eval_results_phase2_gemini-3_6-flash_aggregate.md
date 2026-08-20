# Asterism PoC Phase 2 (instruction vs. structure): Aggregate — `gemini-3.6-flash`

_Generated 2026-08-12T14:26:25_

5 independent run(s), 12 PRIORITY queries x 5 conditions each, assistant model `gemini-3.6-flash` held fixed, temperature=1.0 pinned, reseed-per-call, universal truncation/empty-response guard active throughout (zero truncated or empty responses in this data - `converse()` raises rather than allowing one through). Scorer: `poc_compare_v2`'s pre-registered COMMIT/HEDGE classifier, imported unchanged, validated 11/11 on its held-out set once before this model's first run.

## Per-run counts

| Run | graph | flat_list_prioritized | flat_list | graph_neutral | none |
|---|---|---|---|---|---|
| 1 | 1/12 | 1/12 | 1/12 | 1/12 | 0/12 |
| 2 | 1/12 | 3/12 | 4/12 | 1/12 | 0/12 |
| 3 | 1/12 | 3/12 | 0/12 | 3/12 | 1/12 |
| 4 | 4/12 | 2/12 | 1/12 | 1/12 | 1/12 |
| 5 | 4/12 | 1/12 | 1/12 | 2/12 | 0/12 |

## Aggregate across runs (mean [min-max])

| Condition | mean | min | max |
|---|---|---|---|
| graph | 2.2/12 | 1/12 | 4/12 |
| flat_list_prioritized | 2.0/12 | 1/12 | 3/12 |
| flat_list | 1.4/12 | 0/12 | 4/12 |
| graph_neutral | 1.6/12 | 1/12 | 3/12 |
| none | 0.4/12 | 0/12 | 1/12 |

## Verdict comparisons (mean COMMIT count over 5 runs)

- graph vs flat_list_prioritized: 2.2 vs 2.0  (graph wins -> structural signal)
- flat_list_prioritized vs flat_list: 2.0 vs 1.4  (flat_list_prioritized wins -> instructional signal)
- graph_neutral vs flat_list (structure alone, no instruction): 1.6 vs 1.4  (graph_neutral wins -> structure helps even without the instruction)

**Verdict for `gemini-3.6-flash`: MIXED**