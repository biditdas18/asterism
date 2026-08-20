# Graph 2 (Priya): Correctness of COMMIT-labeled responses

219 COMMIT-labeled responses across all graph-2 Phase A data (3 models x 5 conditions x 5 runs x 12 queries). Ground truth and extraction method are in `research/correctness_analysis_graph2.py`. Q8 ('What's holding me back...') excluded as ambiguous ground truth (N/A), same as graph 1.

## Per model / per condition (among COMMITs)

| Model | Condition | n | correct | wrong | unresolvable | correct-rate | wrong-rate | unresolvable-rate |
|---|---|---|---|---|---|---|---|---|
| claude-sonnet-4-6 | graph | 20 | 16 | 4 | 0 | 80% | 20% | 0% |
| claude-sonnet-4-6 | flat_list_prioritized | 8 | 1 | 7 | 0 | 12% | 88% | 0% |
| claude-sonnet-4-6 | flat_list | 1 | 0 | 1 | 0 | 0% | 100% | 0% |
| claude-sonnet-4-6 | graph_neutral | 27 | 19 | 8 | 0 | 70% | 30% | 0% |
| claude-sonnet-4-6 | none | 0 | - | - | - | - | - | - |
| claude-opus-4-8 | graph | 19 | 12 | 7 | 0 | 63% | 37% | 0% |
| claude-opus-4-8 | flat_list_prioritized | 11 | 1 | 10 | 0 | 9% | 91% | 0% |
| claude-opus-4-8 | flat_list | 1 | 0 | 1 | 0 | 0% | 100% | 0% |
| claude-opus-4-8 | graph_neutral | 5 | 4 | 1 | 0 | 80% | 20% | 0% |
| claude-opus-4-8 | none | 1 | 0 | 1 | 0 | 0% | 100% | 0% |
| gpt-5.5-2026-04-23 | graph | 23 | 22 | 1 | 0 | 96% | 4% | 0% |
| gpt-5.5-2026-04-23 | flat_list_prioritized | 26 | 9 | 17 | 0 | 35% | 65% | 0% |
| gpt-5.5-2026-04-23 | flat_list | 22 | 8 | 14 | 0 | 36% | 64% | 0% |
| gpt-5.5-2026-04-23 | graph_neutral | 22 | 20 | 2 | 0 | 91% | 9% | 0% |
| gpt-5.5-2026-04-23 | none | 11 | 4 | 7 | 0 | 36% | 64% | 0% |

## Off-graph sub-count (within WRONG, for auditability)

| Model | Condition | off_graph | wrong_on_graph |
|---|---|---|---|
| claude-sonnet-4-6 | graph | 1 | 3 |
| claude-sonnet-4-6 | flat_list_prioritized | 0 | 7 |
| claude-sonnet-4-6 | flat_list | 0 | 1 |
| claude-sonnet-4-6 | graph_neutral | 0 | 8 |
| claude-sonnet-4-6 | none | 0 | 0 |
| claude-opus-4-8 | graph | 0 | 7 |
| claude-opus-4-8 | flat_list_prioritized | 0 | 10 |
| claude-opus-4-8 | flat_list | 0 | 1 |
| claude-opus-4-8 | graph_neutral | 0 | 1 |
| claude-opus-4-8 | none | 1 | 0 |
| gpt-5.5-2026-04-23 | graph | 0 | 1 |
| gpt-5.5-2026-04-23 | flat_list_prioritized | 0 | 17 |
| gpt-5.5-2026-04-23 | flat_list | 0 | 14 |
| gpt-5.5-2026-04-23 | graph_neutral | 0 | 2 |
| gpt-5.5-2026-04-23 | none | 7 | 0 |

## Extraction confidence breakdown

| Model | high | low | off_graph | none(unresolvable) |
|---|---|---|---|---|
| claude-sonnet-4-6 | 55 | 0 | 1 | 0 |
| claude-opus-4-8 | 36 | 0 | 1 | 0 |
| gpt-5.5-2026-04-23 | 97 | 0 | 7 | 0 |

## Decisive comparison: accurate decisiveness, or just confident noise?

graph-like = graph + graph_neutral (both see the weighted structure). flat/none-like = flat_list + flat_list_prioritized + none (no weighting).

| Model | graph-like correct-rate (n) | flat/none-like correct-rate (n) | verdict |
|---|---|---|---|
| claude-sonnet-4-6 | 35/47 (74%) | 1/9 (11%) | ACCURATE - graph-like commits are correct meaningfully more often |
| claude-opus-4-8 | 16/24 (67%) | 1/13 (8%) | ACCURATE - graph-like commits are correct meaningfully more often |
| gpt-5.5-2026-04-23 | 42/45 (93%) | 21/59 (36%) | ACCURATE - graph-like commits are correct meaningfully more often |

## Honest flag: absolute wrong-rate within the pure graph condition

| Model | graph condition: correct | wrong | wrong-rate |
|---|---|---|---|
| claude-sonnet-4-6 | 16 | 4 | 20% |
| claude-opus-4-8 | 12 | 7 | 37% |
| gpt-5.5-2026-04-23 | 22 | 1 | 4% |