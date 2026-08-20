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
- **LLM context injection** — on every message, the top-N highest-weight nodes are injected into the model's prompt as context, letting it answer with awareness of your past thinking. See [Research & Evaluation](#research--evaluation) for a measured, honest account of what this buys you.
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
├── llm.py, context.py       context injection + multi-backend assistant calls
├── graph.py                 NetworkX view over the graph, decay-safe queries
├── extractor.py, crawler.py triple extraction, conversation-export ingestion
├── decay_scheduler.py       Hebbian decay / chain-healing / orphan-rescue loop
├── render.py, demo_seed.py  constellation HTML renderer, demo dataset
├── tests/                   pytest suite (`pytest` from repo root)
├── research/                evaluation scripts, scorer, and results (see below)
└── papers/                  paper draft (tex + PDF)
```

## Development

```bash
pytest                                 # run the test suite (26 tests; 1 needs ANTHROPIC_API_KEY)
pytest -k "not live_query"             # skip that one if you haven't run `asterism init` yet
python research/benchmark_latency.py   # rerun the latency benchmark (no API key needed)
```

See [Reproducing the evaluation](#reproducing-the-evaluation) below for the full multi-model campaign.

## Privacy

Your graph never leaves your machine. External calls happen only when you choose to: to the Anthropic API for Claude responses, (optionally) Haiku-powered triple extraction, and — only if you run the research evaluation against those models — the OpenAI/Gemini/Groq APIs. Entity-resolution embeddings run locally (ONNX, no network calls after a one-time model download). The LLM only sees what you explicitly inject from your local graph — it has no access to the raw database. Delete `~/.asterism/` to get a clean slate. No telemetry, no analytics, no accounts.

## Research & Evaluation

The core architectural claim — that a weighted knowledge graph acts as a *priority index* over otherwise-flat LLM memory, the same way a B-tree indexes an ordered file — is tested, not asserted, across multiple models, multiple vendors, two independent seed-graph personas, and 100 priority-ranking queries per graph. Full methodology, every prior (superseded) attempt kept rather than overwritten, and every raw result are in [`research/`](research/).

### The finding

A weighted knowledge graph, injected as context with a prioritization instruction, increases **decisive, more-accurate commitment** over flat, unweighted memory — replicated across **5 models spanning 4 vendors** (Anthropic, OpenAI, DeepSeek, Moonshot), **2 independently-designed seed graphs**, and **100 priority-ranking queries per graph** (24,500 scored responses). The benefit is driven by graph **structure itself**, not the instruction riding along with it: a structure-only condition (`graph_neutral`, weighted context with the prioritize/commit instruction stripped out) reproduces most of the gain in **8 of the 10 model×graph cells measured** — a broader, more model-general result than an earlier 12-query pilot suggested, which had looked Claude-specific rather than structural.

**Stated without spin:** absolute priority-routing accuracy stays modest even where the effect is strongest — the best model tops out around 40% correct, most sit well below that. Decisive is not the same claim as reliably correct, and this eval reports both.

### Five conditions, isolating structure from instruction

An earlier three-condition version of this eval (`graph` / `flat_list` / `none`) showed a gap between `graph` and `flat_list`, but couldn't tell whether that gap came from the *weighted structure* or from an explicit "prioritize and commit" instruction that only the `graph` prompt happened to carry. Two more conditions isolate the two:

| Condition | Structure (weighted, ranked) | Instruction (prioritize/commit) |
|---|---|---|
| `graph` | yes | yes |
| `graph_neutral` | yes | no |
| `flat_list_prioritized` | no | yes |
| `flat_list` | no | no |
| `none` | no context at all | — |

`graph_neutral` vs. `flat_list` isolates structure alone. `flat_list_prioritized` vs. `flat_list` isolates the instruction alone. `graph` vs. `flat_list_prioritized` asks whether structure adds anything on top of an instruction both already share.

### The N=100 scale-up: 5 models, 2 graphs, 100 queries, 5 runs

An initial 12-query pilot (below) suggested the structural effect might be specific to Claude models. A second seed graph (a different persona, a different domain mix, a deliberately closer top-priority race) and a 100-query-per-graph scale-up across a 5-model, 4-vendor panel were run to test that directly. Query set generation, ground truth, and near-tie exclusion are fully deterministic and reviewed before any live call — see [Correctness methodology](#correctness-methodology-commit--correct) below.

**Commit rate by condition** (mean COMMIT count out of 100 queries, over 5 runs):

| Model | Graph | `none` | `flat_list` | `flat_list_prioritized` | `graph` | `graph_neutral` |
|---|---|---|---|---|---|---|
| `claude-sonnet-4-6` | G1 | 0.8 | 26.0 | 32.4 | 47.8 | 45.4 |
| `claude-sonnet-4-6` | G2 | 0.2 | 10.8 | 32.2 | 49.6 | 31.0 |
| `claude-opus-4-8` | G1 | 1.0 | 13.2 | 30.8 | 49.2 | 36.8 |
| `claude-opus-4-8` | G2 | 1.6 | 5.8 | 31.0 | 38.4 | 22.2 |
| `gpt-5.5-2026-04-23` | G1 | 23.6 | 35.6 | 40.4 | 50.8 | 40.8 |
| `gpt-5.5-2026-04-23` | G2 | 30.8 | 36.0 | 50.6 | 54.4 | 40.2 |
| `deepseek-v4-pro` | G1 | 5.0 | 10.6 | 17.4 | 15.0 | **SKIP** |
| `deepseek-v4-pro` | G2 | 3.8 | 7.4 | 13.4 | 16.8 | 14.4 |
| `kimi-k3` | G1 | 2.0 | 15.2 | 20.6 | 17.8 | 12.6 |
| `kimi-k3` | G2 | 1.8 | 8.0 | 11.4 | 16.2 | 11.2 |

**Key gaps, in commit-rate points** (deployed benefit = `graph` − `flat_list`; structure-only = `graph_neutral` − `flat_list`):

| Model | Graph | `graph` − `flat_list` | `graph_neutral` − `flat_list` |
|---|---|---|---|
| `claude-sonnet-4-6` | G1 / G2 | +21.8 / +38.8 | **+19.4** / **+20.2** |
| `claude-opus-4-8` | G1 / G2 | +36.0 / +32.6 | **+23.6** / **+16.4** |
| `gpt-5.5-2026-04-23` | G1 / G2 | +15.2 / +18.4 | +5.2 / +4.2 |
| `deepseek-v4-pro` | G1 / G2 | +4.4 / +9.4 | N/A (skip) / +7.0 |
| `kimi-k3` | G1 / G2 | +2.6 / +8.2 | **−2.6** / +3.2 |

The deployed-benefit gap (`graph` vs `flat_list`) is positive for **every model on both graphs** — no exceptions. The structure-only gap is positive in 8 of 10 measured cells; the two exceptions are disclosed, not hidden: `kimi-k3` is the only model where structure-alone is negative on one graph (G1, −2.6 — run-level, this loses 3/5 runs, not a rounding artifact), and `deepseek-v4-pro` is missing a data point on G1 entirely (see below).

### Correctness methodology (commit ≠ correct)

A model that confidently commits to the *wrong* priority is worse than an honest hedge. Ground truth for each query is derived from the seed graph's own weights, computed **per query** (not a single global figure): for a forced-choice query, ground truth is the higher-weighted of the named items; for an open-ended query, it's the seed graph's single highest-weight root-to-leaf path.

Queries whose ground-truth margin falls **below the decay step** (~3.5 weight points, the smallest deliberate spacing the seed graphs use) are flagged as **near-ties and excluded from correctness scoring only** — they remain fully scored for commit/hedge decisiveness, since that doesn't depend on which answer is "correct."

| Graph | Queries scored for correctness | Near-ties excluded |
|---|---|---|
| G1 | 96 / 100 | 3 (+1 ambiguous) |
| G2 | 69 / 100 | 30 (+1 ambiguous) |

**Correctness, absolute % of the scored set** (does the response name the actually-highest-priority item?):

| Model | Graph | `flat_list` | `graph` | `graph_neutral` |
|---|---|---|---|---|
| `claude-sonnet-4-6` | G1 / G2 | 8% / 6% | 23% / 30% | 22% / 13% |
| `claude-opus-4-8` | G1 / G2 | 8% / 3% | 31% / 21% | 21% / 11% |
| `gpt-5.5-2026-04-23` | G1 / G2 | 18% / 26% | **38%** / **42%** | 32% / 34% |
| `deepseek-v4-pro` | G1 / G2 | 3% / 3% | 9% / 10% | SKIP / 10% |
| `kimi-k3` | G1 / G2 | 8% / 5% | 12% / 11% | 9% / 9% |

Every model, every graph: the graph and graph_neutral conditions are correct more often than flat_list, in absolute terms. **Stated plainly:** even the best result here (GPT-5.5, ~40%) means the model names the right priority under 4 times in 10 — decisive commitment is real and structure-driven, but it is not reliable priority-routing. Full per-condition breakdown (all 5 conditions, absolute correct/wrong/unresolvable counts) in [`n100_analysis.md`](research/results/n100_analysis.md).

### Disclosed limitations and exclusions

- **`deepseek-v4-pro` × G1 × `graph_neutral` is missing, not interpolated.** Two independent attempts both produced responses with `finish_reason="stop"` but zero-length content while still consuming real tokens (2,021 and 2,678 tokens respectively) — a genuine reliability finding about a day-old model release, not a harness bug. The same condition succeeded cleanly on G2 (500/500 calls, no anomalies), so this is a graph1-specific asymmetry, not a general `graph_neutral` failure for this model. Full record: [`n100_empty_response_events.jsonl`](research/results/n100_empty_response_events.jsonl), [`n100_skipped_cells.json`](research/results/n100_skipped_cells.json).
- **`kimi-k3` is the weakest and least consistent model in the panel** — lowest commit rates and lowest correctness throughout, and the only model whose structure-only signal reverses sign between graphs. It also runs at roughly 4x the per-call latency of the other four models (Moonshot's `reasoning_effort` defaults to `"max"` and was left at that default, run at every model's own defaults rather than hand-tuned per model).
- **Gemini and Groq models were excluded from the N=100 panel.** Both were tested at N=12 (see the pilot results below): Gemini's models hit a hard 250-requests/day quota that makes N=100 infeasible on a free/low tier; both Groq models (`openai/gpt-oss-120b`, `llama-3.3-70b-versatile`) failed on sustained throughput (a clean first run, then a multi-hour stall with no server-side error) before reaching even N=12 completion. Their partial N=12 data is preserved in `research/results/` but not part of the primary 5-model panel.

### Pilot (N=12, single seed graph) — superseded by the N=100 result above

The original 12-priority-ranking-query, single-graph pilot first raised this claim and is kept here for the record, not as the current headline finding:

| Model | `graph` | `flat_list_prioritized` | `flat_list` | `graph_neutral` | `none` | Verdict |
|---|---|---|---|---|---|---|
| `claude-sonnet-4-6` | 5.4 [3–8] | 3.6 [3–4] | 3.6 [3–5] | **8.8 [7–11]** | 0.0 [0–0] | STRUCTURAL |
| `claude-opus-4-8` | 6.2 [4–9] | 3.6 [2–5] | 1.6 [0–3] | 5.8 [4–8] | 1.0 [0–2] | MIXED |
| `gpt-5.5-2026-04-23` | 6.6 [3–9] | 6.6 [3–10] | 7.0 [6–8] | 6.6 [5–9] | 2.2 [1–4] | MIXED (no signal) |

At N=12 this looked like it might be Claude-specific (GPT-5.5 showed no separable effect at all). The N=100 scale-up above, across 2 additional non-Claude vendors, shows the structural effect is broader than that pilot could tell — GPT-5.5 does show a small-but-consistent structure-only effect at N=100 (+5.2/+4.2) that the smaller pilot didn't have the power to detect cleanly.

### Is the scorer trustworthy?

COMMIT/HEDGE labeling is a deterministic keyword+structure classifier, pre-registered and frozen before any scored run, validated to 11/11 on a held-out set drawn from earlier development runs (never from data it went on to score) — see `research/poc_compare_v2.py`'s `VALIDATION_SET`. It has never been retuned based on what a scored run's output looked like, including when that meant reporting a weaker number, and it is the exact same scorer (imported, not copied or modified) used for every phase of this eval including the N=100 campaign — re-validated 11/11 before every provider's first live call each session.

Independently, a human rater scored the same 36 responses the scorer did (sonnet, run 1, `graph`/`flat_list`/`none`, from the N=12 pilot): **Cohen's κ = 0.640**, raw agreement 30/36 (83.3%). The 6 disagreements are directional, not noise — the scorer under-counts real commits in `graph` (4/6) and over-counts them in `flat_list` (2/6), which means the measured graph-vs-flat_list gap is a *conservative* estimate of the true effect, not an inflated one. Full confusion matrix and every disagreement in [`scorer_human_agreement.md`](research/results/scorer_human_agreement.md).

### Reproducing the evaluation

```bash
# frozen scorer's own held-out validation (no API calls)
python -c "import sys; sys.path.insert(0,'research'); from poc_compare_v2 import validate; validate()"

