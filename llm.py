import re
import anthropic
from config import load_config
from context import serialize_graph
from db import strengthen_edge, add_edge
from extractor import extract_triples

SYSTEM_TEMPLATE = """You are Asterism, a personal knowledge assistant.
You have access to the user's knowledge graph below.
When you answer, explicitly mention which nodes and edges you are traversing in your reasoning.
Format traversals as: TRAVERSAL: NodeA -> NodeB

{graph_context}
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


def _parse_traversals(text: str) -> list[tuple[str, str]]:
    pairs = []
    for line in re.findall(r"TRAVERSAL:\s*(.+?)(?:\n|$)", text):
        nodes = [n.strip() for n in line.split("->")]
        pairs.extend(zip(nodes, nodes[1:]))
    return pairs


def converse(user_msg: str, conversation_history: list) -> dict:
    client = _make_client()
    graph_context = serialize_graph()
    system_prompt = SYSTEM_TEMPLATE.format(graph_context=graph_context)

    messages = conversation_history + [{"role": "user", "content": user_msg}]

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system_prompt,
        messages=messages,
    )
    response_text = message.content[0].text

    traversals = _parse_traversals(response_text)
    for src, tgt in traversals:
        strengthen_edge(src, tgt)

    triples = extract_triples(user_msg, response_text)
    for t in triples:
        try:
            add_edge(t["source"], t["target"])
        except Exception:
            pass

    return {
        "response": response_text,
        "traversals": traversals,
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
