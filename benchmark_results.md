# Asterism Retrieval Latency Benchmark

_Generated 2026-08-09T17:02:14_

Measures `llm._load_graph_data()` — the query that loads and weight-ranks nodes (plus builds the parent map) for context injection in `inject_mode="graph"` — in isolation. No live API calls; local SQLite retrieval only.

Synthetic graphs use the domain -> theme -> concept chain shape from `demo_seed.py`, seeded into a throwaway test DB (`test_benchmark.db`, deleted after the run). 20 runs per scale.

| Nodes | Edges | Mean (ms) | P95 (ms) | Max (ms) | Min (ms) |
|---|---|---|---|---|---|
| 102 | 101 | 0.415 | 0.528 | 1.092 | 0.338 |
| 1,006 | 1,005 | 3.663 | 3.554 | 18.433 | 2.541 |
| 10,051 | 10,050 | 35.238 | 45.938 | 60.225 | 26.395 |

## Interpretation

Going from 102 to 10,051 nodes (99x more nodes) changed mean retrieval latency from 0.415ms to 35.238ms (84.9x). That's sub-linear to linear — retrieval time grows slower than or in line with graph size. In absolute terms, even the 10,051-node case averages 35.24ms (p95 45.94ms) per retrieval — negligible next to a network round-trip to the Claude API, so at these scales retrieval latency is not the conversational-UX bottleneck.