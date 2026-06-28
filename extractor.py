import json
import re
import requests
import anthropic
from config import load_config

PROMPT_TEMPLATE = """Extract knowledge graph triples from this conversation exchange.
Return ONLY a JSON array. No explanation. No markdown. Raw JSON only.
Format: [{{"source": "entity", "relationship": "verb", "target": "entity"}}]
Rules:
- Entities are nouns (people, tools, concepts, places, projects)
- Relationships are active verbs (knows, uses, builds, studies, works_at)
- Extract 3-8 triples maximum
- Only extract what is clearly stated, never infer
- If nothing extractable, return []

Conversation:
User: {user_msg}
Assistant: {assistant_msg}
"""


def _parse_json(text: str) -> list[dict]:
    text = text.strip()
    # strip markdown code fences if present
    match = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    if match:
        text = match.group(1).strip()
    return json.loads(text)


def _extract_local(prompt: str, config: dict) -> list[dict]:
    model = config.get("ollama_model", "llama3.2:3b")
    resp = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=30,
    )
    resp.raise_for_status()
    return _parse_json(resp.json()["response"])


def _extract_haiku(prompt: str, config: dict) -> list[dict]:
    client = anthropic.Anthropic(api_key=config["anthropic_api_key"])
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_json(message.content[0].text)


def extract_triples(user_msg: str, assistant_msg: str) -> list[dict]:
    config = load_config()
    prompt = PROMPT_TEMPLATE.format(user_msg=user_msg, assistant_msg=assistant_msg)
    try:
        if config.get("extractor_mode") == "haiku":
            return _extract_haiku(prompt, config)
        return _extract_local(prompt, config)
    except Exception:
        return []
