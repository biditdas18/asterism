# Asterism Retrieval Latency Benchmark

_Generated 2026-08-09T16:45:26_

Measures `llm._load_graph_data()` — the query that loads and weight-ranks nodes (plus builds the parent map) for context injection in `inject_mode="graph"` — in isolation. No live API calls; local SQLite retrieval only.

Synthetic graphs use the domain -> theme -> concept chain shape from `demo_seed.py`, seeded into a throwaway test DB (`test_benchmark.db`, deleted after the run). 20 runs per scale.

| Nodes | Edges | Mean (ms) | P95 (ms) | Max (ms) | Min (ms) |
|---|---|---|---|---|---|
| 102 | 101 | 0.352 | 0.582 | 0.712 | 0.285 |
| 1,006 | 1,005 | 3.276 | 2.784 | 18.334 | 2.253 |
| 10,051 | 10,050 | 30.138 | 38.684 | 38.694 | 22.757 |

## Interpretation

Going from 102 to 10,051 nodes (99x more nodes) changed mean retrieval latency from 0.352ms to 30.138ms (85.6x). That's sub-linear to linear — retrieval time grows slower than or in line with graph size. In absolute terms, even the 10,051-node case averages 30.14ms (p95 38.68ms) per retrieval — negligible next to a network round-trip to the Claude API, so at these scales retrieval latency is not the conversational-UX bottleneck.