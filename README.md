![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![License](https://img.shields.io/badge/license-MIT-green) ![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)

# ✦ Asterism

**A local-first personal knowledge graph that thinks like a brain and looks like a constellation.**

Every conversation you have with Claude leaves a trace. Asterism maps those traces into a living star map — the more you think about something, the brighter it glows. Stop thinking about it, and it fades into the dark.

## What it looks like

![Asterism Demo](docs/asterism.gif)

![Constellation zoomed out — Bidit as central star](docs/screenshot-zoomed.png)

![Asterism central node — pulsar effect with radiating edges](docs/screenshot-hover.png)

## How it works

- **Hebbian learning** — edges between concepts strengthen each time the LLM traverses them (`weight += 0.2` per traversal). Concepts that aren't revisited accumulate session exposure time; after 3 hours of uninterrupted exposure without traversal they decay and vanish from the graph.
- **You are the central node** — your user node sits at the centre of the constellation at full brightness, always. It never decays.
- **Local SQLite storage** — the entire graph lives in `~/.asterism/asterism.db`. No cloud, no sync, no accounts.
- **LLM context injection** — on every message, the top-N highest-weight nodes are injected into the Claude prompt as context, letting the model answer with awareness of your past thinking. See [Research & Evaluation](#research--evaluation) for a measured, honest account of what this buys you.
- **Triple extraction** — each exchange is processed by a fast extraction model (local Ollama or Anthropic Haiku) that pulls `(entity, relationship, entity)` triples and writes them to the graph.
- **Entity resolution** — new labels are checked against existing nodes (exact/prefix match, then a local embedding fallback) so the extractor's inevitable rewordings strengthen an existing node instead of forking a near-duplicate one.
- **Fact supersession** — when a new edge contradicts an existing one from the same source with the same relationship (e.g. "uses Postgres" → "uses SQLite"), the old edge is flagged superseded: excluded from default context injection, but never deleted, so "what did you used to think" queries still work.

## Quick Start

```bash
git clone https://github.com/biditdas18/asterism
cd asterism
chmod +x setup.sh && ./setup.sh
```

Then:
1. Run `asterism init` — guided setup wizard
2. Export your Claude data: claude.ai → Settings → Export Data → check email → download zip
3. `asterism crawl --source claude --path path/to/conversations.json`
4. Your constellation opens automatically

That's it. Your mind as a constellation.

## Project structure

```
asterism/
├── app.py, cli.py           entry points (Streamlit app, `asterism` CLI)
├── db.py, schema.sql        SQLite storage, entity resolution, supersession
├── llm.py, context.py       context injection into the Claude prompt
├── graph.py                 NetworkX view over the graph, decay-safe queries
├── extractor.py, crawler.py triple extraction, conversation-export ingestion
├── decay_scheduler.py       Hebbian decay / chain-healing / orphan-rescue loop
├── render.py, demo_seed.py  constellation HTML renderer, demo dataset
├── tests/                   pytest suite (`pytest` from repo root)
├── research/                standalone evaluation scripts + results (see below)
└── papers/                  workshop paper draft (tex + PDF)
```

## Development

```bash
pytest                                 # run the test suite (26 tests; 1 needs ANTHROPIC_API_KEY)
pytest -k "not live_query"             # skip that one if you haven't run `asterism init` yet
python research/poc_compare_v2.py      # rerun the quantitative eval (needs API key)
python research/benchmark_latency.py   # rerun the latency benchmark (no API key needed)
```

## Privacy

Your graph never leaves your machine. The only external calls are to the Anthropic API for Claude responses and (optionally) Haiku-powered triple extraction. Entity-resolution embeddings run locally (ONNX, no network calls after a one-time model download). The LLM only sees what you explicitly inject from your local graph — it has no access to the raw database. Delete `~/.asterism/` to get a clean slate. No telemetry, no analytics, no accounts.

## Research & Evaluation

The core architectural claim — that a weighted knowledge graph acts as a *priority index* over otherwise-flat LLM memory, the same way a B-tree indexes an ordered file — is tested, not asserted. Full methodology, raw per-query labels, and the superseded first attempt (kept for the audit trail rather than quietly overwritten) are in [`research/`](research/).

**Does graph-injected retrieval actually help, and where?**

Three conditions were run on the same seeded graph and the same queries: `graph` (weighted, top-N, traversal-aware — current behavior), `flat_list` (every fact, unweighted, unstructured), and `none` (no memory at all). The `graph` vs. `flat_list` gap isolates the value of the *graph structure* from the value of merely *having memory*.

Responses to 12 priority-ranking queries were scored COMMIT / HEDGE by a deterministic keyword+structure classifier — pre-registered and validated to 100% accuracy on an 11-example held-out set (drawn from earlier runs, never from the run being scored) *before* any of the scored calls were made, and not adjusted afterward:

| Condition | COMMIT rate (of 12) |
|---|---|
| `graph` | **7/12** |
| `flat_list` | 4/12 |
| `none` | 0/12 |

**Finding:** the graph's advantage isn't recall — a flat list recalls the same facts fine. It's *decisiveness under ambiguity*. Without a salience signal, the flat-list condition sees every fact but hedges and hands the ranking decision back to the user; the weighted condition commits to a specific, weight-justified answer. On purely descriptive/recall queries the two conditions are comparable, which is why the metric is scoped to priority queries only — COMMIT vs. HEDGE isn't a meaningful axis for a query that doesn't require picking anything.

**Two supporting components, measured rather than assumed:**
- **Entity resolution has a known ceiling.** A local embedding model (bge-small-en, ONNX/fastembed) cleanly merges reworded or reordered phrasings of the same concept (0.92–0.98 cosine similarity) but cannot reliably separate genuine synonym substitutions ("LLM" vs. "Large Language Models") from merely-related concepts at any single threshold (0.58–0.80, indistinguishable from noise) — so the merge threshold is deliberately conservative, favoring missed merges over false ones.
- **Retrieval latency scales approximately linearly** with graph size and stays well under the cost of an API round-trip: mean latency at 10,000 synthetic nodes has measured in the low tens of milliseconds across reruns (21–35ms depending on machine load — see [`research/results/benchmark_results.md`](research/results/benchmark_results.md) for the latest run). Not the conversational-UX bottleneck at any scale tested.

See [`research/README.md`](research/README.md) for how to reproduce every number above, [`RESEARCH.md`](RESEARCH.md) for the full list of contributions, and [`papers/asterism.tex`](papers/asterism.tex) for the workshop paper.

## Built with

| Layer | Tech |
|---|---|
| Storage | SQLite (`~/.asterism/asterism.db`) |
| Graph | NetworkX |
| Entity resolution | fastembed (ONNX, local) — `BAAI/bge-small-en-v1.5` |
| Visualization | Vanilla JS force simulation (zero dependencies) |
| LLM | Anthropic SDK — `claude-sonnet-4-6` |
| Extraction | Ollama `llama3.2:3b` (local) or Anthropic Haiku (cloud) |
| UI | Streamlit |
| CLI | Click |

## Author

**Bidit** — [github.com/biditdas18](https://github.com/biditdas18)
