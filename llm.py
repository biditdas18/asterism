import re
import anthropic
from config import load_config
from db import strengthen_edge, add_edge, get_connection
from extractor import extract_triples

DIVIDER = "─" * 48

SYSTEM_TEMPLATE = """\
You are Asterism, a personal knowledge assistant for {user}.

You have access to {user}'s personal knowledge graph. The following nodes \
represent their current priorities and thought patterns, weighted by recency \
and usage frequency:

ACTIVE NODES (highest weight first):
{node_lines}

When answering, reference these nodes naturally. Prioritize information from \
high-weight nodes. Note when you are drawing on specific parts of their graph.
When you traverse a concept explicitly, format it as: TRAVERSAL: NodeA -> NodeB
"""


def _make_client() -> anthropic.Anthropic:
    config = load_config()
    key = config.get("anthropic_api_key") or ""
    if not key:
        from dotenv import load_dotenv
        import os
        load_dotenv()
        key = os.environ.get("ANTHROPIC_API_KEY", "")
    return anthropic.Anthropic(api_key=key)


def _load_graph_data() -> tuple[list[dict], dict[str, list[str]]]:
    """
    Returns:
      nodes: list of {label, weight, node_type} sorted by weight desc
      parents: label → list[parent_label] (direct DB parents, highest-weight first)
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT label, weight, node_type FROM nodes ORDER BY weight DESC"
        ).fetchall()
        edges = conn.execute("""
            SELECT n_src.label AS src, n_tgt.label AS tgt, e.weight AS w
            FROM edges e
            JOIN nodes n_src ON n_src.id = e.source_id
            JOIN nodes n_tgt ON n_tgt.id = e.target_id
        """).fetchall()

    nodes = [{"label": r["label"], "weight": r["weight"], "node_type": r["node_type"]}
             for r in rows]

    # build child → parents mapping (edge goes parent→child in our schema)
    parents: dict[str, list[tuple[float, str]]] = {}
    for e in edges:
        parents.setdefault(e["tgt"], []).append((e["w"], e["src"]))
    # sort each parent list by weight desc, keep only labels
    parent_map = {k: [lbl for _, lbl in sorted(v, reverse=True)]
                  for k, v in parents.items()}

    return nodes, parent_map


def _ancestor_path(label: str, parent_map: dict[str, list[str]]) -> str:
    """Walk up to root (user node) and return domain → theme → concept string."""
    path = [label]
    seen = {label}
    cur = label
    for _ in range(5):
        plist = parent_map.get(cur, [])
        if not plist:
            break
        parent = plist[0]
        if parent in seen:
            break
        seen.add(parent)
        path.insert(0, parent)
        cur = parent
    # drop the user node from display (always first if reachable)
    if len(path) > 1:
        path = path[1:]  # skip user node label
    return " → ".join(path)


def _parse_traversals(text: str) -> list[tuple[str, str]]:
    pairs = []
    for line in re.findall(r"TRAVERSAL:\s*(.+?)(?:\n|$)", text):
        nodes = [n.strip() for n in line.split("->")]
        pairs.extend(zip(nodes, nodes[1:]))
    return pairs


def converse(user_msg: str, conversation_history: list) -> dict:
    config = load_config()
    user_name = config.get("user_name", "you")
    client = _make_client()

    nodes, parent_map = _load_graph_data()

    # top 30 nodes for context injection, sorted by weight
    context_nodes = nodes[:30]
    context_labels = [n["label"] for n in context_nodes]

    node_lines = "\n".join(
        f"- {n['label']} (weight: {n['weight']:.0f}, type: {n['node_type']})"
        for n in context_nodes
    )
    system_prompt = SYSTEM_TEMPLATE.format(user=user_name, node_lines=node_lines)

    messages = conversation_history + [{"role": "user", "content": user_msg}]

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system_prompt,
        messages=messages,
    )
    response_text = message.content[0].text

    # strengthen edges for nodes Claude explicitly traversed
    traversals = _parse_traversals(response_text)
    for src, tgt in traversals:
        strengthen_edge(src, tgt)

    # record full traversal session to form shortcuts
    try:
        from graph import record_traversal_session
        all_traversed = list(dict.fromkeys(
            [n for pair in traversals for n in pair] + context_labels[:10]
        ))
        record_traversal_session(all_traversed)
    except Exception:
        pass

    # extract triples and add to graph
    triples = extract_triples(user_msg, response_text)
    for t in triples:
        try:
            add_edge(t["source"], t["target"])
        except Exception:
            pass

    # build traversal display lines
    traversal_display = []
    for n in context_nodes[:8]:  # show top 8 in traversal block
        path = _ancestor_path(n["label"], parent_map)
        traversal_display.append(f"  {path}  [weight: {n['weight']:.0f}]")

    return {
        "response": response_text,
        "traversals": traversals,
        "traversal_display": traversal_display,
        "traversed_nodes": context_labels,
        "triples_extracted": triples,
        "tokens_used": message.usage.input_tokens + message.usage.output_tokens,
    }


# backward-compat shim for tests
def query(user_input: str, model: str = "claude-sonnet-4-6") -> dict:
    result = converse(user_input, [])
    return {
        "response": result["response"],
        "traversals": result["traversals"],
        "tokens_used": result["tokens_used"],
    }
