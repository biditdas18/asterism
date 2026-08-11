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

# Phase 2 (instruction vs. structure isolation). Same node_lines construction
# as their unprimed counterparts (flat_list_prioritized uses flat_list's
# unweighted/unordered labels; graph_neutral uses graph's weighted top-30) -
# only the surrounding instruction differs, by design.

FLAT_LIST_PRIORITIZED_SYSTEM_TEMPLATE = """\
You are Asterism, a personal knowledge assistant for {user}.

Here are topics {user} has previously discussed, in no particular order:

{node_lines}

When answering, reference these topics naturally. Prioritize information from \
these topics. Note when you are drawing on specific parts of this list.
"""

GRAPH_NEUTRAL_SYSTEM_TEMPLATE = """\
You are Asterism, a personal knowledge assistant for {user}.

You have access to {user}'s personal knowledge graph. The following nodes \
represent their current priorities and thought patterns, weighted by recency \
and usage frequency:

ACTIVE NODES (highest weight first):
{node_lines}

Answer using this graph if relevant.
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
             model: str = "claude-sonnet-4-6", temperature: float = 1.0) -> dict:
    """
    inject_mode:
      "graph"                - top-N weighted graph nodes injected, traversal-aware (default, prior behavior)
      "flat_list"             - all node labels injected as an unweighted, unstructured list
      "none"                  - no graph context injected at all
      "flat_list_prioritized" - same unweighted/unordered labels as flat_list, but the
                                 prompt carries the same prioritize/commit instruction
                                 graph uses (no weights, no traversal directive) -
                                 isolates the INSTRUCTION from the structure.
      "graph_neutral"         - same weighted top-N node selection as graph, but the
                                 prompt strips the prioritize/commit instruction and the
                                 traversal directive, presenting the structure neutrally -
                                 isolates the STRUCTURE from the instruction.

    model: the ASSISTANT model only (the model that answers user_msg). Model
    strings starting with gpt/o1/o3/o4 route to OpenAI's chat.completions API;
    everything else (default) routes to the existing Anthropic path unchanged.
    extract_triples()'s own model choice (Haiku/local Ollama, for graph
    maintenance) is independent of this and is not affected.

    temperature: sent explicitly on both backends (default 1.0, pinned).
    If a model rejects the param, this raises rather than silently retrying
    without it - see the two backend blocks below.
    """
    valid_modes = ("graph", "flat_list", "none", "flat_list_prioritized", "graph_neutral")
    if inject_mode not in valid_modes:
        raise ValueError(f"invalid inject_mode: {inject_mode!r}")

    config = load_config()
    user_name = config.get("user_name", "you")

    context_nodes: list[dict] = []
    context_labels: list[str] = []
    parent_map: dict[str, list[str]] = {}

    if inject_mode in ("graph", "graph_neutral"):
        nodes, parent_map = _load_graph_data()

        # top 30 nodes for context injection, sorted by weight
        context_nodes = nodes[:30]
        context_labels = [n["label"] for n in context_nodes]

        node_lines = "\n".join(
            f"- {n['label']} (weight: {n['weight']:.0f}, type: {n['node_type']})"
            for n in context_nodes
        )
        template = SYSTEM_TEMPLATE if inject_mode == "graph" else GRAPH_NEUTRAL_SYSTEM_TEMPLATE
        system_prompt = template.format(user=user_name, node_lines=node_lines)
    elif inject_mode in ("flat_list", "flat_list_prioritized"):
        nodes, _ = _load_graph_data()
        context_labels = sorted(n["label"] for n in nodes)
        node_lines = "\n".join(f"- {label}" for label in context_labels)
        template = FLAT_LIST_SYSTEM_TEMPLATE if inject_mode == "flat_list" else FLAT_LIST_PRIORITIZED_SYSTEM_TEMPLATE
        system_prompt = template.format(user=user_name, node_lines=node_lines)
    else:  # "none"
        system_prompt = FLAT_SYSTEM_TEMPLATE.format(user=user_name)

    messages = conversation_history + [{"role": "user", "content": user_msg}]

    # Generous ceilings - budgets, not targets. OpenAI reasoning models draw
    # hidden reasoning tokens from the same max_completion_tokens pool as
    # visible output, so they need much more headroom than a plain chat
    # model; 1024 was found (empirically, via a live audit) to silently
    # truncate ~8% of gpt-5.5 responses to nothing. Anthropic's audit found
    # occasional near-ceiling/truncated responses from opus's longer
    # answers at 1024, so it's raised too, well above the ~1030-token max
    # observed in that audit.
    OPENAI_MAX_COMPLETION_TOKENS = 8192
    ANTHROPIC_MAX_TOKENS = 4096

    if _is_openai_model(model):
        client = _make_openai_client()
        openai_messages = [{"role": "system", "content": system_prompt}] + messages
        try:
            response = client.chat.completions.create(
                model=model, max_completion_tokens=OPENAI_MAX_COMPLETION_TOKENS,
                temperature=temperature, messages=openai_messages,
            )
        except Exception as e1:
            if "temperature" in str(e1).lower():
                raise RuntimeError(
                    f"Model {model!r} rejected temperature={temperature} on the OpenAI "
                    f"path (max_completion_tokens attempt) - not falling back silently. "
                    f"Original error: {e1}"
                ) from e1
            try:
                response = client.chat.completions.create(
                    model=model, max_tokens=OPENAI_MAX_COMPLETION_TOKENS,
                    temperature=temperature, messages=openai_messages,
                )
            except Exception as e2:
                if "temperature" in str(e2).lower():
                    raise RuntimeError(
                        f"Model {model!r} rejected temperature={temperature} on the "
                        f"OpenAI path (max_tokens fallback attempt) - not falling back "
                        f"silently. Original error: {e2}"
                    ) from e2
                raise
        response_text = response.choices[0].message.content
        tokens_used = response.usage.prompt_tokens + response.usage.completion_tokens
        finish_signal = response.choices[0].finish_reason
        truncated = finish_signal == "length"
    else:
        client = _make_client()
        try:
            message = client.messages.create(
                model=model,
                max_tokens=ANTHROPIC_MAX_TOKENS,
                temperature=temperature,
                system=system_prompt,
                messages=messages,
            )
        except Exception as e:
            if "temperature" in str(e).lower():
                raise RuntimeError(
                    f"Model {model!r} rejected temperature={temperature} on the "
                    f"Anthropic path - not falling back silently. Original error: {e}"
                ) from e
            raise
        response_text = message.content[0].text
        tokens_used = message.usage.input_tokens + message.usage.output_tokens
        finish_signal = message.stop_reason
        truncated = finish_signal == "max_tokens"

    # Universal fail-fast guard: no truncated or empty response may ever be
    # silently scored, for any model on any backend. A truncated/empty
    # response would otherwise flow into classify_commit_or_hedge() as an
    # apparent HEDGE (nothing to match COMMIT patterns against), silently
    # corrupting the eval rather than erroring - this stops that outright.
    if truncated or not response_text or not response_text.strip():
        raise RuntimeError(
            f"Model {model!r} returned a truncated or empty response for "
            f"inject_mode={inject_mode!r} (finish/stop reason={finish_signal!r}, "
            f"content_len={len(response_text or '')}, tokens_used={tokens_used}). "
            f"Refusing to score this - raise the token budget or investigate, do "
            f"not silently continue."
        )

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
