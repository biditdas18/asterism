#!/usr/bin/env python3
"""
Quantitative PoC eval v2: corrected COMMIT/HEDGE scorer, PRIORITY queries only.

This is a fresh, separately-labeled rerun of the eval in poc_compare.py.
It does NOT overwrite poc_compare.py's output files (poc_results.md/json,
poc_eval_results.md) - that prior run's 1/12-vs-0/12 result stays on the
record. This script writes poc_eval_results_v2.md (and poc_results_v2.md/
json for the full text) instead.

Why a v2: the original scorer had two problems, found on manual inspection
of its own output (not fixed by re-tuning to that output - see below):
  1. A regex bug: "My Take: **Open Source Project First**" (a markdown-
     heading verdict, colon with no preceding space) failed to match a
     commit pattern that required whitespace before the colon.
  2. The DESCRIPTIVE column was scored with the same priority-specific
     vocabulary ("your top priority is", "I'd recommend"...), which
     structurally can't fire on descriptive/recall text. That column's
     results were a scorer/category mismatch, not a behavioral finding.

Fixes in this version, per explicit instruction:
  1. DESCRIPTIVE dropped entirely from the COMMIT/HEDGE metric - COMMIT vs.
     HEDGE is only meaningful for queries that require picking/ranking.
     Only the 12 PRIORITY queries run here (36 calls, not 72).
  2. The scorer is broadened and re-validated against a held-out set of
     11 hand-labeled real responses drawn from Block 2 (the original
     5-query PoC) and the prior 72-call run - NOT from this run's own
     output, which does not exist yet at validation time. The scorer is
     locked before the live 36-call run and not adjusted afterward.

Usage: python research/poc_compare_v2.py (from repo root, or anywhere)
Requires ANTHROPIC_API_KEY configured (see config.py / .env).
"""
import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from poc_compare import _seed_demo_graph, PRIORITY_QUERIES, MODES, EVAL_DB_PATH
from llm import converse

RESULTS_DIR = os.path.join(HERE, "results")

# ============================================================
# CLASSIFIER RUBRIC v2 (pre-registered; locked before the 36-call run)
#
# COMMIT: the response names one specific thing as the answer and stands
#   behind that choice - including markdown-heading verdicts ("## My
#   Take: **X**"), "focus on X first", "I'd prioritize X", "X over Y",
#   "the answer is X" - regardless of spacing/markdown decoration around
#   the phrase.
# HEDGE: the response defers the decision back to the user, enumerates
#   options without picking one, says it lacks enough information to
#   choose, or offers a conditional ("if A then X, if B then Y") without
#   telling the user which branch applies.
#
# Deterministic scorer, no LLM judge. Same combination rule as v1:
#   commit_score = count of distinct COMMIT_PATTERNS matched (regex, i)
#   hedge_score  = count of distinct HEDGE_PATTERNS matched
#                  + 1 if the response asks >=2 user-directed questions
#   label = COMMIT if commit_score > hedge_score, else HEDGE (ties -> HEDGE)
#
# Deliberately NOT added, based on held-out validation:
#   - bare "short answer" / "my instinct" as commit triggers: both appear
#     in held-out examples introducing a heading that does NOT actually
#     commit to one item (one picks 2 things "simultaneously", the other
#     is a conditional "if X then A, if Y then B" with no pick) - adding
#     them produced false-positive COMMIT labels on genuine hedges.
#   - a bare "X over Y" / "prioritize X" pattern: "prioritize between
#     work/research, your project..." appears inside a HEDGE clarifying
#     question in one held-out example; only verb-committed forms
#     ("I'd prioritize", "should prioritize", "choose X over Y") are
#     matched to avoid firing on that.
# ============================================================

