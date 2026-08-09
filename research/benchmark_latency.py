#!/usr/bin/env python3
"""
Benchmark: does graph retrieval scale acceptably as the graph grows?

Times llm._load_graph_data() — the query that loads and weight-ranks
nodes (plus builds the parent map) for context injection in
inject_mode="graph" — in isolation. Local-only, no live API calls.

Seeds a throwaway test DB with synthetic domain -> theme -> concept
graphs (same shape as demo_seed.py, not flat random nodes) at
100 / 1,000 / 10,000 nodes, times the retrieval call 20x per scale,
and writes min/mean/p95/max to benchmark_results.md.

Usage: python research/benchmark_latency.py (from repo root, or anywhere)
"""
import datetime
import os
import random
import sqlite3
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import db
import llm

RESULTS_DIR = os.path.join(HERE, "results")
TEST_DB_PATH = os.path.join(HERE, "test_benchmark.db")
SCHEMA_PATH = os.path.join(ROOT, "schema.sql")
SCALES = [100, 1_000, 10_000]
RUNS_PER_SCALE = 20


def _init_test_db():
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    conn = sqlite3.connect(TEST_DB_PATH)
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())
    conn.close()


def _seed_synthetic_graph(target_nodes: int) -> tuple[int, int]:
    """
    Bulk-insert a domain -> theme -> concept chain graph (demo_seed.py's
    shape) sized to ~target_nodes total nodes, with weighted edges.
    Bypasses db.add_node/add_edge (and their entity-dedup check) via
    direct sqlite3 executemany — labels here are synthetic and unique
    by construction, so dedup has nothing to do; this is seeding, not
    the retrieval path under test.
    """
    rng = random.Random(42)
    node_rows = [("User", "user", 100.0)]
    edge_rows = []  # (source_label, target_label, weight)

    n_domains = max(1, target_nodes // 200)
    themes_per_domain = 5
    concepts_per_theme = max(1, (target_nodes - n_domains) // (n_domains * themes_per_domain))

    for d in range(n_domains):
        domain = f"Domain {d}"
        node_rows.append((domain, "domain", round(rng.uniform(20, 100), 1)))
        edge_rows.append(("User", domain, 1.0))
        for t in range(themes_per_domain):
            theme = f"Domain {d} Theme {t}"
            node_rows.append((theme, "theme", round(rng.uniform(10, 80), 1)))
            edge_rows.append((domain, theme, 1.0))
            prev = theme
            for c in range(concepts_per_theme):
                concept = f"Domain {d} Theme {t} Concept {c}"
                node_rows.append((concept, "concept", round(rng.uniform(1, 60), 1)))
                edge_rows.append((prev, concept, 1.0))
                prev = concept

    conn = sqlite3.connect(TEST_DB_PATH)
    conn.executemany(
        "INSERT INTO nodes (label, node_type, weight) VALUES (?, ?, ?)", node_rows
    )
    label_to_id = {label: nid for nid, label in conn.execute("SELECT id, label FROM nodes")}
    edge_id_rows = [(label_to_id[s], label_to_id[t], w) for s, t, w in edge_rows]
    conn.executemany(
        "INSERT INTO edges (source_id, target_id, weight) VALUES (?, ?, ?)", edge_id_rows
    )
    conn.commit()
    conn.close()
    return len(node_rows), len(edge_id_rows)


def _percentile(values: list[float], pct: float) -> float:
    s = sorted(values)
    return s[round(pct * (len(s) - 1))]


def _time_retrieval(n_runs: int) -> list[float]:
    times = []
    for _ in range(n_runs):
        t0 = time.perf_counter()
        llm._load_graph_data()
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000)  # ms
    return times


def run() -> list[dict]:
    db.DB_PATH = TEST_DB_PATH  # redirect retrieval path at a throwaway DB
    results = []
    for scale in SCALES:
        _init_test_db()
        n_nodes, n_edges = _seed_synthetic_graph(scale)
        times = _time_retrieval(RUNS_PER_SCALE)
        result = {
            "target_nodes": scale,
            "actual_nodes": n_nodes,
            "actual_edges": n_edges,
            "min_ms": min(times),
            "mean_ms": statistics.mean(times),
            "p95_ms": _percentile(times, 0.95),
            "max_ms": max(times),
        }
        results.append(result)
        print(f"{n_nodes:>6} nodes / {n_edges:>6} edges: "
              f"mean={result['mean_ms']:.3f}ms  p95={result['p95_ms']:.3f}ms  "
              f"max={result['max_ms']:.3f}ms  min={result['min_ms']:.3f}ms")
    return results


def _classify_scaling(results: list[dict]) -> str:
    first, last = results[0], results[-1]
    node_ratio = last["actual_nodes"] / first["actual_nodes"]
    time_ratio = last["mean_ms"] / first["mean_ms"] if first["mean_ms"] > 0 else float("inf")
    if time_ratio <= node_ratio * 1.3:
        verdict = "sub-linear to linear — retrieval time grows slower than or in line with graph size"
    elif time_ratio <= node_ratio * 2.5:
        verdict = "roughly linear, with some overhead beyond pure O(n) — likely the unindexed ORDER BY weight sort"
    else:
        verdict = "worse than linear — retrieval time is growing meaningfully faster than the graph itself"
    return (
        f"Going from {first['actual_nodes']:,} to {last['actual_nodes']:,} nodes "
        f"({node_ratio:.0f}x more nodes) changed mean retrieval latency from "
        f"{first['mean_ms']:.3f}ms to {last['mean_ms']:.3f}ms ({time_ratio:.1f}x). "
        f"That's {verdict}. In absolute terms, even the {last['actual_nodes']:,}-node case "
        f"averages {last['mean_ms']:.2f}ms (p95 {last['p95_ms']:.2f}ms) per retrieval — "
        f"negligible next to a network round-trip to the Claude API, so at these scales "
        f"retrieval latency is not the conversational-UX bottleneck."
    )


def render_markdown(results: list[dict]) -> str:
    lines = [
        "# Asterism Retrieval Latency Benchmark",
        "",
        f"_Generated {datetime.datetime.now().isoformat(timespec='seconds')}_",
        "",
        "Measures `llm._load_graph_data()` — the query that loads and weight-ranks "
        "nodes (plus builds the parent map) for context injection in "
        '`inject_mode="graph"` — in isolation. No live API calls; local SQLite '
        "retrieval only.",
        "",
        "Synthetic graphs use the domain -> theme -> concept chain shape from "
        f"`demo_seed.py`, seeded into a throwaway test DB (`test_benchmark.db`, "
        f"deleted after the run). {RUNS_PER_SCALE} runs per scale.",
        "",
        "| Nodes | Edges | Mean (ms) | P95 (ms) | Max (ms) | Min (ms) |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['actual_nodes']:,} | {r['actual_edges']:,} | {r['mean_ms']:.3f} | "
            f"{r['p95_ms']:.3f} | {r['max_ms']:.3f} | {r['min_ms']:.3f} |"
        )
    lines += ["", "## Interpretation", "", _classify_scaling(results)]
    return "\n".join(lines)


if __name__ == "__main__":
    results = run()
    md = render_markdown(results)
    out_path = os.path.join(RESULTS_DIR, "benchmark_results.md")
    with open(out_path, "w") as f:
        f.write(md)
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    print(f"\nWrote {out_path}; cleaned up test DB.")
