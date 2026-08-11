# Research scripts

Standalone evaluation scripts backing the claims in the root [README](../README.md)
and [RESEARCH.md](../RESEARCH.md). None of these are part of the installed
`asterism` package or touch your real `~/.asterism/asterism.db` — each seeds
its own throwaway, isolated SQLite file and deletes it when done.

Run any of them from the repo root (or anywhere — they locate the repo root
themselves):

```bash
python research/poc_compare_multimodel.py <model> [n_runs]   # THE current eval, see below
python research/correctness_analysis.py                       # commit != correct check (no API calls)
python research/score_agreement.py [path/to/filled.csv]       # scorer-human kappa (no API calls)
python research/poc_compare_v2.py      # superseded: single-model, 3-condition eval, kept for the record
python research/poc_compare.py         # superseded: the original first attempt, kept for the record
python research/benchmark_latency.py   # local-only, no API calls
```

| Script | What it measures | Needs API key? |
|---|---|---|
| `poc_compare_multimodel.py` | **Current.** 5 conditions (`graph`, `flat_list_prioritized`, `flat_list`, `graph_neutral`, `none`) x 3 models x 5 runs, isolating graph *structure* from the prioritize/commit *instruction*. See below. | Yes (Anthropic or OpenAI, depending on model) |
| `correctness_analysis.py` | Among responses already labeled COMMIT, does the named target match the seed graph's true highest-weight node? Ground truth derived from the seed graph's own weights; deterministic label/alias matching, not an LLM judge. Does not touch the scorer. | No |
| `score_agreement.py` | Cohen's kappa between the frozen scorer and a human rater on a 36-row sheet. Reads an already-filled CSV; does not fill it or touch the scorer. | No |
| `poc_compare_v2.py` | Superseded: the 3-condition (`graph`/`flat_list`/`none`), single-model (`claude-sonnet-4-6`) version of this eval. Its scorer and held-out `VALIDATION_SET` are imported unchanged by every later script — still the canonical, frozen, pre-registered classifier. Kept running, not just kept as a record: this is how you re-validate the scorer itself. | Yes |
| `poc_compare.py` | Superseded: the original first attempt (regex bug + a category-mismatched metric on descriptive queries). Kept, not deleted, so the correction is auditable rather than quietly overwritten. | Yes |
| `benchmark_latency.py` | Does graph retrieval latency scale acceptably as the graph grows (100 / 1,000 / 10,000 synthetic nodes)? | No |

## Reproducing the evaluation

`poc_compare_multimodel.py` reuses `poc_compare_v2.py`'s scorer, held-out
`VALIDATION_SET`, and `validate()` **unchanged** — imported, not copied,
never re-tuned, including when a run's own output looked like it undercounted
commits. Only the assistant model varies; the seeded graph, the 12 PRIORITY
queries, the 5 inject conditions, and the scoring rule are identical across
every model. `extract_triples()`'s own model (graph maintenance, Haiku/local
Ollama) is independent of this and unaffected.

Reproducibility knobs, all active by default:
- **temperature=1.0**, sent explicitly on both backends. If a model rejects the
  param, the run raises rather than silently retrying without it.
- **Reseed-per-call** — the eval DB is wiped and reseeded from the pristine
  seed graph before *every individual call*, not once per run, with the
  (node, edge) count asserted constant against the run's own first call; a run
  aborts before the API call if that invariant ever breaks.
- **Universal truncation/empty-response guard** — every response is checked
  against its backend's own truncation signal before it can reach the scorer.
  A gpt-5.5 baseline that silently returned empty responses ~8% of the time
  at an earlier, too-small token budget was discarded entirely once this was
  found, not corrected in place.

A single 60-call run (12 queries x 5 conditions) is a small, noisy sample —
response phrasing (and so the deterministic scorer's label) varies run to
run even for the same model. Rather than chase a single-run number, the
script runs the full eval `n_runs` times per model and reports the
across-run distribution — mean/min/max per condition. There is no target to
hit; whatever the distribution is gets reported.

```bash
python research/poc_compare_multimodel.py claude-sonnet-4-6 5   # needs ANTHROPIC_API_KEY
python research/poc_compare_multimodel.py claude-opus-4-8 5     # needs ANTHROPIC_API_KEY
python research/poc_compare_multimodel.py gpt-5.5-2026-04-23 5  # needs OPENAI_API_KEY
```

Model strings starting with `gpt`/`o1`/`o3`/`o4` route to OpenAI
(`chat.completions.create`); everything else routes to Anthropic. Copy
`.env.example` to `.env` and fill in whichever key(s) the models you're
running need — see the root README's Privacy section for what does and
doesn't leave your machine. `GEMINI_API_KEY`/`GROQ_API_KEY` are placeholders
for a not-yet-run cross-vendor extension; nothing in this repo calls them yet.

After a campaign, `correctness_analysis.py` and `score_agreement.py` both run
against the results already on disk — no API calls, safe to rerun any time.

## results/

Generated output — full side-by-side responses, scored commit/hedge tables,
correctness verdicts, and latency numbers. Regenerated by re-running the
corresponding script; not hand-edited (the one exception is `human_label` in
the `*_human_eval.csv` sheets, filled in by hand on purpose).

**Current (Phase 2, 5-condition):**
- `poc_eval_results_phase2_<model-tag>_aggregate.md` — mean/min/max commit rate + STRUCTURAL/INSTRUCTIONAL/MIXED verdict, one per model
- `poc_results_phase2_<model-tag>_run<i>.md` / `.json`, `poc_eval_results_phase2_<model-tag>_run<i>.md` — per-run detail backing each aggregate
- `correctness_analysis.md` / `_raw.json` — commit-vs-correct scoring, all models/conditions/runs
- `scorer_human_agreement.md` — captured script output: kappa, raw agreement, confusion matrix, all 6 disagreements
- `sonnet_phase2_run1_human_eval.csv` — the filled sheet backing that kappa

**Superseded (kept for the audit trail, not deleted):**
- `poc_eval_results_<model-tag>_aggregate.md` / `_run<i>.md`, `poc_results_<model-tag>_run<i>.*` — the original 3-condition multimodel eval, before the instruction-vs-structure split
- `poc_eval_results_v2.md`, `poc_results_v2.md` / `.json` — single-model (sonnet), 3-condition
- `poc_eval_results.md`, `poc_results.md` / `.json` — the original first (buggy) attempt
- `sonnet_run1_human_eval.csv` — the earlier, pre-Phase-2 human-eval sheet (untouched, unfilled)

**Always:**
- `benchmark_results.md` — latency numbers
