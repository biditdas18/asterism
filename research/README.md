# Research scripts

Standalone evaluation scripts backing the claims in the root [README](../README.md)
and [RESEARCH.md](../RESEARCH.md). None of these are part of the installed
`asterism` package or touch your real `~/.asterism/asterism.db` — each seeds
its own throwaway, isolated SQLite file and deletes it when done.

Run any of them from the repo root (or anywhere — they locate the repo root
themselves):

```bash
python research/generate_queries_n100.py                      # THE current query set, deterministic, no API calls
python research/n100_campaign.py <provider>                    # THE current eval - see below
python research/n100_tables.py                                 # numbers-only tables from committed N=100 results
python research/n100_analysis.py                                # fuller per-model/per-graph N=100 breakdown
python research/poc_compare_multimodel.py <model> [n_runs]    # N=12 pilot (superseded by N=100, kept running)
python research/correctness_analysis.py                       # N=12 pilot commit != correct check (no API calls)
python research/correctness_analysis_graph2.py                 # same, second seed graph (no API calls)
python research/score_agreement.py [path/to/filled.csv]       # scorer-human kappa (no API calls)
python research/poc_compare_v2.py      # superseded: single-model, 3-condition eval, kept for the record
python research/poc_compare.py         # superseded: the original first attempt, kept for the record
python research/benchmark_latency.py   # local-only, no API calls
```

