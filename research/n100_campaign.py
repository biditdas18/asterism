#!/usr/bin/env python3
"""
Phase C: N=100 scale-up campaign, resumable multi-day, one worker per
PROVIDER (not per model) so accounts stay isolated but same-vendor models
share nothing that needs isolating between them.

PROVIDER_MODELS below is deliberately fixed to the 5-model panel approved
for this run - Gemini and Groq are NOT in scope (250/day cap makes N=100
infeasible for Gemini; Groq already failed twice on throughput at N=12).
They keep their existing N=12 Phase B data, untouched by this script.

CELL = (model, graph, condition). A cell is all-or-nothing: it is only
considered done once all 5 runs x 100 queries (500 calls) for that
(model, graph, condition) complete successfully. An interrupted cell is
NEVER resumed mid-way - on restart it re-runs from call 1, and nothing is
written for a cell until it fully completes. This is a deliberate
simplicity/integrity tradeoff (more wasted work on interruption, zero risk
of subtly-wrong partial-cell bookkeeping), not an oversight.

Per-provider isolation: each provider gets its own eval DB file
(research/eval_<provider>.db) and its own ledger file
(research/results/n100_ledger_<provider>.json) - safe to run all 4 provider
workers as separate concurrent processes with zero shared mutable state.

Guards (same as every prior phase): temperature=1.0 pinned (kimi-k3 is the
disclosed exception - see llm.py, its fixed server-side default already
equals 1.0), reseed-per-call with abort-on-drift, universal truncation/
empty-response guard (all live inside llm.converse(), unchanged), frozen v2
scorer imported unchanged and validated 11/11 before a provider's first
live call this run, extractor.py untouched.

Usage: python research/n100_campaign.py <provider>
  provider in {anthropic, openai, deepseek, kimi}
"""
import datetime
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import db
from db import init_db, add_node, add_edge, get_connection
from llm import converse
from poc_compare_v2 import validate, classify_commit_or_hedge, VALIDATION_SET
from poc_compare import DEMO_GRAPH, DEMO_USER
from seed_graph_2 import DEMO_GRAPH_2, DEMO_USER_2
from correctness_analysis import extract_target as extract_target_g1
from correctness_analysis_graph2 import extract_target as extract_target_g2

RESULTS_DIR = os.path.join(HERE, "results")
TEMPERATURE = 1.0
CONDITIONS = ["graph", "flat_list_prioritized", "flat_list", "graph_neutral", "none"]
GRAPHS = ["graph1", "graph2"]
N_RUNS = 5
HEARTBEAT_INTERVAL_S = 60
WATCHDOG_TIMEOUT_S = 600  # 10 min

# Cells deliberately excluded from attempting at all - distinct from the
# ledger's completed_cells (which means real data exists). A skipped cell
# has NO data and is never retried; the reason is disclosed in the final
# report, not silently dropped. deepseek-v4-pro|graph1|graph_neutral is
# skipped after 2 attempts both produced recurring empty-but-token-consuming
# responses on 2 DISTINCT queries - see research/results/
# n100_empty_response_events.jsonl for the full record. graph2|graph_neutral
# for the same model is deliberately NOT pre-skipped here - it gets exactly
# one normal-sequence attempt to test whether the failure is condition-
# systematic (both graphs) or graph1-specific; if it also fails, add it here
# manually before the next relaunch - do not auto-retry it.
SKIPPED_CELLS = {
    "deepseek": {
        "deepseek-v4-pro|graph1|graph_neutral":
            "deepseek-v4-pro produced recurring empty-but-token-consuming responses "
            "in the graph_neutral condition across >=2 distinct queries over 2 attempts; "
            "its structure-alone signal is unmeasurable on this setup",
    },
}


def _skipped_cells_log_path() -> str:
    return os.path.join(RESULTS_DIR, "n100_skipped_cells.json")


def _record_skip(provider: str, key: str, reason: str):
    path = _skipped_cells_log_path()
    data = []
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
    data.append({"provider": provider, "cell": key, "reason": reason,
                 "recorded_at": datetime.datetime.now().isoformat(timespec="seconds")})
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

