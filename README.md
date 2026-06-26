# ✦ Asterism
> Local-first personal knowledge graph with Hebbian TTL decay, rendered as a living constellation.

## What it does

Asterism lets you build a personal knowledge graph by adding nodes (concepts, entities, events) and edges between them. When you query it in natural language, a Claude-powered assistant reasons over the graph and explicitly traverses relevant connections — those edges get strengthened (higher weight) as a result, a form of Hebbian learning: *neurons that fire together, wire together*. Edges and nodes that aren't accessed decay over time via TTL, so the graph naturally forgets stale knowledge and keeps itself focused on what you actually use.

## Stack

- **Python** — all logic
- **SQLite** — local storage for nodes and edges (with weight + TTL)
- **NetworkX** — in-memory graph operations and shortest-path traversal
- **pyvis** — constellation-style HTML graph render
- **Streamlit** — web UI
- **Anthropic Claude** (`claude-sonnet-4-6`) — LLM layer for natural language queries
- **python-dotenv** — `.env` support for API key

## Setup

```bash
# 1. Clone
git clone https://github.com/biditdas18/asterism.git
cd asterism

# 2. Create virtualenv with uv
uv venv .venv
source .venv/bin/activate

# 3. Install dependencies
uv pip install -r requirements.txt

# 4. Set your API key
cp .env.example .env
# Edit .env and replace with your real ANTHROPIC_API_KEY

# 5. Initialize the database
python -c "from db import init_db; init_db()"
```

## Run

**Streamlit app:**
```bash
streamlit run app.py
```

**Decay scheduler** (separate terminal — runs TTL decay every 60s):
```bash
python decay_scheduler.py
```

## Project Structure

| File | Description |
|---|---|
| `schema.sql` | SQLite schema — nodes and edges tables with weight + TTL columns |
| `db.py` | CRUD layer: add/get/delete nodes and edges, decay, strengthen |
| `graph.py` | NetworkX layer: build graph, traverse paths, summarize, run decay |
| `context.py` | Serializes the graph into an LLM system prompt string |
| `llm.py` | Claude API query, TRAVERSAL tag parser, edge strengthening on response |
| `render.py` | pyvis constellation render — weight-based node size/color, dark bg |
| `app.py` | Streamlit UI: sidebar graph editor, chat interface, inline graph view |
| `decay_scheduler.py` | Background process: calls `run_decay()` every 60s with timestamped logs |
| `test_foundation.py` | Tests for db.py and graph.py |
| `test_llm.py` | Tests for context serializer and traversal parser |
| `.env.example` | Template for your API key |

## How the Hebbian loop works

1. You add nodes and edges manually, or they're created implicitly when Claude traverses a new connection.
2. When you ask a question, the graph is serialized and injected into Claude's system prompt.
3. Claude responds and marks which nodes it traversed with `TRAVERSAL: A -> B -> C` tags.
4. Asterism parses those tags and calls `strengthen_edge()` on each pair — weight goes up, TTL resets.
5. Edges and nodes that are never traversed slowly lose weight and eventually decay away.
6. What you think about survives. What you ignore fades.
