# Asterism Retrieval Latency Benchmark

_Generated 2026-08-09T16:26:08_

Measures `llm._load_graph_data()` — the query that loads and weight-ranks nodes (plus builds the parent map) for context injection in `inject_mode="graph"` — in isolation. No live API calls; local SQLite retrieval only.

Synthetic graphs use the domain -> theme -> concept chain shape from `demo_seed.py`, seeded into a throwaway test DB (`test_benchmark.db`, deleted after the run). 20 runs per scale.

| Nodes | Edges | Mean (ms) | P95 (ms) | Max (ms) | Min (ms) |
|---|---|---|---|---|---|
| 102 | 101 | 0.337 | 0.491 | 0.523 | 0.289 |
| 1,006 | 1,005 | 2.812 | 2.616 | 14.423 | 2.031 |
| 10,051 | 10,050 | 33.872 | 38.698 | 42.843 | 21.891 |

## Interpretation

Going from 102 to 10,051 nodes (99x more nodes) changed mean retrieval latency from 0.337ms to 33.872ms (100.5x). That's sub-linear to linear — retrieval time grows slower than or in line with graph size. In absolute terms, even the 10,051-node case averages 33.87ms (p95 38.70ms) per retrieval — negligible next to a network round-trip to the Claude API, so at these scales retrieval latency is not the conversational-UX bottleneck.