PROVIDER_MODELS = {
    "anthropic": ["claude-sonnet-4-6", "claude-opus-4-8"],
    "openai": ["gpt-5.5-2026-04-23"],
    "deepseek": ["deepseek-v4-pro"],
    "kimi": ["kimi-k3"],
}
ALL_PROVIDERS = list(PROVIDER_MODELS)
TOTAL_CELLS_ALL_PROVIDERS = sum(len(models) for models in PROVIDER_MODELS.values()) * len(GRAPHS) * len(CONDITIONS)

GRAPH_INFO = {
    "graph1": {
        "seed_fn": lambda: _seed(DEMO_GRAPH, DEMO_USER),
        "queries_path": os.path.join(HERE, "queries_n100_graph1.json"),
        "extract_target": extract_target_g1,
    },
    "graph2": {
        "seed_fn": lambda: _seed(DEMO_GRAPH_2, DEMO_USER_2),
        "queries_path": os.path.join(HERE, "queries_n100_graph2.json"),
        "extract_target": extract_target_g2,
    },
}


def _seed(graph_data, user_label):
    """Same seeding formula as poc_compare._seed_demo_graph / seed_graph_2,
    parameterized so both graphs can share one function here without
    duplicating either frozen module's own seeder."""
    def set_weight(label, weight):
        with get_connection() as conn:
            conn.execute("UPDATE nodes SET weight = ? WHERE label = ?", (weight, label))

    def add_chain(parent, titles, base_weight):
        prev = parent
        for i, title in enumerate(titles):
            w = base_weight * (1 - 0.05 * i)
            add_node(title, node_type="concept")
            set_weight(title, round(w, 1))
            add_edge(prev, title)
            prev = title

    add_node(user_label, node_type="user")
    set_weight(user_label, 100.0)
    for d in graph_data:
        add_node(d["domain"], node_type="domain")
        set_weight(d["domain"], d["domain_weight"])
        add_edge(user_label, d["domain"])
        for t in d["themes"]:
            add_node(t["name"], node_type="theme")
            set_weight(t["name"], t["weight"])
            add_edge(d["domain"], t["name"])
            add_chain(t["name"], t["chain"], t["weight"])


def _load_queries(graph: str) -> list[dict]:
    with open(GRAPH_INFO[graph]["queries_path"]) as f:
        return json.load(f)


def _tag(model: str) -> str:
    import re
    return re.sub(r"[^a-zA-Z0-9_-]", "_", model)


def _cell_key(model: str, graph: str, condition: str) -> str:
    return f"{model}|{graph}|{condition}"


def _ledger_path(provider: str) -> str:
    return os.path.join(RESULTS_DIR, f"n100_ledger_{provider}.json")


def _load_ledger(provider: str) -> dict:
    path = _ledger_path(provider)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"completed_cells": [], "history": []}


def _save_ledger(provider: str, ledger: dict):
    with open(_ledger_path(provider), "w") as f:
        json.dump(ledger, f, indent=2)


def _status_path() -> str:
    return os.path.join(RESULTS_DIR, "n100_status.json")


def _write_status(provider: str, model: str, graph: str, condition: str,
                   calls_done: int, calls_total: int, cell_idx: int, cells_total: int,
                   cell_started_at: float, extra: dict | None = None):
    """Merges this provider's live state into the shared status.json - each
    provider only ever writes its own top-level key, so concurrent writes
    from different provider processes never race on the same bytes."""
    path = _status_path()
    status = {}
    if os.path.exists(path):
        try:
            with open(path) as f:
                status = json.load(f)
        except (json.JSONDecodeError, OSError):
            status = {}
    elapsed = time.time() - cell_started_at
    rate = calls_done / elapsed if elapsed > 0 and calls_done > 0 else None
    remaining_calls = calls_total - calls_done
    eta_this_cell_s = (remaining_calls / rate) if rate else None
    status[provider] = {
        "model": model, "graph": graph, "condition": condition,
        "cell_index": cell_idx, "cells_total_this_provider": cells_total,
        "calls_done_this_cell": calls_done, "calls_total_this_cell": calls_total,
        "pct_this_cell": round(100 * calls_done / calls_total, 1) if calls_total else 0,
        "eta_this_cell_seconds": round(eta_this_cell_s) if eta_this_cell_s else None,
        "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        **(extra or {}),
    }
    with open(path, "w") as f:
        json.dump(status, f, indent=2)


def _seed_node_edge_count() -> tuple[int, int]:
    with get_connection() as conn:
        n = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        e = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    return n, e


def _empty_response_log_path() -> str:
    return os.path.join(RESULTS_DIR, "n100_empty_response_events.jsonl")