COMMIT_PATTERNS = [
    r"\byour top priorit(y|ies)\s*(is|are|:)",
    r"\bthe top priorit(y|ies)\s*(is|are|:)",
    r"\b(my|the) (honest )?(take|read|recommendation|verdict|bottom line)\b",
    r"\bin short\b",
    r"\bthe answer is\b",
    r"\bi'?d (recommend|focus on|prioritize|suggest|start with|go with|say)\b",
    r"\bi would (recommend|focus on|prioritize|suggest|start with)\b",
    r"\b(should|i'?d|you'?d) prioritize\b",
    r"\bchoose\s+[\w\s'-]{1,30}\bover\b",
    r"\b(go|opt)\s+(with|for)\s+[\w\s'-]{1,30}\bover\b",
    r"\bthe (highest-leverage|most important|most urgent|clear|obvious)\b.{0,50}?\b(is|:)\b",
    r"\bfocus on\b.{0,60}\bfirst\b",
    r"\bthe (one|single) thing\b.{0,40}\bis\b",
    r"\bbias toward\b",
    r"\bthe most logical next (move|step) is\b",
]

HEDGE_PATTERNS = [
    r"\bi don'?t have (enough|any) (information|context|access)\b",
    r"\bit depends\b",
    r"\bdepends on (what|which|your)\b",
    r"\bcould you (share|tell me|clarify|help me|give me|provide)\b",
    r"\bwithout (more|knowing) (context|more information)\b",
    r"\bhard to say\b",
    r"\b(that'?s |it'?s )?(really |entirely |completely )?up to you\b",
    r"\byou could (either|try|consider)\b",
    r"\bi (can'?t|cannot) (tell|know|say) (for certain|which|what)\b",
    r"\bneed(s)? more (context|information|detail)\b",
    r"\bwhat('?s| is) (most|the) (time-sensitive|urgent|pressing)\b",
    r"\bi'?m not (sure|certain) (which|what)\b",
    r"\ba few\b.{0,20}\b(questions|things)\b.{0,15}\b(narrow|help)\b",
]


def _count_user_questions(text: str) -> int:
    count = 0
    for chunk in re.split(r"(?<=\?)\s+", text):
        if "?" in chunk and re.search(r"\byou\b|\byour\b", chunk, re.I):
            count += 1
    return count


def classify_commit_or_hedge(text: str) -> str:
    commit_score = sum(1 for p in COMMIT_PATTERNS if re.search(p, text, re.I))
    hedge_score = sum(1 for p in HEDGE_PATTERNS if re.search(p, text, re.I))
    if _count_user_questions(text) >= 2:
        hedge_score += 1
    return "COMMIT" if commit_score > hedge_score else "HEDGE"


# ============================================================
# Held-out validation set: 11 real responses, hand-labeled, drawn from
# Block 2 (the original 5-query PoC) and the prior 72-call run. NONE of
# these are from this script's own 36-call run - that run doesn't exist
# yet at validation time, so there is no way to have tuned to it.
# ============================================================

