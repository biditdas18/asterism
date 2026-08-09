#!/usr/bin/env python3
"""
PoC: does graph-indexed retrieval (weighted top-N nodes, traversal-aware)
beat a flat, unstructured list of the same underlying facts — and does
either beat having no memory at all?

Runs a fixed set of queries three times each via llm.converse(), once per
inject_mode ("graph", "flat_list", "none"), and writes the responses
side by side to poc_results.md / .json.

The headline comparison is graph vs. flat_list — both see the same facts
from the same DB, so any difference isolates the value of the graph
structure itself (weighting + hierarchy + traversal), not just "having
memory". flat_list vs. none is kept for reference (the has-memory-at-all
baseline).

Usage: python poc_compare.py
Requires ANTHROPIC_API_KEY configured (see config.py / .env).
"""
import datetime
import json

from db import get_connection
from llm import converse, _load_graph_data

QUERIES = [
    "What have I been working on lately?",
    "What's my top priority right now?",
    "How does my interest in Stoicism connect to my career?",
    "Summarize what you know about me in a few sentences.",
    "What should I focus on next?",
]

MODES = ["graph", "flat_list", "none"]


def _injected_context():
    """The top-30 weighted nodes converse(inject_mode='graph') puts in the
    system prompt, plus the edges connecting them (for reference only —
    converse() injects the weighted node list as text, not edges), plus
    the full unweighted label set converse(inject_mode='flat_list') uses."""
    nodes, _ = _load_graph_data()
    top = nodes[:30]
    labels = {n["label"] for n in top}
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT n1.label AS src, n2.label AS tgt, e.weight AS w
            FROM edges e
            JOIN nodes n1 ON e.source_id = n1.id
            JOIN nodes n2 ON e.target_id = n2.id
        """).fetchall()
    edges = [dict(r) for r in rows if r["src"] in labels and r["tgt"] in labels]
    all_labels = sorted(n["label"] for n in nodes)
    return top, edges, all_labels


def run():
    injected_nodes, injected_edges, flat_labels = _injected_context()
    results = []
    for q in QUERIES:
        by_mode = {}
        for mode in MODES:
            print(f"Querying (inject_mode={mode}): {q!r}")
            out = converse(q, [], inject_mode=mode)
            by_mode[mode] = {
                "response": out["response"],
                "tokens_used": out["tokens_used"],
            }
        results.append({"query": q, **by_mode})
    return results, injected_nodes, injected_edges, flat_labels


def render_markdown(results, injected_nodes, injected_edges, flat_labels) -> str:
    lines = [
        "# Asterism PoC: Graph-Indexed vs. Flat-List vs. No-Memory Comparison",
        "",
        f"_Generated {datetime.datetime.now().isoformat(timespec='seconds')}_",
        "",
        "Each query below was run three times against the same model on the same DB, "
        "one per `inject_mode`:",
        "",
        "- **graph** — top-30 weighted nodes injected, traversal-aware (current behavior)",
        "- **flat_list** — all node labels injected as an unweighted, unstructured list "
        "(same underlying facts as `graph`, no weighting/hierarchy/traversal)",
        "- **none** — no graph context injected at all (no-memory baseline)",
        "",
        "**Headline comparison: `graph` vs. `flat_list`.** Both see the same facts from the "
        "same DB, so any difference isolates the value of the graph structure itself, not "
        "just \"having memory\". `flat_list` vs. `none` is kept for reference only.",
        "",
        "## Injected context",
        "",
        f"**graph mode — {len(injected_nodes)} nodes** injected, highest weight first:",
        "",
    ]
    for n in injected_nodes:
        lines.append(f"- [{n['node_type']}] {n['label']} (weight: {n['weight']:.1f})")
    lines += [
        "",
        f"**graph mode — {len(injected_edges)} edges** among those nodes (shown for "
        "reference — `converse()` injects the weighted node list as text, not edges):",
        "",
    ]
    for e in injected_edges:
        lines.append(f"- {e['src']} → {e['tgt']} (weight: {e['w']:.1f})")
    lines += [
        "",
        f"**flat_list mode — {len(flat_labels)} labels** injected, alphabetical, no weights/hierarchy:",
        "",
        ", ".join(flat_labels),
        "",
        "## Query comparisons",
        "",
    ]

    for i, r in enumerate(results, 1):
        lines += [f"### {i}. {r['query']}", ""]
        for mode, heading in [
            ("graph", "**graph (weighted, traversal-aware):**"),
            ("flat_list", "**flat_list (unweighted, unstructured):**"),
            ("none", "**none (no memory):**"),
        ]:
            lines += [
                heading,
                "",
                "> " + r[mode]["response"].replace("\n", "\n> "),
                "",
                f"_tokens: {r[mode]['tokens_used']}_",
                "",
            ]
    return "\n".join(lines)


if __name__ == "__main__":
    results, injected_nodes, injected_edges, flat_labels = run()

    with open("poc_results.json", "w") as f:
        json.dump({
            "injected_nodes": injected_nodes,
            "injected_edges": injected_edges,
            "flat_list_labels": flat_labels,
            "results": results,
        }, f, indent=2)

    md = render_markdown(results, injected_nodes, injected_edges, flat_labels)
    with open("poc_results.md", "w") as f:
        f.write(md)

    print("\nWrote poc_results.md and poc_results.json")
