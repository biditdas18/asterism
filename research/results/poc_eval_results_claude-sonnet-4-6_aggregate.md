# Asterism PoC (cross-model, multi-run): Aggregate — `claude-sonnet-4-6`

_Generated 2026-08-10T14:05:00_

5 independent run(s) of the full 36-call eval (12 PRIORITY queries x 3 conditions), each against a freshly reseeded isolated DB, assistant model `claude-sonnet-4-6` held fixed. Scorer: `poc_compare_v2`'s pre-registered COMMIT/HEDGE classifier, imported unchanged, validated 11/11 on its held-out set once before this model's first run. There is no per-run target number — this reports the across-run distribution as measured, not a comparison against an expected value.

## Per-run counts

| Run | graph | flat_list | none | gap (graph-flat_list) |
|---|---|---|---|---|
| 1 | 6/12 | 1/12 | 0/12 | +5 |
| 2 | 8/12 | 3/12 | 0/12 | +5 |
| 3 | 6/12 | 3/12 | 0/12 | +3 |
| 4 | 6/12 | 4/12 | 0/12 | +2 |
| 5 | 7/12 | 4/12 | 0/12 | +3 |

## Aggregate across runs

| Condition | mean | min | max |
|---|---|---|---|
| graph | 6.6/12 | 6/12 | 8/12 |
| flat_list | 3.0/12 | 1/12 | 4/12 |
| none | 0.0/12 | 0/12 | 0/12 |

**graph-flat_list gap across runs:** mean +3.6, range [+2, +5]

graph beat flat_list in every run for `claude-sonnet-4-6` (gap > 0 in all 5 runs).