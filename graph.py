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


def record_traversal_session(node_list: list[str]):
    """
    After an LLM query, form shortcuts between co-traversed nodes
    that share a non-traversed bridge node.
    A → B → C where B not traversed → create/strengthen A→C directly.
    """
    if len(node_list) < 2:
        return
    G = build_graph()
    U = G.to_undirected()
    traversed = set(node_list)

    for i, a in enumerate(node_list):
        if a not in U:
            continue
        a_neighbors = set(U.neighbors(a))
        for c in node_list[i + 1:]:
            if c not in U or U.has_edge(a, c):
                continue
            # any common neighbor not traversed this session = valid bridge
            bridging = (a_neighbors & set(U.neighbors(c))) - traversed
            if not bridging:
                continue
            _upsert_shortcut(a, c)
            print(f"✦ Shortcut formed: {a} → {c}")


def _upsert_shortcut(source: str, target: str):
    """Create a shortcut edge at weight 30, or strengthen by 10 if it already exists."""
    sql = """
        INSERT INTO edges (source_id, target_id, weight)
        VALUES (
            (SELECT id FROM nodes WHERE label = ?),
            (SELECT id FROM nodes WHERE label = ?),
            30.0
        )
        ON CONFLICT(source_id, target_id) DO UPDATE SET
            weight = weight + 10,
            last_accessed = CURRENT_TIMESTAMP
    """
    with get_connection() as conn:
        conn.execute(sql, (source, target))


def run_decay():
    """Trigger TTL decay on both nodes and edges."""
    decay_edges()
    decay_nodes()
