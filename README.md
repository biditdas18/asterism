# ✦ Asterism
> An X-ray of your brain.

Every conversation you have with Claude leaves a trace. Asterism maps those traces into a living constellation — the more you think about something, the brighter it glows. Stop thinking about it, and it fades.

![constellation](docs/constellation.png)

## Install

```bash
pip install asterism-ai
```

## Usage

```bash
asterism init   # first-time setup: API key, extractor choice, DB init
asterism chat   # launch the chat interface
asterism view   # open the constellation in your browser
```

## How it works

Every message you send is processed by an extraction model that pulls out knowledge graph triples — `(entity, relationship, entity)` — and writes them to a local SQLite database. When you revisit a topic, the edges connecting those concepts get stronger (higher weight) and glow brighter. When you stop thinking about something, a background decay process slowly erodes its weight until it fades from the graph entirely.

This is Hebbian learning applied to memory: **neurons that fire together, wire together. Neurons that fire apart, drift apart.**

The result is a constellation that is literally a map of your mind — shaped by what you think about, not what you were told to remember.

## Privacy

**Your graph never leaves your machine.** The only external call is to the Anthropic API for Claude responses and (optionally) Haiku-powered extraction. Your knowledge graph lives in `~/.asterism/asterism.db`. No telemetry, no cloud sync, no accounts.

## Stack

| Layer | Tech |
|---|---|
| Storage | SQLite (local, `~/.asterism/`) |
| Graph | NetworkX |
| Visualization | Vanilla JS force simulation (zero dependencies) |
| LLM | Anthropic Claude (`claude-sonnet-4-6`) |
| Extraction | Ollama `llama3.2:3b` (local) or Anthropic Haiku (cloud) |
| UI | Streamlit |
| CLI | Click |

## Contributing

```bash
git clone https://github.com/biditdas18/asterism.git
cd asterism
uv venv .venv && source .venv/bin/activate
uv pip install -r requirements.txt
cp .env.example .env  # add your ANTHROPIC_API_KEY
python -m pytest test_foundation.py test_llm.py -v
```

PRs welcome. Keep it local-first.
