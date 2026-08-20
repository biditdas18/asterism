# Phase C (N=100) Analysis

Scorer: frozen v2 `classify_commit_or_hedge`, validated 11/11 pre-flight, labels read from already-collected data (scored live during collection, not rescored here). Correctness scored only on the defensible-margin query set (graph1: 96/100, graph2: 69/100) using each query's own query-local margin, not a global figure. deepseek-v4-pro is missing graph1/graph_neutral (disclosed skip, not interpolated) - see notes per model.

## claude-sonnet-4-6

### graph1

| Condition | mean COMMIT/100 | min | max |
|---|---|---|---|
| graph | 47.8 | 44 | 52 |
| flat_list_prioritized | 32.4 | 29 | 35 |
| flat_list | 26.0 | 21 | 28 |
| graph_neutral | 45.4 | 41 | 51 |
| none | 0.8 | 0 | 1 |

- **graph vs flat_list gap (deployed benefit): +21.8** (47.8 vs 26.0)
- **graph_neutral vs flat_list gap (structure-only, Finding 3): +19.4** (45.4 vs 26.0)

**Correctness (Finding 2, defensible-margin set only, absolute numbers):**
| Condition | n COMMIT-in-set | correct | wrong | unresolvable | correct-rate |
|---|---|---|---|---|---|
| graph | 229 | 112 | 117 | 0 | 49% |
| flat_list_prioritized | 154 | 39 | 115 | 0 | 25% |
| flat_list | 125 | 40 | 85 | 0 | 32% |
| graph_neutral | 212 | 108 | 104 | 0 | 51% |
| none | 4 | 0 | 4 | 0 | 0% |

- graph-like (graph+graph_neutral) correct: **220/441 (50%)**
- flat/none-like correct: **79/283 (28%)**

### graph2

| Condition | mean COMMIT/100 | min | max |
|---|---|---|---|
| graph | 49.6 | 47 | 53 |
| flat_list_prioritized | 32.2 | 26 | 35 |
| flat_list | 10.8 | 8 | 14 |
| graph_neutral | 31.0 | 29 | 33 |
| none | 0.2 | 0 | 1 |

- **graph vs flat_list gap (deployed benefit): +38.8** (49.6 vs 10.8)
- **graph_neutral vs flat_list gap (structure-only, Finding 3): +20.2** (31.0 vs 10.8)

**Correctness (Finding 2, defensible-margin set only, absolute numbers):**
| Condition | n COMMIT-in-set | correct | wrong | unresolvable | correct-rate |
|---|---|---|---|---|---|
| graph | 167 | 103 | 64 | 0 | 62% |
| flat_list_prioritized | 120 | 50 | 70 | 0 | 42% |
| flat_list | 44 | 20 | 24 | 0 | 45% |
| graph_neutral | 96 | 46 | 50 | 0 | 48% |
| none | 1 | 1 | 0 | 0 | 100% |

- graph-like (graph+graph_neutral) correct: **149/263 (57%)**
- flat/none-like correct: **71/165 (43%)**

## claude-opus-4-8

### graph1

| Condition | mean COMMIT/100 | min | max |
|---|---|---|---|
| graph | 49.2 | 47 | 52 |
| flat_list_prioritized | 30.8 | 23 | 36 |
| flat_list | 13.2 | 10 | 20 |
| graph_neutral | 36.8 | 30 | 43 |
| none | 1.0 | 0 | 2 |

- **graph vs flat_list gap (deployed benefit): +36.0** (49.2 vs 13.2)
- **graph_neutral vs flat_list gap (structure-only, Finding 3): +23.6** (36.8 vs 13.2)

**Correctness (Finding 2, defensible-margin set only, absolute numbers):**
| Condition | n COMMIT-in-set | correct | wrong | unresolvable | correct-rate |
|---|---|---|---|---|---|
| graph | 236 | 149 | 87 | 0 | 63% |
| flat_list_prioritized | 149 | 77 | 72 | 0 | 52% |
| flat_list | 65 | 39 | 26 | 0 | 60% |
| graph_neutral | 178 | 101 | 77 | 0 | 57% |
| none | 5 | 0 | 5 | 0 | 0% |

- graph-like (graph+graph_neutral) correct: **250/414 (60%)**
- flat/none-like correct: **116/219 (53%)**

### graph2

