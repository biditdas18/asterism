# Task 1: Correctness of COMMIT-labeled responses

343 COMMIT-labeled responses across all Phase 2 data (3 models x 5 conditions x 5 runs x 12 queries). Ground truth and extraction method are in `research/correctness_analysis.py`. Q8 ('What's holding me back...') excluded as ambiguous ground truth (N/A), not force-scored.

## Per model / per condition (among COMMITs)

| Model | Condition | n | correct | wrong | unresolvable | correct-rate | wrong-rate | unresolvable-rate |
|---|---|---|---|---|---|---|---|---|
| claude-sonnet-4-6 | graph | 26 | 12 | 14 | 0 | 46% | 54% | 0% |
| claude-sonnet-4-6 | flat_list_prioritized | 15 | 1 | 14 | 0 | 7% | 93% | 0% |
| claude-sonnet-4-6 | flat_list | 18 | 4 | 14 | 0 | 22% | 78% | 0% |
| claude-sonnet-4-6 | graph_neutral | 41 | 19 | 22 | 0 | 46% | 54% | 0% |
| claude-sonnet-4-6 | none | 0 | - | - | - | - | - | - |
| claude-opus-4-8 | graph | 29 | 16 | 13 | 0 | 55% | 45% | 0% |
| claude-opus-4-8 | flat_list_prioritized | 18 | 6 | 12 | 0 | 33% | 67% | 0% |
| claude-opus-4-8 | flat_list | 8 | 2 | 6 | 0 | 25% | 75% | 0% |
| claude-opus-4-8 | graph_neutral | 27 | 21 | 6 | 0 | 78% | 22% | 0% |
| claude-opus-4-8 | none | 5 | 0 | 5 | 0 | 0% | 100% | 0% |
| gpt-5.5-2026-04-23 | graph | 31 | 23 | 8 | 0 | 74% | 26% | 0% |
| gpt-5.5-2026-04-23 | flat_list_prioritized | 32 | 18 | 14 | 0 | 56% | 44% | 0% |
| gpt-5.5-2026-04-23 | flat_list | 34 | 22 | 12 | 0 | 65% | 35% | 0% |
| gpt-5.5-2026-04-23 | graph_neutral | 31 | 21 | 10 | 0 | 68% | 32% | 0% |
| gpt-5.5-2026-04-23 | none | 11 | 1 | 10 | 0 | 9% | 91% | 0% |

## Off-graph sub-count (within WRONG, for auditability)

| Model | Condition | off_graph | wrong_on_graph |
|---|---|---|---|
| claude-sonnet-4-6 | graph | 2 | 12 |
| claude-sonnet-4-6 | flat_list_prioritized | 0 | 14 |
| claude-sonnet-4-6 | flat_list | 0 | 14 |
| claude-sonnet-4-6 | graph_neutral | 1 | 21 |
| claude-sonnet-4-6 | none | 0 | 0 |
| claude-opus-4-8 | graph | 0 | 13 |
| claude-opus-4-8 | flat_list_prioritized | 0 | 12 |
| claude-opus-4-8 | flat_list | 0 | 6 |
| claude-opus-4-8 | graph_neutral | 0 | 6 |
| claude-opus-4-8 | none | 5 | 0 |
| gpt-5.5-2026-04-23 | graph | 0 | 8 |
| gpt-5.5-2026-04-23 | flat_list_prioritized | 0 | 14 |
| gpt-5.5-2026-04-23 | flat_list | 0 | 12 |
| gpt-5.5-2026-04-23 | graph_neutral | 0 | 10 |
| gpt-5.5-2026-04-23 | none | 7 | 3 |

## Extraction confidence breakdown

| Model | high | low | off_graph | none(unresolvable) |
|---|---|---|---|---|
| claude-sonnet-4-6 | 97 | 0 | 3 | 0 |
| claude-opus-4-8 | 82 | 0 | 5 | 0 |
| gpt-5.5-2026-04-23 | 132 | 0 | 7 | 0 |

## Decisive comparison: accurate decisiveness, or just confident noise?

graph-like = graph + graph_neutral (both see the weighted structure). flat/none-like = flat_list + flat_list_prioritized + none (no weighting). If graph-like's correct-rate isn't clearly higher, the graph's added commit rate from Phase 2 would be confidence without accuracy.

| Model | graph-like correct-rate (n) | flat/none-like correct-rate (n) | verdict |
|---|---|---|---|
| claude-sonnet-4-6 | 31/67 (46%) | 5/33 (15%) | ACCURATE - graph-like commits are correct meaningfully more often |
| claude-opus-4-8 | 37/56 (66%) | 8/31 (26%) | ACCURATE - graph-like commits are correct meaningfully more often |
| gpt-5.5-2026-04-23 | 44/62 (71%) | 41/77 (53%) | ACCURATE - graph-like commits are correct meaningfully more often |

## Honest flag: absolute wrong-rate within the pure graph condition

Even where graph-like beats flat/none on correctness, the ABSOLUTE wrong-rate when graph itself commits is reported here without spin - a model can be more accurate than the alternative while still being wrong most of the time in absolute terms.

| Model | graph condition: correct | wrong | wrong-rate |
|---|---|---|---|
| claude-sonnet-4-6 | 12 | 14 | 54%  <-- WRONG more than half the time |
| claude-opus-4-8 | 16 | 13 | 45% |
| gpt-5.5-2026-04-23 | 23 | 8 | 26% |