def _log_empty_response_event(model: str, graph: str, condition: str, run_idx: int,
                               query: dict, error_str: str):
    """Every empty/truncated-response event is a disclosable methodological
    finding, not just noise that goes away when the cell is retried - logged
    here regardless of whether the retry that follows succeeds or fails
    again, so a one-off blip and a systematic pattern are both on the
    record, not just whichever one happened to be the last thing printed
    before the process exited."""
    import re
    tokens_match = re.search(r"tokens_used=(\d+)", error_str)
    event = {
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "model": model, "graph": graph, "condition": condition, "run": run_idx,
        "query_id": query["id"], "query_text": query["text"],
        "tokens_burned": int(tokens_match.group(1)) if tokens_match else None,
        "raw_error": error_str,
    }
    print(f"[EMPTY-RESPONSE EVENT] {model} {graph}/{condition} run{run_idx} "
          f"query={query['id']!r} tokens_burned={event['tokens_burned']}")
    with open(_empty_response_log_path(), "a") as f:
        f.write(json.dumps(event) + "\n")


def _watchdog_call(fn, timeout_s=WATCHDOG_TIMEOUT_S, label=""):
    """Runs fn() in a worker thread with a hard wall-clock timeout. On
    timeout: logs a visible stall, retries ONCE (fresh call), and if that
    also times out, raises so the caller can decide (this campaign: the
    whole cell aborts uncompleted, consistent with 'never resume a
    half-scored cell' - a stalled call is exactly the kind of interruption
    that voids the cell). Python threads can't be force-killed; an
    abandoned thread from a timed-out call may finish later in the
    background and its result is simply discarded - this is the standard,
    accepted limitation of a thread-based watchdog and is not silent: the
    stall itself is always logged before moving on."""
    for attempt in (1, 2):
        with ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(fn)
            try:
                return future.result(timeout=timeout_s)
            except FutureTimeoutError:
                print(f"[WATCHDOG] {label}: no response after {timeout_s}s "
                      f"(attempt {attempt}/2) - {'retrying once' if attempt == 1 else 'giving up, aborting cell'}")
                if attempt == 2:
                    raise RuntimeError(f"{label}: watchdog timeout on retry - aborting cell, no partial output")


def run_cell(model: str, graph: str, condition: str, cell_idx: int, cells_total: int) -> dict:
    queries = _load_queries(graph)
    seed_fn = GRAPH_INFO[graph]["seed_fn"]
    eval_db_path = _EVAL_DB_PATH  # set by main() per provider

    calls_total = N_RUNS * len(queries)
    calls_done = 0
    cell_started_at = time.time()
    last_heartbeat = cell_started_at

    per_run_results = []
    baseline = None
    for run_idx in range(1, N_RUNS + 1):
        run_results = []
        for q in queries:
            db.DB_PATH = eval_db_path
            if os.path.exists(eval_db_path):
                os.remove(eval_db_path)
            init_db()
            seed_fn()
            counts = _seed_node_edge_count()
            if baseline is None:
                baseline = counts
            elif counts != baseline:
                raise RuntimeError(
                    f"E-FIX INVARIANT VIOLATED at model={model!r} graph={graph!r} "
                    f"condition={condition!r} run={run_idx} query={q['id']!r}: seed was "
                    f"{counts}, expected {baseline}. Aborting cell - no partial output."
                )

            def _call():
                return converse(q["text"], [], inject_mode=condition, model=model, temperature=TEMPERATURE)

            try:
                out = _watchdog_call(_call, label=f"{model}/{graph}/{condition}/run{run_idx}/{q['id']}")
            except RuntimeError as e:
                if "truncated or empty response" in str(e):
                    _log_empty_response_event(model, graph, condition, run_idx, q, str(e))
                raise
            label = classify_commit_or_hedge(out["response"])
            run_results.append({
                "query_id": q["id"], "query_text": q["text"], "family": q["family"],
                "ground_truth": q["ground_truth"], "response": out["response"],
                "tokens_used": out["tokens_used"], "label": label,
            })
            calls_done += 1

            now = time.time()
            if now - last_heartbeat >= HEARTBEAT_INTERVAL_S:
                last_heartbeat = now
                elapsed = now - cell_started_at
                rate = calls_done / elapsed if elapsed > 0 else 0
                eta_s = (calls_total - calls_done) / rate if rate > 0 else None
                eta_str = f"{eta_s/3600:.1f}h" if eta_s else "?"
                print(f"[HEARTBEAT][{model}] cell {cell_idx}/{cells_total} ({graph}/{condition}) "
                      f"| {calls_done}/{calls_total} calls ({100*calls_done/calls_total:.1f}%) "
                      f"| run {run_idx}/{N_RUNS} | rate={rate:.3f} calls/s | ETA this cell: {eta_str}")
                _write_status(_PROVIDER, model, graph, condition, calls_done, calls_total,
                              cell_idx, cells_total, cell_started_at)

        per_run_results.append(run_results)

    if os.path.exists(eval_db_path):
        os.remove(eval_db_path)

    return {"model": model, "graph": graph, "condition": condition,
            "n_runs": N_RUNS, "n_queries": len(queries),
            "temperature": TEMPERATURE, "runs": per_run_results}