| Condition | mean COMMIT/100 | min | max |
|---|---|---|---|
| graph | 38.4 | 34 | 44 |
| flat_list_prioritized | 31.0 | 24 | 37 |
| flat_list | 5.8 | 2 | 9 |
| graph_neutral | 22.2 | 16 | 27 |
| none | 1.6 | 0 | 4 |

- **graph vs flat_list gap (deployed benefit): +32.6** (38.4 vs 5.8)
- **graph_neutral vs flat_list gap (structure-only, Finding 3): +16.4** (22.2 vs 5.8)

**Correctness (Finding 2, defensible-margin set only, absolute numbers):**
| Condition | n COMMIT-in-set | correct | wrong | unresolvable | correct-rate |
|---|---|---|---|---|---|
| graph | 130 | 73 | 57 | 0 | 56% |
| flat_list_prioritized | 118 | 51 | 67 | 0 | 43% |
| flat_list | 21 | 12 | 9 | 0 | 57% |
| graph_neutral | 77 | 38 | 39 | 0 | 49% |
| none | 2 | 1 | 1 | 0 | 50% |

- graph-like (graph+graph_neutral) correct: **111/207 (54%)**
- flat/none-like correct: **64/141 (45%)**

## gpt-5.5-2026-04-23

### graph1

| Condition | mean COMMIT/100 | min | max |
|---|---|---|---|
| graph | 50.8 | 46 | 54 |
| flat_list_prioritized | 40.4 | 37 | 43 |
| flat_list | 35.6 | 31 | 40 |
| graph_neutral | 40.8 | 37 | 44 |
| none | 23.6 | 22 | 26 |

- **graph vs flat_list gap (deployed benefit): +15.2** (50.8 vs 35.6)
- **graph_neutral vs flat_list gap (structure-only, Finding 3): +5.2** (40.8 vs 35.6)

**Correctness (Finding 2, defensible-margin set only, absolute numbers):**
| Condition | n COMMIT-in-set | correct | wrong | unresolvable | correct-rate |
|---|---|---|---|---|---|
| graph | 239 | 182 | 57 | 0 | 76% |
| flat_list_prioritized | 190 | 90 | 100 | 0 | 47% |
| flat_list | 167 | 88 | 79 | 0 | 53% |
| graph_neutral | 193 | 152 | 41 | 0 | 79% |
| none | 109 | 38 | 71 | 0 | 35% |

- graph-like (graph+graph_neutral) correct: **334/432 (77%)**
- flat/none-like correct: **216/466 (46%)**

### graph2

| Condition | mean COMMIT/100 | min | max |
|---|---|---|---|
| graph | 54.4 | 50 | 57 |
| flat_list_prioritized | 50.6 | 45 | 57 |
| flat_list | 36.0 | 33 | 38 |
| graph_neutral | 40.2 | 36 | 48 |
| none | 30.8 | 28 | 35 |

- **graph vs flat_list gap (deployed benefit): +18.4** (54.4 vs 36.0)
- **graph_neutral vs flat_list gap (structure-only, Finding 3): +4.2** (40.2 vs 36.0)

**Correctness (Finding 2, defensible-margin set only, absolute numbers):**
| Condition | n COMMIT-in-set | correct | wrong | unresolvable | correct-rate |
|---|---|---|---|---|---|
| graph | 208 | 145 | 63 | 0 | 70% |
| flat_list_prioritized | 193 | 118 | 75 | 0 | 61% |
| flat_list | 141 | 88 | 53 | 0 | 62% |
| graph_neutral | 162 | 116 | 46 | 0 | 72% |
| none | 124 | 61 | 63 | 0 | 49% |

- graph-like (graph+graph_neutral) correct: **261/370 (71%)**
- flat/none-like correct: **267/458 (58%)**

## deepseek-v4-pro

### graph1
**MISSING DATA: graph_neutral (disclosed skip, not interpolated)**

| Condition | mean COMMIT/100 | min | max |
|---|---|---|---|
| graph | 15.0 | 11 | 20 |
| flat_list_prioritized | 17.4 | 12 | 23 |
| flat_list | 10.6 | 6 | 15 |
| graph_neutral | **MISSING** | - | - |
| none | 5.0 | 3 | 7 |

- **graph vs flat_list gap (deployed benefit): +4.4** (15.0 vs 10.6)
- graph_neutral vs flat_list gap (structure-only, Finding 3): **N/A - graph_neutral missing for this graph, not computed**