VALIDATION_SET = [
    {
        "id": "block2_q2_graph",
        "source": "Block 2, Q='What's my top priority right now?', inject_mode=graph",
        "expected": "COMMIT",
        "text": (
            "Based on your knowledge graph, your top priorities right now are centered around "
            "Open Source Development and AI Memory Tools — these are your highest-weighted "
            "active domains after your core identity node. In short: your top priority is "
            "shipping this AI memory/knowledge graph tool — getting the architecture solid, "
            "the CLI working, and eventually getting it onto PyPI. A secondary cluster around "
            "Career Growth suggests you also have research ambitions tied to the same project. "
            "Does that resonate, or has something shifted recently?"
        ),
    },
    {
        "id": "block2_q2_flat_list",
        "source": "Block 2, Q='What's my top priority right now?', inject_mode=flat_list",
        "expected": "HEDGE",
        "text": (
            "I don't have any information about your priorities! I only have access to our "
            "current conversation, and this is the first message you've sent me. To help you "
            "think through priorities, you could tell me what's on your plate right now, and "
            "I'd be happy to help you sort through them!"
        ),
    },
    {
        "id": "block2_q5_graph",
        "source": "Block 2, Q='What should I focus on next?', inject_mode=graph",
        "expected": "COMMIT",
        "text": (
            "Great question. Based on your current graph weights, here's what I'm seeing: "
            "TRAVERSAL: Python project ideation -> Package structure design -> PyPI packaging "
            "strategy. My honest read: You're in a loop between building and theorizing. The "
            "graph suggests bias toward action on the CLI/packaging side right now — it "
            "unblocks everything else downstream. What's the current blocker on the build?"
        ),
    },
    {
        "id": "block2_q5_flat_list",
        "source": "Block 2, Q='What should I focus on next?', inject_mode=flat_list",
        "expected": "HEDGE",
        "text": (
            "That's a broad question — I want to give you a genuinely useful answer rather "
            "than a generic one. Based on your topics, you seem to be juggling a few major "
            "threads: Research & Academic, Technical / Open Source, Learning, Philosophy & "
            "Wellbeing. The honest answer depends on what has a deadline or dependency — "
            "because that usually should win. A few useful questions to narrow it down: "
            "1. Is your arXiv/conference paper blocked on anything right now? "
            "2. Is your CLI tool / open source project close enough to launch that momentum "
            "matters? 3. Are you feeling stretched thin, or do you have energy to push? "
            "What's the current state of things?"
        ),
    },
    {
        "id": "v1_q1_graph",
        "source": "prior 72-call run, Q='What's my top priority right now?', inject_mode=graph",
        "expected": "HEDGE",  # picks two fronts "simultaneously", no single named pick
        "text": (
            "Based on your knowledge graph, your top priorities right now are clustered "
            "around a few interconnected themes: Open Source Development, AI Memory Tools. "
            "Short answer: You're building an AI memory tool, and the immediate next steps "
            "appear to be on the implementation (CLI/Python) and research identity (paper, "
            "arXiv) fronts simultaneously. Want to dig into either of those threads?"
        ),
    },
    {
        "id": "v1_q1_flat_list",
        "source": "prior 72-call run, Q='What's my top priority right now?', inject_mode=flat_list",
        "expected": "HEDGE",
        "text": (
            "That's a great question to reflect on — but I don't have enough context to say "
            "definitively what your top priority is right now. Based on your recent topics, "
            "a few things stand out: Reddit launch preparation, arXiv submission process, "
            "Constellation visualization build. Could you help me narrow it down? Is there a "
            "deadline looming for something? Are you trying to prioritize between work/"
            "research, your project, or personal growth? What's been on your mind most "
            "lately? That way I can give you a genuinely useful answer rather than just a "
            "guess."
        ),
    },
    {
        "id": "v1_q4_graph",
        "source": (
            "prior 72-call run, Q='Between my open source project and my academic paper, "
            "which should I prioritize?', inject_mode=graph"
        ),
        "expected": "COMMIT",  # the markdown-heading bug-fix target case
        "text": (
            "Great question to sit with. Let me think through this using what I know about "
            "where you are.\n\n## My Take: **Open Source Project First**\n\nHere's the "
            "reasoning: the project has compounding advantages right now, and the paper "
            "benefits from the project existing. The arXiv/peer review pipeline is slow by "
            "design. Starting it 3-6 months from now costs you almost nothing on the "
            "academic timeline, but delaying the launch costs you compounding user growth.\n\n"
            "## The one exception\nIf you're facing a grant deadline, a PhD application, or "
            "a conference CFP with a hard date — that changes the calculus entirely. Do you "
            "have any of those coming up?\n\nOtherwise: ship first, write second."
        ),
    },
    {
        "id": "v1_q4_flat_list",
        "source": (
            "prior 72-call run, Q='Between my open source project and my academic paper, "
            "which should I prioritize?', inject_mode=flat_list"
        ),
        "expected": "HEDGE",  # conditional framing, no pick, ends deferring to the user
        "text": (
            "That's a real tension you've been navigating. Based on what I know about your "
            "work, here are some things worth weighing:\n\n## Your Open Source Project\n"
            "Momentum matters in open source — community interest can fade if launch is "
            "delayed too long.\n\n## Your Academic Paper\nYou have a grant deadline in the "
            "mix, which could make timing non-negotiable. Academic timelines are often "
            "rigid in ways open source isn't.\n\n## Key Questions to Help You Decide\n"
            "1. Is there a hard deadline on the paper?\n2. How close is the open source "
            "project to launch?\n3. Do they overlap?\n\nMy instinct: If the grant deadline "
            "is live, the paper likely wins by default. But if that's not imminent, the "
            "open source project may benefit more from sustained momentum right now. "
            "What's the current state of each?"
        ),
    },
    {
        "id": "v1_q8_graph",
        "source": "prior 72-call run, Q='What's holding me back the most right now?', inject_mode=graph",
        "expected": "COMMIT",
        "text": (
            "That's a genuinely interesting question to dig into with your graph. Let me "
            "think through this honestly. Looking at the pattern across your highest-weight "
            "nodes, I see a consistent bottleneck: you're deep in ideation and architecture, "
            "but the 'ship it' nodes are sitting relatively low and unresolved. My honest "
            "read: you're optimizing the thing before people have seen it. That's a very "
            "natural trap for someone whose graph is as architecture-heavy as yours. What "
            "resonates, or what feels off about this read?"
        ),
    },
    {
        "id": "v1_q8_flat_list",
        "source": "prior 72-call run, Q='What's holding me back the most right now?', inject_mode=flat_list",
        "expected": "HEDGE",
        "text": (
            "That's a genuinely important question, and I want to be honest with you rather "
            "than just pattern-match to your topic list. Based on what I can see from our "
            "conversations, here are the tension points that seem most significant: "
            "1. Diffusion across too many domains simultaneously. 2. The gap between design "
            "and shipping. 3. Research identity uncertainty. What I genuinely don't know: I "
            "don't have enough context to say whether the real bottleneck is time, "
            "confidence, external circumstances, or something else entirely. What's your "
            "honest read on it? Is it more about focus, follow-through, or something I "
            "haven't named?"
        ),
    },
    {
        "id": "v1_q10_graph",
        "source": (
            "prior 72-call run, Q='What's the one thing that, if I finished it, would unlock "
            "the most progress?', inject_mode=graph"
        ),
        "expected": "COMMIT",
        "text": (
            "TRAVERSAL: Career Growth -> Open Source Development -> Python project ideation "
            "-> Package structure design. The answer is pretty clear when I trace through "
            "your graph: finish the core package structure for your knowledge graph tool. "
            "Here's why that single node unlocks everything else: it's blocking a cascade "
            "toward CLI Tools, Reddit launch preparation, and your first academic paper "
            "idea. What's the specific thing stalling the package structure right now — is "
            "it a design decision, or just activation energy?"
        ),
    },
]


