from graph import graph_summary

def serialize_graph(max_nodes: int = 50) -> str:
    summary = graph_summary()
    nodes = summary["node_list"][:max_nodes]
    edges = summary["edge_list"]

    node_lines = []
    for label, data in nodes:
        weight = round(data.get("weight", 1.0), 2)
        ntype = data.get("node_type", "concept")
        node_lines.append(f"  - [{ntype}] {label} (strength: {weight})")

    edge_lines = []
    for src, tgt, data in edges:
        weight = round(data.get("weight", 1.0), 2)
        edge_lines.append(f"  - {src} --> {tgt} (weight: {weight})")

    prompt = (
        "## Knowledge Graph State\n\n"
        "### Nodes\n" + "\n".join(node_lines) + "\n\n"
        "### Edges\n" + "\n".join(edge_lines) + "\n\n"
        "Use this graph as context. When answering, "
        "traverse relevant nodes and edges explicitly."
    )
    return prompt
