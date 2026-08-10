# Asterism PoC (cross-model, multi-run): Aggregate — `gpt-5.5-2026-04-23`

_Generated 2026-08-10T15:47:47_

5 independent run(s) of the full 36-call eval (12 PRIORITY queries x 3 conditions), each against a freshly reseeded isolated DB, assistant model `gpt-5.5-2026-04-23` held fixed. Scorer: `poc_compare_v2`'s pre-registered COMMIT/HEDGE classifier, imported unchanged, validated 11/11 on its held-out set once before this model's first run. There is no per-run target number — this reports the across-run distribution as measured, not a comparison against an expected value.

## Per-run counts

| Run | graph | flat_list | none | gap (graph-flat_list) |
|---|---|---|---|---|
| 1 | 4/12 | 6/12 | 2/12 | -2 |
| 2 | 4/12 | 6/12 | 1/12 | -2 |
| 3 | 6/12 | 6/12 | 2/12 | +0 |
| 4 | 6/12 | 5/12 | 2/12 | +1 |
| 5 | 8/12 | 5/12 | 0/12 | +3 |

## Aggregate across runs

| Condition | mean | min | max |
|---|---|---|---|
| graph | 5.6/12 | 4/12 | 8/12 |
| flat_list | 5.6/12 | 5/12 | 6/12 |
| none | 1.4/12 | 0/12 | 2/12 |

**graph-flat_list gap across runs:** mean +0.0, range [-2, +3]

**Flag:** the graph-flat_list gap is zero or negative in at least one run for `gpt-5.5-2026-04-23` — graph did not beat flat_list in every run.