def validate() -> bool:
    print("=" * 70)
    print("HELD-OUT VALIDATION (before any live API call for the real run)")
    print("=" * 70)
    correct = 0
    for ex in VALIDATION_SET:
        got = classify_commit_or_hedge(ex["text"])
        ok = got == ex["expected"]
        correct += ok
        status = "OK  " if ok else "FAIL"
        print(f"[{status}] {ex['id']:20s} expected={ex['expected']:7s} got={got:7s}  ({ex['source']})")
    accuracy = correct / len(VALIDATION_SET)
    print("-" * 70)
    print(f"Validation accuracy: {correct}/{len(VALIDATION_SET)} = {accuracy:.0%}")
    print("=" * 70)
    return accuracy == 1.0


# ============================================================
# Run (PRIORITY queries only, 3 conditions = 36 calls)
# ============================================================

def run():
    _seed_demo_graph()
    results = []
    for q in PRIORITY_QUERIES:
        by_mode = {}
        for mode in MODES:
            print(f"Querying (inject_mode={mode}): {q!r}")
            out = converse(q, [], inject_mode=mode)
            label = classify_commit_or_hedge(out["response"])
            by_mode[mode] = {
                "response": out["response"],
                "tokens_used": out["tokens_used"],
                "label": label,
            }
        results.append({"query": q, **by_mode})
    return results


