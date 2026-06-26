import networkx as nx
from db import (
    init_db, add_node, get_node, delete_node, decay_nodes,
    add_edge, get_edges, delete_edge, decay_edges, strengthen_edge, get_connection
)


def build_graph() -> nx.DiGraph:
    """Load full graph from SQLite into NetworkX."""
    G = nx.DiGraph()

    with get_connection() as conn:
        nodes = conn.execute("SELECT * FROM nodes").fetchall()
        edges = conn.execute("""
            SELECT e.*, n1.label AS source_label, n2.label AS target_label
            FROM edges e
            JOIN nodes n1 ON e.source_id = n1.id
            JOIN nodes n2 ON e.target_id = n2.id
        """).fetchall()

    for n in nodes:
        G.add_node(n["label"], weight=n["weight"], node_type=n["node_type"])

    for e in edges:
        G.add_edge(e["source_label"], e["target_label"], weight=e["weight"])

    return G


def get_neighbors(label: str) -> list[str]:
    """Return all neighbors of a node by label."""
    G = build_graph()
    if label not in G:
        return []
    return list(G.neighbors(label))


def traverse(source_label: str, target_label: str) -> list[str]:
    """
    Find shortest path between two nodes.
    Strengthen all edges along the path (Hebbian: traversal = reinforcement).
    """
    G = build_graph()

    if source_label not in G or target_label not in G:
        return []

    try:
        path = nx.shortest_path(G, source=source_label, target=target_label, weight=None)
    except nx.NetworkXNoPath:
        return []

    # Strengthen each edge in the path
    for i in range(len(path) - 1):
        strengthen_edge(path[i], path[i + 1])

    return path


def graph_summary() -> dict:
    """Return basic stats about the current graph state."""
    G = build_graph()
    return {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "density": round(nx.density(G), 4),
        "node_list": list(G.nodes(data=True)),
        "edge_list": list(G.edges(data=True)),
    }


def run_decay():
    """Trigger TTL decay on both nodes and edges."""
    decay_edges()
    decay_nodes()
