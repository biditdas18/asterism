# Asterism PoC Phase 2 / Graph 2 (Priya): Aggregate — `gemini-3.6-flash`

_Generated 2026-08-12T15:35:50_

5 independent run(s) against seed_graph_2 (Priya persona), 12 PRIORITY queries x 5 conditions each, assistant model `gemini-3.6-flash` held fixed, temperature=1.0 pinned, reseed-per-call, universal truncation/empty-response guard active throughout. Scorer: `poc_compare_v2`'s pre-registered COMMIT/HEDGE classifier, imported unchanged, validated 11/11 on its held-out set once before this model's first run.

## Per-run counts

| Run | graph | flat_list_prioritized | flat_list | graph_neutral | none |
|---|---|---|---|---|---|
| 1 | 0/12 | 2/12 | 1/12 | 3/12 | 1/12 |
| 2 | 0/12 | 1/12 | 0/12 | 1/12 | 1/12 |
| 3 | 2/12 | 1/12 | 1/12 | 1/12 | 0/12 |
| 4 | 0/12 | 1/12 | 0/12 | 0/12 | 1/12 |
| 5 | 2/12 | 1/12 | 1/12 | 0/12 | 1/12 |

## Aggregate across runs (mean [min-max])

| Condition | mean | min | max |
|---|---|---|---|
| graph | 0.8/12 | 0/12 | 2/12 |
| flat_list_prioritized | 1.2/12 | 1/12 | 2/12 |
| flat_list | 0.6/12 | 0/12 | 1/12 |
| graph_neutral | 1.0/12 | 0/12 | 3/12 |
| none | 0.8/12 | 0/12 | 1/12 |

## Verdict comparisons (mean COMMIT count over runs)

- graph vs flat_list_prioritized: 0.8 vs 1.2  (flat_list_prioritized wins -> no structural signal)
- flat_list_prioritized vs flat_list: 1.2 vs 0.6  (flat_list_prioritized wins -> instructional signal)
- graph_neutral vs flat_list (structure alone, no instruction): 1.0 vs 0.6  (graph_neutral wins -> structure helps even without the instruction)
- graph_neutral vs graph (does the instruction add anything on top of structure): 1.0 vs 0.8  (graph_neutral wins)

**Verdict for `gemini-3.6-flash` on graph 2: INSTRUCTIONAL**