"""
Demo seed: wipes asterism.db and rebuilds it with fictional data for user "Alex".
Run: python demo_seed.py
"""
import os
import sys
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db as _db
from db import init_db, add_node, add_edge, get_connection
from config import get_db_path, load_config, save_config

# ── wipe and reinit ──────────────────────────────────────────────────────────

db_path = get_db_path()
if os.path.exists(db_path):
    os.remove(db_path)

_db.DB_PATH = db_path
init_db()

# ── point config at Alex so asterism view renders correctly ──────────────────

config = load_config()
config["user_name"] = "Alex"
save_config(config)

# ── helpers ──────────────────────────────────────────────────────────────────

def set_weight(label: str, weight: float):
    with get_connection() as conn:
        conn.execute("UPDATE nodes SET weight = ? WHERE label = ?", (weight, label))


def add_chain(parent: str, titles: list[str], base_weight: float):
    """Add causal chain: parent → t0 → t1 → … with linearly decreasing weights."""
    prev = parent
    n = len(titles)
    for i, title in enumerate(titles):
        w = base_weight * (1 - 0.05 * i)   # slight recency gradient
        add_node(title, node_type="concept")
        set_weight(title, round(w, 1))
        add_edge(prev, title)
        prev = title


# ── graph data ───────────────────────────────────────────────────────────────

USER = "Alex"
add_node(USER, node_type="user")
set_weight(USER, 100.0)

GRAPH = [
    {
        "domain": "Open Source Development",
        "domain_weight": 85,
        "themes": [
            {
                "name": "AI Memory Tools",
                "weight": 80,
                "chain": [
                    "LLM context window limitations",
                    "Knowledge graph architecture research",
                    "Hebbian decay design",
                    "Graph as retrieval index insight",
                    "Constellation visualization build",
                    "PyPI packaging strategy",
                    "Reddit launch preparation",
                ],
            },
            {
                "name": "CLI Tools",
                "weight": 72,
                "chain": [
                    "Python project ideation",
                    "Click framework exploration",
                    "Package structure design",
                    "User adoption optimization",
                ],
            },
        ],
    },
    {
        "domain": "Career Growth",
        "domain_weight": 75,
        "themes": [
            {
                "name": "Research Identity",
                "weight": 70,
                "chain": [
                    "First academic paper idea",
                    "arXiv submission process",
                    "Peer review participation",
                    "Conference paper planning",
                    "Citation building strategy",
                ],
            },
            {
                "name": "Technical Skills",
                "weight": 65,
                "chain": [
                    "Distributed systems fundamentals",
                    "Data intensive applications reading",
                    "B-tree index deep dive",
                    "System design patterns",
                ],
            },
        ],
    },
    {
        "domain": "Philosophy & Identity",
        "domain_weight": 65,
        "themes": [
            {
                "name": "Stoicism",
                "weight": 60,
                "chain": [
                    "Marcus Aurelius introduction",
                    "Meditations first reading",
                    "Stoic principles for career",
                    "Daily practice implementation",
                ],
            },
        ],
    },
    {
        "domain": "Health & Wellbeing",
        "domain_weight": 25,
        "themes": [
            {
                "name": "Fitness",
                "weight": 22,
                "chain": [
                    "Gym routine design",
                    "Nutrition basics",
                ],
            },
        ],
    },
]

for d in GRAPH:
    add_node(d["domain"], node_type="domain")
    set_weight(d["domain"], d["domain_weight"])
    add_edge(USER, d["domain"])

    for t in d["themes"]:
        add_node(t["name"], node_type="theme")
        set_weight(t["name"], t["weight"])
        add_edge(d["domain"], t["name"])
        add_chain(t["name"], t["chain"], t["weight"])

# ── summary ──────────────────────────────────────────────────────────────────

with get_connection() as conn:
    n_nodes = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
    n_edges = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]

print(f"\n✦ Demo constellation seeded")
print(f"  Nodes: {n_nodes}  Edges: {n_edges}  Domains: 4")
print(f"  ✦ Opening constellation...")

from render import render_graph
html_path = render_graph()
webbrowser.open(f"file://{html_path}")