def main():
    global _PROVIDER, _EVAL_DB_PATH
    if len(sys.argv) < 2 or sys.argv[1] not in PROVIDER_MODELS:
        print(f"Usage: python research/n100_campaign.py <provider>  (provider in {list(PROVIDER_MODELS)})")
        sys.exit(1)
    provider = sys.argv[1]
    _PROVIDER = provider
    _EVAL_DB_PATH = os.path.join(HERE, f"eval_{provider}.db")

    if not validate():
        print("\nValidation FAILED against the v2 held-out set - aborting before spending API budget.")
        sys.exit(1)
    n_ok = sum(1 for e in VALIDATION_SET if classify_commit_or_hedge(e["text"]) == e["expected"])
    print(f"Validation clean ({n_ok}/{len(VALIDATION_SET)}). Provider={provider!r}, "
          f"models={PROVIDER_MODELS[provider]}, temperature={TEMPERATURE}.\n")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    ledger = _load_ledger(provider)

    cells = [(model, graph, condition)
             for model in PROVIDER_MODELS[provider]
             for graph in GRAPHS
             for condition in CONDITIONS]
    cells_total = len(cells)

    skip_map = SKIPPED_CELLS.get(provider, {})

    for cell_idx, (model, graph, condition) in enumerate(cells, 1):
        key = _cell_key(model, graph, condition)
        if key in ledger["completed_cells"]:
            print(f"[{provider}] cell {cell_idx}/{cells_total} ({key}) already complete - skipping")
            continue
        if key in skip_map:
            reason = skip_map[key]
            print(f"[{provider}] cell {cell_idx}/{cells_total} ({key}) DELIBERATELY SKIPPED "
                  f"(not attempted, no data): {reason}")
            _record_skip(provider, key, reason)
            continue

        print(f"\n{'='*70}\n[{provider}] CELL {cell_idx}/{cells_total}: {key}\n{'='*70}")
        t0 = time.time()
        try:
            result = run_cell(model, graph, condition, cell_idx, cells_total)
        except Exception as e:
            print(f"\n[{provider}] CELL {cell_idx}/{cells_total} ({key}) FAILED after "
                  f"{time.time()-t0:.0f}s: {e!r}")
            print(f"[{provider}] Stopping this worker clean. No partial output written for this cell. "
                  f"Ledger unchanged - {key} will re-run from scratch next launch.")
            _write_status(provider, model, graph, condition, 0, 0, cell_idx, cells_total, t0,
                          extra={"state": "FAILED", "error": str(e)})
            sys.exit(1)

        tag = _tag(model)
        out_path = os.path.join(RESULTS_DIR, f"n100_{tag}_{graph}_{condition}.json")
        with open(out_path, "w") as f:
            json.dump(result, f, indent=2)

        ledger["completed_cells"].append(key)
        ledger["history"].append({"cell": key, "completed_at": datetime.datetime.now().isoformat(timespec="seconds"),
                                  "duration_s": round(time.time() - t0)})
        _save_ledger(provider, ledger)
        print(f"[{provider}] CELL {cell_idx}/{cells_total} ({key}) DONE in {(time.time()-t0)/3600:.2f}h. "
              f"Wrote {out_path}")

    print(f"\n[{provider}] ALL {cells_total} CELLS COMPLETE.")
    _write_status(provider, "", "", "", 0, 0, cells_total, cells_total, time.time(),
                  extra={"state": "COMPLETE"})


if __name__ == "__main__":
    main()
