import os
import pytest
from db import (
    init_db, add_node, get_node, delete_node, decay_nodes,
    add_edge, get_edges, delete_edge, decay_edges, strengthen_edge, get_connection
)
from graph import build_graph, get_neighbors, traverse, graph_summary, run_decay

# Use a test database
os.environ["TESTING"] = "1"
import db
db.DB_PATH = os.path.join(os.path.dirname(__file__), "test_asterism.db")


def setup_function():
    """Fresh DB before each test."""
    if os.path.exists(db.DB_PATH):
        os.remove(db.DB_PATH)
    init_db()


def teardown_function():
    """Clean up after each test."""
    if os.path.exists(db.DB_PATH):
        os.remove(db.DB_PATH)


# --- NODE TESTS ---

def test_add_and_get_node():
    node_id = add_node("Python", node_type="concept")
    assert isinstance(node_id, int)
    node = get_node("Python")
    assert node is not None
    assert node["label"] == "Python"
    assert node["node_type"] == "concept"
    assert node["weight"] == 1.0


def test_add_node_conflict_increases_weight():
    add_node("Python")
    add_node("Python")  # second insert should bump weight
    node = get_node("Python")
    assert node["weight"] > 1.0


def test_add_node_merges_near_duplicate_label():
    add_node("Marcus Aurelius", node_type="entity")
    add_node("Marcus Aurelius introduction")  # verbose extractor variant of the same entity
    node = get_node("Marcus Aurelius")
    assert node["weight"] > 1.0  # existing node strengthened...
    assert get_node("Marcus Aurelius introduction") is None  # ...not forked into a new one


def test_add_node_does_not_merge_unrelated_labels():
    add_node("Gym routine design")
    add_node("Package structure design")  # shares a suffix, different entity
    assert get_node("Gym routine design") is not None
    assert get_node("Package structure design") is not None


def test_add_node_merges_reworded_synonym_via_embedding():
    """No shared prefix, so this only merges via the embedding fallback."""
    add_node("Database indexing strategy", node_type="concept")
    add_node("Strategy for indexing databases")  # same concept, reworded
    node = get_node("Database indexing strategy")
    assert node["weight"] > 1.0
    assert get_node("Strategy for indexing databases") is None


def test_add_node_does_not_merge_close_but_distinct_concepts_via_embedding():
    """Close but wrong: shares a word and a topic area, but is a genuinely
    different entity - the embedding fallback must not merge these."""
    add_node("Philosophy & Identity", node_type="domain")
    add_node("Research Identity", node_type="theme")
    assert get_node("Philosophy & Identity") is not None
    assert get_node("Research Identity") is not None


def test_delete_node():
    add_node("Rust")
    result = delete_node("Rust")
    assert result is True
    assert get_node("Rust") is None


def test_delete_nonexistent_node():
    result = delete_node("Ghost")
    assert result is False


# --- EDGE TESTS ---

def test_add_and_get_edge():
    add_edge("Python", "Machine Learning")
    edges = get_edges("Python")
    assert len(edges) > 0
    labels = [(e["source_label"], e["target_label"]) for e in edges]
    assert ("Python", "Machine Learning") in labels


def test_add_edge_conflict_increases_weight():
    add_edge("Python", "Machine Learning")
    add_edge("Python", "Machine Learning")
    edges = get_edges("Python")
    edge = edges[0]
    assert edge["weight"] > 1.0


def test_delete_edge():
    add_edge("Python", "Machine Learning")
    result = delete_edge("Python", "Machine Learning")
    assert result is True
    edges = get_edges("Python")
    assert len(edges) == 0


def test_strengthen_edge():
    add_edge("Python", "Machine Learning")
    strengthen_edge("Python", "Machine Learning", delta=0.5)
    edges = get_edges("Python")
    assert edges[0]["weight"] >= 1.5


# --- GRAPH TESTS ---

def test_build_graph():
    add_edge("Bidit", "Python")
    add_edge("Python", "Machine Learning")
    G = build_graph()
    assert G.number_of_nodes() >= 2
    assert G.number_of_edges() >= 1


def test_get_neighbors():
    add_edge("Bidit", "Python")
    add_edge("Bidit", "SQLite")
    neighbors = get_neighbors("Bidit")
    assert "Python" in neighbors
    assert "SQLite" in neighbors


def test_traverse_strengthens_edges():
    add_edge("Bidit", "Python")
    add_edge("Python", "Machine Learning")
    path = traverse("Bidit", "Machine Learning")
    assert path == ["Bidit", "Python", "Machine Learning"]
    edges = get_edges("Python")
    for e in edges:
        if e["source_label"] == "Python" and e["target_label"] == "Machine Learning":
            assert e["weight"] > 1.0


def test_graph_summary():
    add_edge("Bidit", "Python")
    summary = graph_summary()
    assert summary["nodes"] >= 2
    assert summary["edges"] >= 1
    assert "density" in summary


def test_run_decay_does_not_crash():
    add_edge("Bidit", "Python")
    run_decay()  # should not raise


# --- TEMPORAL / SUPERSESSION TESTS ---

def test_add_edge_conflict_marks_old_edge_superseded():
    add_edge("Alex", "Postgres", relationship="uses")
    add_edge("Alex", "SQLite", relationship="uses")  # same source+relationship, different target

    postgres_edge = next(e for e in get_edges("Postgres") if e["source_label"] == "Alex")
    sqlite_edge = next(e for e in get_edges("SQLite") if e["source_label"] == "Alex")

    assert postgres_edge["superseded_by"] == sqlite_edge["id"]
    assert sqlite_edge["superseded_by"] is None

    # unrelated relationship on the same source must not be caught up in this
    add_edge("Alex", "Databases", relationship="studies")
    studies_edge = next(e for e in get_edges("Databases") if e["source_label"] == "Alex")
    assert studies_edge["superseded_by"] is None


def test_superseded_edge_excluded_from_graph_summary_by_default():
    add_edge("Alex", "Postgres", relationship="uses")
    add_edge("Alex", "SQLite", relationship="uses")

    default_pairs = [(s, t) for s, t, _ in graph_summary()["edge_list"]]
    assert ("Alex", "SQLite") in default_pairs
    assert ("Alex", "Postgres") not in default_pairs

    # not deleted - still there if explicitly asked for history
    history_pairs = [(s, t) for s, t, _ in graph_summary(include_superseded=True)["edge_list"]]
    assert ("Alex", "Postgres") in history_pairs
    assert get_node("Postgres") is not None


def test_superseded_edge_removal_does_not_orphan_node_with_other_paths():
    add_node("Alex", node_type="user")
    add_edge("Alex", "Postgres", relationship="uses")
    add_edge("Alex", "SQLite", relationship="uses")   # supersedes Postgres fact-edge, ttl -> 0
    add_edge("Alex", "Backend Learning")               # unrelated structural edge
    add_edge("Backend Learning", "Postgres")           # Postgres also reachable via this path

    decay_edges()  # sweeps the now-eligible-for-immediate-pruning superseded edge

    postgres_edges = get_edges("Postgres")
    assert not any(e["relationship"] == "uses" for e in postgres_edges)  # superseded edge is gone
    assert get_node("Postgres") is not None  # node itself untouched

    from decay_scheduler import _rescue_orphans
    _rescue_orphans()  # must not crash, and must not treat Postgres as an orphan

    rescue_edges = [e for e in get_edges("Postgres") if e["weight"] == 20.0]
    assert rescue_edges == []  # no rescue edge created - it was never orphaned