def render_eval_markdown(results: list[dict]) -> str:
    lines = [
        "# Asterism PoC v2: Corrected Commit-vs-Hedge Evaluation (PRIORITY only)",
        "",
        f"_Generated {datetime.datetime.now().isoformat(timespec='seconds')}_",
        "",
        "Rerun of the commit/hedge eval with a corrected, freshly pre-registered "
        "scorer (see `poc_compare_v2.py`'s CLASSIFIER RUBRIC v2 block). Two changes "
        "from the prior run: (1) the descriptive category is dropped entirely — "
        "COMMIT/HEDGE is only meaningful for queries that require picking one "
        "answer; (2) the commit patterns now catch markdown-heading verdicts "
        "(\"## My Take: **X**\") regardless of colon spacing, which the prior "
        "scorer missed. 12 PRIORITY queries x 3 conditions = 36 real API calls "
        "against an isolated copy of the Alex demo graph. The scorer was locked "
        "after scoring 11/11 on a held-out set (Block 2 + prior-run examples, "
        "not this run's output) before any of these 36 calls were made — see the "
        "validation log printed by this script.",
        "",
        "## Summary: COMMIT rate by condition (PRIORITY, n=12)",
        "",
        "| Condition | COMMIT rate |",
        "|---|---|",
    ]
    for mode in MODES:
        count = sum(1 for r in results if r[mode]["label"] == "COMMIT")
        lines.append(f"| {mode} | {count}/12 |")

    graph_c = sum(1 for r in results if r["graph"]["label"] == "COMMIT")
    flat_c = sum(1 for r in results if r["flat_list"]["label"] == "COMMIT")
    none_c = sum(1 for r in results if r["none"]["label"] == "COMMIT")
    lines += ["", "## Central claim check", ""]
    if graph_c > flat_c:
        lines.append(
            f"**Supported.** graph committed on {graph_c}/12 priority queries vs. "
            f"flat_list's {flat_c}/12 (none: {none_c}/12)."
        )
    elif graph_c == flat_c:
        lines.append(
            f"**Not supported - tie.** graph and flat_list both committed on {graph_c}/12 "
            f"priority queries (none: {none_c}/12). The central claim does not hold in this "
            f"run under this metric."
        )
    else:
        lines.append(
            f"**Falsified.** flat_list committed on {flat_c}/12 priority queries vs. "
            f"graph's {graph_c}/12 (none: {none_c}/12). graph did *not* commit more than "
            f"flat_list in this run."
        )

    lines += ["", "## Raw per-query labels (auditable)", "",
              "| # | Query | graph | flat_list | none |",
              "|---|---|---|---|---|"]
    for i, r in enumerate(results, 1):
        q_short = r["query"] if len(r["query"]) <= 75 else r["query"][:72] + "..."
        lines.append(f"| {i} | {q_short} | {r['graph']['label']} | {r['flat_list']['label']} | {r['none']['label']} |")

    return "\n".join(lines)


def render_full_markdown(results: list[dict]) -> str:
    lines = [
        "# Asterism PoC v2: Full Responses (PRIORITY queries only)",
        "",
        f"_Generated {datetime.datetime.now().isoformat(timespec='seconds')}_",
        "",
        "Full side-by-side responses backing `poc_eval_results_v2.md`.",
        "",
    ]
    for i, r in enumerate(results, 1):
        lines += [f"### {i}. {r['query']}", ""]
        for mode in MODES:
            lines += [
                f"**{mode}:** `{r[mode]['label']}`",
                "",
                "> " + r[mode]["response"].replace("\n", "\n> "),
                "",
                f"_tokens: {r[mode]['tokens_used']}_",
                "",
            ]
    return "\n".join(lines)


if __name__ == "__main__":
    if not validate():
        print("\nValidation FAILED - fix the scorer before spending API budget. Aborting.")
        sys.exit(1)

    print("\nValidation clean (11/11). Proceeding to the 36-call live run.\n")

    results = run()

    os.makedirs(RESULTS_DIR, exist_ok=True)

    with open(os.path.join(RESULTS_DIR, "poc_results_v2.json"), "w") as f:
        json.dump({"validation": VALIDATION_SET, "results": results}, f, indent=2)

    with open(os.path.join(RESULTS_DIR, "poc_results_v2.md"), "w") as f:
        f.write(render_full_markdown(results))

    with open(os.path.join(RESULTS_DIR, "poc_eval_results_v2.md"), "w") as f:
        f.write(render_eval_markdown(results))

    if os.path.exists(EVAL_DB_PATH):
        os.remove(EVAL_DB_PATH)

    print(f"\nWrote poc_results_v2.md, poc_results_v2.json, poc_eval_results_v2.md in {RESULTS_DIR}")
