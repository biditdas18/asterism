# Asterism PoC Phase 2 / Graph 2 (Priya): Aggregate — `claude-opus-4-8`

_Generated 2026-08-12T04:16:44_

5 independent run(s) against seed_graph_2 (Priya persona), 12 PRIORITY queries x 5 conditions each, assistant model `claude-opus-4-8` held fixed, temperature=1.0 pinned, reseed-per-call, universal truncation/empty-response guard active throughout. Scorer: `poc_compare_v2`'s pre-registered COMMIT/HEDGE classifier, imported unchanged, validated 11/11 on its held-out set once before this model's first run.

## Per-run counts

| Run | graph | flat_list_prioritized | flat_list | graph_neutral | none |
|---|---|---|---|---|---|
| 1 | 7/12 | 3/12 | 1/12 | 0/12 | 1/12 |
| 2 | 4/12 | 2/12 | 0/12 | 2/12 | 0/12 |
| 3 | 6/12 | 5/12 | 1/12 | 1/12 | 0/12 |
| 4 | 4/12 | 2/12 | 0/12 | 2/12 | 0/12 |
| 5 | 0/12 | 1/12 | 1/12 | 1/12 | 0/12 |

## Aggregate across runs (mean [min-max])

| Condition | mean | min | max |
|---|---|---|---|
| graph | 4.2/12 | 0/12 | 7/12 |
| flat_list_prioritized | 2.6/12 | 1/12 | 5/12 |
| flat_list | 0.6/12 | 0/12 | 1/12 |
| graph_neutral | 1.2/12 | 0/12 | 2/12 |
| none | 0.2/12 | 0/12 | 1/12 |

## Verdict comparisons (mean COMMIT count over runs)

- graph vs flat_list_prioritized: 4.2 vs 2.6  (graph wins -> structural signal)
- flat_list_prioritized vs flat_list: 2.6 vs 0.6  (flat_list_prioritized wins -> instructional signal)
- graph_neutral vs flat_list (structure alone, no instruction): 1.2 vs 0.6  (graph_neutral wins -> structure helps even without the instruction)
- graph_neutral vs graph (does the instruction add anything on top of structure): 1.2 vs 4.2  (graph wins)

**Verdict for `claude-opus-4-8` on graph 2: MIXED**