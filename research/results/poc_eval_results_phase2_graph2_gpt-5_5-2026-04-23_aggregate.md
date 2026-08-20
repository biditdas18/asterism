# Asterism PoC Phase 2 / Graph 2 (Priya): Aggregate — `gpt-5.5-2026-04-23`

_Generated 2026-08-12T05:33:55_

5 independent run(s) against seed_graph_2 (Priya persona), 12 PRIORITY queries x 5 conditions each, assistant model `gpt-5.5-2026-04-23` held fixed, temperature=1.0 pinned, reseed-per-call, universal truncation/empty-response guard active throughout. Scorer: `poc_compare_v2`'s pre-registered COMMIT/HEDGE classifier, imported unchanged, validated 11/11 on its held-out set once before this model's first run.

## Per-run counts

| Run | graph | flat_list_prioritized | flat_list | graph_neutral | none |
|---|---|---|---|---|---|
| 1 | 6/12 | 6/12 | 4/12 | 5/12 | 2/12 |
| 2 | 4/12 | 4/12 | 5/12 | 7/12 | 4/12 |
| 3 | 5/12 | 5/12 | 4/12 | 4/12 | 1/12 |
| 4 | 6/12 | 6/12 | 6/12 | 3/12 | 2/12 |
| 5 | 5/12 | 7/12 | 5/12 | 6/12 | 3/12 |

## Aggregate across runs (mean [min-max])

| Condition | mean | min | max |
|---|---|---|---|
| graph | 5.2/12 | 4/12 | 6/12 |
| flat_list_prioritized | 5.6/12 | 4/12 | 7/12 |
| flat_list | 4.8/12 | 4/12 | 6/12 |
| graph_neutral | 5.0/12 | 3/12 | 7/12 |
| none | 2.4/12 | 1/12 | 4/12 |

## Verdict comparisons (mean COMMIT count over runs)

- graph vs flat_list_prioritized: 5.2 vs 5.6  (flat_list_prioritized wins -> no structural signal)
- flat_list_prioritized vs flat_list: 5.6 vs 4.8  (flat_list_prioritized wins -> instructional signal)
- graph_neutral vs flat_list (structure alone, no instruction): 5.0 vs 4.8  (graph_neutral wins -> structure helps even without the instruction)
- graph_neutral vs graph (does the instruction add anything on top of structure): 5.0 vs 5.2  (graph wins)

**Verdict for `gpt-5.5-2026-04-23` on graph 2: INSTRUCTIONAL**