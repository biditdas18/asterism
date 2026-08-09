# Asterism Retrieval Latency Benchmark

_Generated 2026-08-09T18:30:58_

Measures `llm._load_graph_data()` — the query that loads and weight-ranks nodes (plus builds the parent map) for context injection in `inject_mode="graph"` — in isolation. No live API calls; local SQLite retrieval only.

Synthetic graphs use the domain -> theme -> concept chain shape from `demo_seed.py`, seeded into a throwaway test DB (`test_benchmark.db`, deleted after the run). 20 runs per scale.

| Nodes | Edges | Mean (ms) | P95 (ms) | Max (ms) | Min (ms) |
|---|---|---|---|---|---|
| 102 | 101 | 0.214 | 0.253 | 0.329 | 0.197 |
| 1,006 | 1,005 | 2.199 | 1.805 | 12.992 | 1.433 |
| 10,051 | 10,050 | 21.128 | 27.865 | 28.429 | 15.589 |

## Interpretation

Going from 102 to 10,051 nodes (99x more nodes) changed mean retrieval latency from 0.214ms to 21.128ms (98.6x). That's sub-linear to linear — retrieval time grows slower than or in line with graph size. In absolute terms, even the 10,051-node case averages 21.13ms (p95 27.87ms) per retrieval — negligible next to a network round-trip to the Claude API, so at these scales retrieval latency is not the conversational-UX bottleneck.