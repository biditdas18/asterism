import os
import re
import anthropic
from context import serialize_graph
from db import strengthen_edge, add_node, add_edge, get_connection

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_TEMPLATE = """
You are Asterism, a personal knowledge assistant.
You have access to the user's knowledge graph below.
When you answer, explicitly mention which nodes and edges
you are traversing in your reasoning.
Format traversals as: TRAVERSAL: NodeA -> NodeB

{graph_context}
"""

def query(user_input: str, model: str = "claude-sonnet-4-6") -> dict:
    graph_context = serialize_graph()
    system_prompt = SYSTEM_TEMPLATE.format(graph_context=graph_context)
    message = client.messages.create(
        model=model,
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_input}]
    )
    response_text = message.content[0].text
    traversals = _parse_traversals(response_text)
    for src, tgt in traversals:
        strengthen_edge(src, tgt)
    return {
        "response": response_text,
        "traversals": traversals,
        "tokens_used": message.usage.input_tokens + message.usage.output_tokens
    }

def _parse_traversals(text: str) -> list[tuple[str, str]]:
    pattern = r"TRAVERSAL:\s*(.+?)\s*->\s*(.+?)(?:\n|$)"
    matches = re.findall(pattern, text)
    return [(m[0].strip(), m[1].strip()) for m in matches]
