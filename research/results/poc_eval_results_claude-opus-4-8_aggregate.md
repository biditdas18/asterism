# Asterism PoC (cross-model, multi-run): Aggregate — `claude-opus-4-8`

_Generated 2026-08-10T15:07:13_

5 independent run(s) of the full 36-call eval (12 PRIORITY queries x 3 conditions), each against a freshly reseeded isolated DB, assistant model `claude-opus-4-8` held fixed. Scorer: `poc_compare_v2`'s pre-registered COMMIT/HEDGE classifier, imported unchanged, validated 11/11 on its held-out set once before this model's first run. There is no per-run target number — this reports the across-run distribution as measured, not a comparison against an expected value.

## Per-run counts

| Run | graph | flat_list | none | gap (graph-flat_list) |
|---|---|---|---|---|
| 1 | 6/12 | 3/12 | 1/12 | +3 |
| 2 | 10/12 | 2/12 | 1/12 | +8 |
| 3 | 4/12 | 0/12 | 1/12 | +4 |
| 4 | 8/12 | 2/12 | 0/12 | +6 |
| 5 | 7/12 | 4/12 | 0/12 | +3 |

## Aggregate across runs

| Condition | mean | min | max |
|---|---|---|---|
| graph | 7.0/12 | 4/12 | 10/12 |
| flat_list | 2.2/12 | 0/12 | 4/12 |
| none | 0.6/12 | 0/12 | 1/12 |

**graph-flat_list gap across runs:** mean +4.8, range [+3, +8]

graph beat flat_list in every run for `claude-opus-4-8` (gap > 0 in all 5 runs).