**Correctness (Finding 2, defensible-margin set only, absolute numbers):**
| Condition | n COMMIT-in-set | correct | wrong | unresolvable | correct-rate |
|---|---|---|---|---|---|
| graph | 69 | 43 | 26 | 0 | 62% |
| flat_list_prioritized | 78 | 27 | 51 | 0 | 35% |
| flat_list | 50 | 13 | 37 | 0 | 26% |
| graph_neutral | **MISSING** | - | - | - | - |
| none | 24 | 8 | 16 | 0 | 33% |

- graph-like (graph+graph_neutral) correct: **43/69 (62%)**
- flat/none-like correct: **48/152 (32%)**

### graph2

| Condition | mean COMMIT/100 | min | max |
|---|---|---|---|
| graph | 16.8 | 13 | 23 |
| flat_list_prioritized | 13.4 | 12 | 15 |
| flat_list | 7.4 | 5 | 9 |
| graph_neutral | 14.4 | 11 | 19 |
| none | 3.8 | 3 | 5 |

- **graph vs flat_list gap (deployed benefit): +9.4** (16.8 vs 7.4)
- **graph_neutral vs flat_list gap (structure-only, Finding 3): +7.0** (14.4 vs 7.4)

**Correctness (Finding 2, defensible-margin set only, absolute numbers):**
| Condition | n COMMIT-in-set | correct | wrong | unresolvable | correct-rate |
|---|---|---|---|---|---|
| graph | 51 | 36 | 15 | 0 | 71% |
| flat_list_prioritized | 52 | 30 | 22 | 0 | 58% |
| flat_list | 22 | 12 | 10 | 0 | 55% |
| graph_neutral | 48 | 36 | 12 | 0 | 75% |
| none | 15 | 8 | 7 | 0 | 53% |

- graph-like (graph+graph_neutral) correct: **72/99 (73%)**
- flat/none-like correct: **50/89 (56%)**

## kimi-k3

### graph1

| Condition | mean COMMIT/100 | min | max |
|---|---|---|---|
| graph | 17.8 | 15 | 21 |
| flat_list_prioritized | 20.6 | 12 | 27 |
| flat_list | 15.2 | 10 | 19 |
| graph_neutral | 12.6 | 7 | 15 |
| none | 2.0 | 1 | 4 |

- **graph vs flat_list gap (deployed benefit): +2.6** (17.8 vs 15.2)
- **graph_neutral vs flat_list gap (structure-only, Finding 3): -2.6** (12.6 vs 15.2)

**Correctness (Finding 2, defensible-margin set only, absolute numbers):**
| Condition | n COMMIT-in-set | correct | wrong | unresolvable | correct-rate |
|---|---|---|---|---|---|
| graph | 83 | 60 | 23 | 0 | 72% |
| flat_list_prioritized | 97 | 53 | 44 | 0 | 55% |
| flat_list | 74 | 40 | 34 | 0 | 54% |
| graph_neutral | 60 | 44 | 16 | 0 | 73% |
| none | 10 | 0 | 10 | 0 | 0% |

- graph-like (graph+graph_neutral) correct: **104/143 (73%)**
- flat/none-like correct: **93/181 (51%)**

### graph2

| Condition | mean COMMIT/100 | min | max |
|---|---|---|---|
| graph | 16.2 | 11 | 22 |
| flat_list_prioritized | 11.4 | 7 | 16 |
| flat_list | 8.0 | 4 | 10 |
| graph_neutral | 11.2 | 7 | 14 |
| none | 1.8 | 0 | 4 |

- **graph vs flat_list gap (deployed benefit): +8.2** (16.2 vs 8.0)
- **graph_neutral vs flat_list gap (structure-only, Finding 3): +3.2** (11.2 vs 8.0)

**Correctness (Finding 2, defensible-margin set only, absolute numbers):**
| Condition | n COMMIT-in-set | correct | wrong | unresolvable | correct-rate |
|---|---|---|---|---|---|
| graph | 63 | 38 | 25 | 0 | 60% |
| flat_list_prioritized | 37 | 21 | 16 | 0 | 57% |
| flat_list | 30 | 17 | 13 | 0 | 57% |
| graph_neutral | 43 | 30 | 13 | 0 | 70% |
| none | 6 | 1 | 5 | 0 | 17% |

- graph-like (graph+graph_neutral) correct: **68/106 (64%)**
- flat/none-like correct: **39/73 (53%)**