# 1. generate the frozen N=100 query set per graph (deterministic, zero LLM calls -
#    templated fill against the seed graphs' own weights, no model in the eval panel
#    touches query generation)
python research/generate_queries_n100.py

# 2. run the N=100 campaign, one process per PROVIDER (not per model) so accounts stay
#    isolated - each provider gets its own eval DB and its own resumable ledger. Safe to
#    run all 4 in parallel as separate processes.
python research/n100_campaign.py anthropic   # claude-sonnet-4-6 + claude-opus-4-8, needs ANTHROPIC_API_KEY
python research/n100_campaign.py openai      # gpt-5.5-2026-04-23, needs OPENAI_API_KEY
python research/n100_campaign.py deepseek    # deepseek-v4-pro, needs DEEPSEEK_API_KEY
python research/n100_campaign.py kimi        # kimi-k3, needs MOONSHOT_API_KEY

# 3. analysis (zero API calls - reads existing results)
python research/n100_tables.py               # the 4 tables above, recomputed from committed data
python research/n100_analysis.py              # fuller per-model/per-graph breakdown

# legacy N=12 pilot + correctness + scorer-human agreement (zero API calls where noted)
python research/poc_compare_multimodel.py claude-sonnet-4-6 5     # needs ANTHROPIC_API_KEY
python research/correctness_analysis.py        # no API calls
python research/score_agreement.py             # no API calls
```

Copy `.env.example` to `.env` and fill in whichever key(s) the models you're running need: `ANTHROPIC_API_KEY` (sonnet, opus), `OPENAI_API_KEY` (gpt-5.5), `DEEPSEEK_API_KEY`, `MOONSHOT_API_KEY` (kimi). `GEMINI_API_KEY`/`GROQ_API_KEY` are exercised only by the excluded N=12 breadth attempts described above.

**Reproducibility knobs, all active by default:**
- **Fixed decoding temperature** (1.0, sent explicitly on every backend) — if a model ever rejects the param, the run raises rather than silently retrying without it. One disclosed exception: `kimi-k3`'s temperature is fixed server-side at 1.0 by Moonshot and their API rejects the param entirely — the harness omits it for that model only and hard-fails if a different temperature were ever requested, so the pin is enforced by the provider's own default rather than an explicit param for this one case.
- **Reseed-per-call invariant** — the eval DB is wiped and reseeded from the pristine seed graph before *every individual call*; a run aborts before spending an API call if the (node, edge) count ever drifts from the run's own baseline.
- **Universal truncation/empty-response guard** — every response is checked against its backend's own truncation/empty signal before it can reach the scorer; a truncated or empty response raises instead of being silently counted as a hedge. This guard is what caught deepseek's graph1/graph_neutral failure above — it worked exactly as designed.
- **Per-provider isolated eval databases and resumable ledgers** (N=100 campaign) — each provider (`anthropic`/`openai`/`deepseek`/`kimi`) writes to its own `eval_<provider>.db` and its own `n100_ledger_<provider>.json`, so providers can run concurrently with zero shared mutable state, and an interrupted campaign resumes from the last fully-completed cell rather than restarting or silently continuing a partial one.
- **Model+graph+condition+run-tagged output files** — no run, model, graph, or phase of this eval has ever overwritten another; every superseded or excluded attempt (Gemini's quota wall, Groq's throughput stall, a discarded first GPT-5.5 baseline that was silently truncating ~8% of the time, deepseek's disclosed skip) is preserved and disclosed rather than quietly dropped.

See [`research/README.md`](research/README.md) for the full script-by-script index, [`RESEARCH.md`](RESEARCH.md) for the dated development record, and [`papers/`](papers/) for the paper draft.

## Built with

| Layer | Tech |
|---|---|
| Storage | SQLite (`~/.asterism/asterism.db`) |
| Graph | NetworkX |
| Entity resolution | fastembed (ONNX, local) — `BAAI/bge-small-en-v1.5` |
| Visualization | Vanilla JS force simulation (zero dependencies) |
| LLM (product) | Anthropic SDK — `claude-sonnet-4-6` by default |
| LLM (evaluation) | 5 models / 4 vendors — Anthropic (`claude-sonnet-4-6`, `claude-opus-4-8`), OpenAI (`gpt-5.5-2026-04-23`), DeepSeek (`deepseek-v4-pro`), Moonshot (`kimi-k3`); Gemini/Groq tested but excluded from the primary panel (quota/throughput, see Research & Evaluation). Model is a parameter, not hardcoded, in `llm.converse()` |
| Extraction | Ollama `llama3.2:3b` (local) or Anthropic Haiku (cloud) |
| UI | Streamlit |
| CLI | Click |

## Author

**Bidit** — [github.com/biditdas18](https://github.com/biditdas18)
