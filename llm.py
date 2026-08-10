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

FLAT_LIST_SYSTEM_TEMPLATE = """\
You are Asterism, a personal knowledge assistant for {user}.

Here are topics {user} has previously discussed, in no particular order:

{node_lines}

Answer using this list if relevant.
"""

FLAT_SYSTEM_TEMPLATE = """\
You are Asterism, a personal knowledge assistant for {user}.

Answer using only the current conversation. You have no access to {user}'s \
knowledge graph or prior history.
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


def _is_openai_model(model: str) -> bool:
    return model.startswith(("gpt", "o1", "o3", "o4"))


def _make_openai_client():
    import os
    import openai
    from dotenv import load_dotenv
    load_dotenv()
    return openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))


def _load_graph_data() -> tuple[list[dict], dict[str, list[str]]]:
    """
    Returns:
      nodes: list of {label, weight, node_type} sorted by weight desc
      parents: label → list[parent_label] (direct DB parents, highest-weight first)

    Excludes superseded facts from context injection: a node is left out
    only if every fact-edge (relationship != '') pointing at it has been
    superseded — nodes with no fact-edges (structural/hierarchy nodes) or
    with at least one still-current fact-edge are unaffected. Edges used
    for the parent map exclude superseded edges outright, same reasoning
    as db.add_edge's relationship-conflict handling.
    """
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT label, weight, node_type FROM nodes n
            WHERE NOT EXISTS (
                SELECT 1 FROM edges e WHERE e.target_id = n.id AND e.relationship != ''
            )
            OR EXISTS (
                SELECT 1 FROM edges e
                WHERE e.target_id = n.id AND e.relationship != '' AND e.superseded_by IS NULL
            )
            ORDER BY weight DESC
        """).fetchall()
        edges = conn.execute("""
            SELECT n_src.label AS src, n_tgt.label AS tgt, e.weight AS w
            FROM edges e
            JOIN nodes n_src ON n_src.id = e.source_id
            JOIN nodes n_tgt ON n_tgt.id = e.target_id
            WHERE e.superseded_by IS NULL
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


def converse(user_msg: str, conversation_history: list, inject_mode: str = "graph",
             model: str = "claude-sonnet-4-6") -> dict:
    """
    inject_mode:
      "graph"     - top-N weighted graph nodes injected, traversal-aware (default, prior behavior)
      "flat_list" - all node labels injected as an unweighted, unstructured list
      "none"      - no graph context injected at all

    model: the ASSISTANT model only (the model that answers user_msg). Model
    strings starting with gpt/o1/o3/o4 route to OpenAI's chat.completions API;
    everything else (default) routes to the existing Anthropic path unchanged.
    extract_triples()'s own model choice (Haiku/local Ollama, for graph
    maintenance) is independent of this and is not affected.
    """
    if inject_mode not in ("graph", "flat_list", "none"):
        raise ValueError(f"invalid inject_mode: {inject_mode!r}")

    config = load_config()
    user_name = config.get("user_name", "you")

    context_nodes: list[dict] = []
    context_labels: list[str] = []
    parent_map: dict[str, list[str]] = {}

    if inject_mode == "graph":
        nodes, parent_map = _load_graph_data()

        # top 30 nodes for context injection, sorted by weight
        context_nodes = nodes[:30]
        context_labels = [n["label"] for n in context_nodes]

        node_lines = "\n".join(
            f"- {n['label']} (weight: {n['weight']:.0f}, type: {n['node_type']})"
            for n in context_nodes
        )
        system_prompt = SYSTEM_TEMPLATE.format(user=user_name, node_lines=node_lines)
    elif inject_mode == "flat_list":
        nodes, _ = _load_graph_data()
        context_labels = sorted(n["label"] for n in nodes)
        node_lines = "\n".join(f"- {label}" for label in context_labels)
        system_prompt = FLAT_LIST_SYSTEM_TEMPLATE.format(user=user_name, node_lines=node_lines)
    else:  # "none"
        system_prompt = FLAT_SYSTEM_TEMPLATE.format(user=user_name)

    messages = conversation_history + [{"role": "user", "content": user_msg}]

    if _is_openai_model(model):
        client = _make_openai_client()
        openai_messages = [{"role": "system", "content": system_prompt}] + messages
        try:
            response = client.chat.completions.create(
                model=model, max_completion_tokens=1024, messages=openai_messages,
            )
        except Exception:
            response = client.chat.completions.create(
                model=model, max_tokens=1024, messages=openai_messages,
            )
        response_text = response.choices[0].message.content
        tokens_used = response.usage.prompt_tokens + response.usage.completion_tokens
    else:
        client = _make_client()
        message = client.messages.create(
            model=model,
            max_tokens=1024,
            system=system_prompt,
            messages=messages,
        )
        response_text = message.content[0].text
        tokens_used = message.usage.input_tokens + message.usage.output_tokens

    traversals = []
    triples = []
    if inject_mode == "graph":
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
                add_edge(t["source"], t["target"], relationship=t.get("relationship", ""))
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
        "tokens_used": tokens_used,
    }


# backward-compat shim for tests
def query(user_input: str, model: str = "claude-sonnet-4-6") -> dict:
    result = converse(user_input, [])
    return {
        "response": result["response"],
        "traversals": result["traversals"],
        "tokens_used": result["tokens_used"],
    }