| Script | What it measures | Needs API key? |
|---|---|---|
| `generate_queries_n100.py` | **Current.** Generates the frozen 100-query-per-graph set from the seed graphs' own node labels via a fixed template bank — zero LLM calls, fully deterministic, no model under test ever generates its own eval queries. Computes each query's ground truth and a query-local near-tie margin (excluded from correctness scoring below the decay step, ~3.5 weight points). | No |
| `n100_campaign.py` | **Current.** The N=100 eval: 5 conditions x 5 models x 2 graphs x 5 runs. One process per **provider** (`anthropic`/`openai`/`deepseek`/`kimi`), each with its own isolated eval DB and its own resumable ledger (`n100_ledger_<provider>.json`) — safe to run all 4 concurrently. A cell (model×graph×condition) is all-or-nothing: an interrupted cell restarts from call 1 on relaunch rather than resuming mid-cell. Includes a heartbeat/watchdog (10-minute per-call timeout, retried once) and `n100_status.json` for live progress. | Yes (see `.env.example`) |
| `n100_tables.py` | Numbers-only rebuild of the 4 core result tables (commit rate, key gaps, correctness denominators, correctness %, run-level consistency) directly from the committed `n100_*.json` result files. No API calls, no interpretation. | No |
| `n100_analysis.py` | Fuller prose-annotated per-model/per-graph N=100 breakdown, written to `results/n100_analysis.md`. No API calls. | No |
| `poc_compare_multimodel.py` | N=12 pilot (superseded by the N=100 campaign above, kept running as the scorer's own re-validation path). 5 conditions x 3 models x 5 runs, isolating graph *structure* from the prioritize/commit *instruction*. | Yes (Anthropic or OpenAI, depending on model) |
| `correctness_analysis.py` | N=12 pilot correctness check, seed graph 1. Among responses already labeled COMMIT, does the named target match the seed graph's true highest-weight node? Deterministic label/alias matching, not an LLM judge. Does not touch the scorer. | No |
| `correctness_analysis_graph2.py` | Same, for the second seed graph (Priya persona). | No |
| `score_agreement.py` | Cohen's kappa between the frozen scorer and a human rater on a 36-row sheet (N=12 pilot data). Reads an already-filled CSV; does not fill it or touch the scorer. | No |
| `poc_compare_v2.py` | Superseded: the 3-condition (`graph`/`flat_list`/`none`), single-model (`claude-sonnet-4-6`) version of this eval. Its scorer and held-out `VALIDATION_SET` are imported unchanged by every later script (including `n100_campaign.py`) — still the canonical, frozen, pre-registered classifier. Kept running, not just kept as a record: this is how you re-validate the scorer itself. | Yes |
| `poc_compare.py` | Superseded: the original first attempt (regex bug + a category-mismatched metric on descriptive queries). Kept, not deleted, so the correction is auditable rather than quietly overwritten. | Yes |
| `benchmark_latency.py` | Does graph retrieval latency scale acceptably as the graph grows (100 / 1,000 / 10,000 synthetic nodes)? | No |

## Reproducing the evaluation

### Current: N=100, 5 models, 2 graphs

`n100_campaign.py` reuses `poc_compare_v2.py`'s scorer, held-out
`VALIDATION_SET`, and `validate()` **unchanged** — imported, not copied,
never re-tuned. Queries come from `generate_queries_n100.py`'s frozen,
deterministic output (`queries_n100_graph1.json` / `queries_n100_graph2.json`),
not generated live by any model under test. `extract_triples()`'s own model
(graph maintenance, Haiku/local Ollama) is independent of this and unaffected.

```bash
python research/generate_queries_n100.py     # regenerate the query set (byte-identical every time - no randomness)

python research/n100_campaign.py anthropic   # sonnet + opus, needs ANTHROPIC_API_KEY
python research/n100_campaign.py openai      # gpt-5.5, needs OPENAI_API_KEY
python research/n100_campaign.py deepseek    # needs DEEPSEEK_API_KEY
python research/n100_campaign.py kimi        # needs MOONSHOT_API_KEY

python research/n100_tables.py               # numbers-only tables from committed results
python research/n100_analysis.py              # fuller breakdown -> results/n100_analysis.md
```

Reproducibility knobs, all active by default:
- **temperature=1.0**, sent explicitly on every backend (one disclosed
  exception: `kimi-k3`'s temperature is fixed server-side and the param is
  omitted for that model only, hard-failing if a different value were ever
  requested).
- **Reseed-per-call** — the eval DB is wiped and reseeded from the pristine
  seed graph before *every individual call*; a run aborts before the API
  call if the (node, edge) count ever drifts from the run's own baseline.
- **Universal truncation/empty-response guard** — every response is checked
  against its backend's own truncation/empty signal before it can reach the
  scorer. This is what caught `deepseek-v4-pro`'s graph1/graph_neutral
  failures (see `n100_empty_response_events.jsonl`) rather than silently
  scoring them as hedges.
- **Per-provider isolated eval DB + resumable ledger** — each of the 4
  providers (`anthropic`/`openai`/`deepseek`/`kimi`) owns its own
  `eval_<provider>.db` and `n100_ledger_<provider>.json`; safe to run all 4
  concurrently, and an interrupted campaign resumes at the last
  fully-completed (model, graph, condition) cell rather than continuing a
  partially-scored one.

Model strings starting with `gpt`/`o1`/`o3`/`o4` route to OpenAI; `gemini*`
routes to Google's OpenAI-compatible endpoint; two explicit Groq model ids
route to Groq; `deepseek-v4-pro` and `kimi-k3` route to their own
OpenAI-compatible endpoints; everything else routes to Anthropic. Copy
`.env.example` to `.env` and fill in whichever key(s) you're running —
`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `MOONSHOT_API_KEY`
cover the primary 5-model panel; `GEMINI_API_KEY`/`GROQ_API_KEY` cover the
excluded breadth attempt (see root README's Disclosed limitations).

### N=12 pilot (superseded, kept running)

`poc_compare_multimodel.py` is the original single-graph, 12-query, 3-model
pilot that first found this effect and motivated the N=100 scale-up. Same
scorer, same reseed/temperature/truncation-guard discipline, smaller scale:

```bash
python research/poc_compare_multimodel.py claude-sonnet-4-6 5   # needs ANTHROPIC_API_KEY
python research/poc_compare_multimodel.py claude-opus-4-8 5     # needs ANTHROPIC_API_KEY
python research/poc_compare_multimodel.py gpt-5.5-2026-04-23 5  # needs OPENAI_API_KEY
```

After a campaign, `correctness_analysis.py` / `correctness_analysis_graph2.py`
and `score_agreement.py` all run against results already on disk — no API
calls, safe to rerun any time.

## results/

Generated output — full side-by-side responses, scored commit/hedge tables,
correctness verdicts, and latency numbers. Regenerated by re-running the
corresponding script; not hand-edited (the one exception is `human_label` in
the `*_human_eval.csv` sheets, filled in by hand on purpose).

**Current (N=100, 5 models x 2 graphs x 5 conditions x 5 runs):**
- `n100_<model-tag>_<graph>_<condition>.json` — full per-run responses, one file per (model, graph, condition) cell; 49 present, `deepseek-v4-pro_graph1_graph_neutral` is a disclosed skip (see `n100_skipped_cells.json`)
- `n100_ledger_<provider>.json` — resumable progress ledger, one per provider, lists every fully-completed cell + per-cell duration
- `n100_status.json` — live progress snapshot (overwritten each heartbeat during a run)
- `n100_skipped_cells.json` — deliberately-skipped cells with the disclosed reason
- `n100_empty_response_events.jsonl` — every truncation/empty-response event the universal guard caught, regardless of whether the retry that followed succeeded
- `n100_analysis.md` — full per-model/per-graph breakdown

**Pilot (N=12, kept for the record — the finding that motivated the scale-up above):**
- `poc_eval_results_phase2_<model-tag>_aggregate.md` — mean/min/max commit rate + STRUCTURAL/INSTRUCTIONAL/MIXED verdict, one per model
- `poc_results_phase2_<model-tag>_run<i>.md` / `.json`, `poc_eval_results_phase2_<model-tag>_run<i>.md` — per-run detail backing each aggregate
- `correctness_analysis.md` / `_raw.json` — commit-vs-correct scoring, seed graph 1
- `correctness_analysis_graph2.md` / `_raw.json` — same, seed graph 2
- `scorer_human_agreement.md` — captured script output: kappa, raw agreement, confusion matrix, all 6 disagreements
- `sonnet_phase2_run1_human_eval.csv` — the filled sheet backing that kappa

**Superseded (kept for the audit trail, not deleted):**
- `poc_eval_results_<model-tag>_aggregate.md` / `_run<i>.md`, `poc_results_<model-tag>_run<i>.*` — the original 3-condition multimodel eval, before the instruction-vs-structure split
- `poc_eval_results_v2.md`, `poc_results_v2.md` / `.json` — single-model (sonnet), 3-condition
- `poc_eval_results.md`, `poc_results.md` / `.json` — the original first (buggy) attempt
- `sonnet_run1_human_eval.csv` — the earlier, pre-Phase-2 human-eval sheet (untouched, unfilled)

**Always:**
- `benchmark_results.md` — latency numbers
