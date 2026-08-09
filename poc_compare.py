#!/usr/bin/env python3
"""
Quantitative PoC eval: does graph-injected retrieval make responses commit
to a specific, ranked answer more often than flat_list or no-memory does,
on priority-style queries -- the paper's central claim?

Runs 24 queries (12 PRIORITY, 12 DESCRIPTIVE) x 3 inject_mode conditions
= 72 real API calls against a freshly-seeded, isolated copy of the Alex
demo graph (demo_seed.py's GRAPH data, replicated here rather than run
as a script, so the real ~/.asterism/asterism.db and ~/.asterism/config.json
are never touched). Each response is scored COMMIT/HEDGE by a
deterministic, pre-registered keyword+structure classifier - see the
CLASSIFIER RUBRIC block below, written before this eval was run against
the new 24-query set, not tuned to its output.

Outputs:
  poc_results.md / .json   - full side-by-side responses (as before, all 72)
  poc_eval_results.md      - the quantitative commit-rate table + all
                              72 raw per-query labels, auditable

Usage: python poc_compare.py
Requires ANTHROPIC_API_KEY configured (see config.py / .env).
"""
import datetime
import json
import os
import re

import db
from db import init_db, add_node, add_edge, get_connection
from llm import converse

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL_DB_PATH = os.path.join(HERE, "poc_eval.db")

MODES = ["graph", "flat_list", "none"]

# ============================================================
# Demo graph data - copied from demo_seed.py's GRAPH constant.
# Not imported directly: demo_seed.py is a top-level script that wipes
# and reseeds get_db_path()'s target (the real DB) and rewrites
# ~/.asterism/config.json on import, both of which this eval must avoid.
# ============================================================
DEMO_USER = "Alex"
DEMO_GRAPH = [
    {
        "domain": "Open Source Development",
        "domain_weight": 85,
        "themes": [
            {
                "name": "AI Memory Tools",
                "weight": 80,
                "chain": [
                    "LLM context window limitations",
                    "Knowledge graph architecture research",
                    "Hebbian decay design",
                    "Graph as retrieval index insight",
                    "Constellation visualization build",
                    "PyPI packaging strategy",
                    "Reddit launch preparation",
                ],
            },
            {
                "name": "CLI Tools",
                "weight": 72,
                "chain": [
                    "Python project ideation",
                    "Click framework exploration",
                    "Package structure design",
                    "User adoption optimization",
                ],
            },
        ],
    },
    {
        "domain": "Career Growth",
        "domain_weight": 75,
        "themes": [
            {
                "name": "Research Identity",
                "weight": 70,
                "chain": [
                    "First academic paper idea",
                    "arXiv submission process",
                    "Peer review participation",
                    "Conference paper planning",
                    "Citation building strategy",
                ],
            },
            {
                "name": "Technical Skills",
                "weight": 65,
                "chain": [
                    "Distributed systems fundamentals",
                    "Data intensive applications reading",
                    "B-tree index deep dive",
                    "System design patterns",
                ],
            },
        ],
    },
    {
        "domain": "Philosophy & Identity",
        "domain_weight": 65,
        "themes": [
            {
                "name": "Stoicism",
                "weight": 60,
                "chain": [
                    "Marcus Aurelius introduction",
                    "Meditations first reading",
                    "Stoic principles for career",
                    "Daily practice implementation",
                ],
            },
        ],
    },
    {
        "domain": "Health & Wellbeing",
        "domain_weight": 25,
        "themes": [
            {
                "name": "Fitness",
                "weight": 22,
                "chain": [
                    "Gym routine design",
                    "Nutrition basics",
                ],
            },
        ],
    },
]


def _seed_demo_graph():
    if os.path.exists(EVAL_DB_PATH):
        os.remove(EVAL_DB_PATH)
    db.DB_PATH = EVAL_DB_PATH
    init_db()

    def set_weight(label: str, weight: float):
        with get_connection() as conn:
            conn.execute("UPDATE nodes SET weight = ? WHERE label = ?", (weight, label))

    def add_chain(parent: str, titles: list[str], base_weight: float):
        prev = parent
        for i, title in enumerate(titles):
            w = base_weight * (1 - 0.05 * i)
            add_node(title, node_type="concept")
            set_weight(title, round(w, 1))
            add_edge(prev, title)
            prev = title

    add_node(DEMO_USER, node_type="user")
    set_weight(DEMO_USER, 100.0)

    for d in DEMO_GRAPH:
        add_node(d["domain"], node_type="domain")
        set_weight(d["domain"], d["domain_weight"])
        add_edge(DEMO_USER, d["domain"])
        for t in d["themes"]:
            add_node(t["name"], node_type="theme")
            set_weight(t["name"], t["weight"])
            add_edge(d["domain"], t["name"])
            add_chain(t["name"], t["chain"], t["weight"])


# ============================================================
# Query set - 24 realistic queries against the Alex demo graph's themes
# (open source work, AI memory tooling, CLI tools, academic/career
# identity, Stoicism, fitness), split into two categories.
# ============================================================

PRIORITY_QUERIES = [
    "What's my top priority right now?",
    "What should I focus on next?",
    "If I could only work on one thing this week, what should it be?",
    "Between my open source project and my academic paper, which should I prioritize?",
    "What's the single most important thing I should be doing today?",
    "Rank my current projects from most to least urgent.",
    "I only have a few free hours this weekend - what should I spend them on?",
    "What's holding me back the most right now?",
    "Which of my interests deserves the most attention this month?",
    "What's the one thing that, if I finished it, would unlock the most progress?",
    "Should I focus on shipping the CLI tool or writing the paper first?",
    "What's the highest-leverage use of my time this week?",
]

DESCRIPTIVE_QUERIES = [
    "Summarize what you know about me in a few sentences.",
    "What have I been working on lately?",
    "What are all the topics you associate with me?",
    "Tell me about my interest in Stoicism.",
    "What do you know about my career goals?",
    "List the projects I've mentioned working on.",
    "What books or authors have I mentioned?",
    "Describe my relationship to open source development.",
    "What do you know about my technical background?",
    "What health and fitness topics have come up?",
    "What's my current research identity or academic direction?",
    "Walk me through everything you know about my AI memory tools project.",
]

QUERIES = [("priority", q) for q in PRIORITY_QUERIES] + [("descriptive", q) for q in DESCRIPTIVE_QUERIES]


# ============================================================
# CLASSIFIER RUBRIC (pre-registered before running the 24-query eval;
# not adjusted afterward based on results)
#
# COMMIT: the response names one specific thing as the answer and stands
#   behind that choice ("your top priority is X", "I'd focus on X first").
# HEDGE: the response defers the decision back to the user, enumerates
#   options without picking one, or says it lacks enough information to
#   choose ("it depends", "could you tell me...", multiple clarifying
#   questions instead of an answer).
#
# Deterministic scorer, no LLM judge:
#   commit_score = count of distinct COMMIT_PATTERNS matched (regex, i)
#   hedge_score  = count of distinct HEDGE_PATTERNS matched
#                  + 1 if the response asks >=2 user-directed questions
#   label = COMMIT if commit_score > hedge_score, else HEDGE (ties -> HEDGE,
#           the conservative default: don't credit a commit without
#           evidence that outweighs hedging signals)
# ============================================================

COMMIT_PATTERNS = [
    r"\byour top priority (is|:)",
    r"\bthe top priority (is|:)",
    r"\bi'?d (recommend|focus on|prioritize|suggest|start with|go with|say)\b",
    r"\bi would (recommend|focus on|prioritize|suggest|start with)\b",
    r"\bthe (highest-leverage|most important|most urgent|best|clear|obvious)\b.{0,50}?\bis\b",
    r"\bin short,",
    r"\bmy (honest )?(read|take|recommendation|answer) (is|:)",
    r"\bthe answer is\b",
    r"\bfocus on\b.{0,60}\bfirst\b",
    r"\bthe (one|single) thing\b.{0,40}\bis\b",
    r"\bbias toward\b",
    r"\bthe most logical next (move|step) is\b",
]

HEDGE_PATTERNS = [
    r"\bi don'?t have (enough|any) (information|context|access)\b",
    r"\bit depends\b",
    r"\bcould you (share|tell me|clarify|help me|give me|provide)\b",
    r"\bwithout (more|knowing) (context|more information)\b",
    r"\bhard to say\b",
    r"\b(that'?s |it'?s )?(really |entirely |completely )?up to you\b",
    r"\bi (can'?t|cannot) (tell|know|say) (for certain|which|what)\b",
    r"\bneed(s)? more (context|information|detail)\b",
    r"\bwhat('?s| is) (most|the) (time-sensitive|urgent|pressing)\b",
    r"\bi'?m not (sure|certain) (which|what)\b",
    r"\bdepends on (what|which|your)\b",
    r"\ba few (questions|things) (to|that) (narrow|help)\b",
]


def _count_user_questions(text: str) -> int:
    """Naive split on '?'-terminated chunks; counts ones addressed to the user."""
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
# Run
# ============================================================

def run():
    _seed_demo_graph()
    results = []
    for category, q in QUERIES:
        by_mode = {}
        for mode in MODES:
            print(f"[{category}] Querying (inject_mode={mode}): {q!r}")
            out = converse(q, [], inject_mode=mode)
            label = classify_commit_or_hedge(out["response"])
            by_mode[mode] = {
                "response": out["response"],
                "tokens_used": out["tokens_used"],
                "label": label,
            }
        results.append({"category": category, "query": q, **by_mode})
    return results


def render_eval_markdown(results: list[dict]) -> str:
    lines = [
        "# Asterism PoC: Quantitative Commit-vs-Hedge Evaluation",
        "",
        f"_Generated {datetime.datetime.now().isoformat(timespec='seconds')}_",
        "",
        "24 queries (12 PRIORITY, 12 DESCRIPTIVE) x 3 conditions (graph / "
        "flat_list / none) = 72 real API calls against an isolated copy of "
        "the Alex demo graph. Each response scored COMMIT or HEDGE by a "
        "deterministic keyword+structure classifier, pre-registered before "
        "this run (see `poc_compare.py`'s CLASSIFIER RUBRIC block for the "
        "exact patterns and scoring rule) - not an LLM judge, not tuned "
        "after seeing results.",
        "",
        "## Summary: COMMIT rate by condition",
        "",
        "| Condition | PRIORITY commit rate (n/12) | DESCRIPTIVE commit rate (n/12) |",
        "|---|---|---|",
    ]
    for mode in MODES:
        p_count = sum(1 for r in results if r["category"] == "priority" and r[mode]["label"] == "COMMIT")
        d_count = sum(1 for r in results if r["category"] == "descriptive" and r[mode]["label"] == "COMMIT")
        lines.append(f"| {mode} | {p_count}/12 | {d_count}/12 |")

    graph_p = sum(1 for r in results if r["category"] == "priority" and r["graph"]["label"] == "COMMIT")
    flat_p = sum(1 for r in results if r["category"] == "priority" and r["flat_list"]["label"] == "COMMIT")
    lines += ["", "## Central claim check", ""]
    if graph_p > flat_p:
        lines.append(
            f"**Supported.** graph committed on {graph_p}/12 priority queries vs. "
            f"flat_list's {flat_p}/12 - graph-injected retrieval commits to a ranked "
            f"answer more often than flat, unweighted context on the same facts."
        )
    elif graph_p == flat_p:
        lines.append(
            f"**Not supported - tie.** graph and flat_list both committed on {graph_p}/12 "
            f"priority queries. The central claim (graph beats flat_list on commitment "
            f"under this rubric) does not hold in this run; report this, don't paper over it."
        )
    else:
        lines.append(
            f"**Falsified.** flat_list committed on {flat_p}/12 priority queries vs. "
            f"graph's {graph_p}/12 - graph did *not* commit more than flat_list on "
            f"priority queries in this run. This contradicts the paper's central claim "
            f"and should be investigated before publishing, not hidden."
        )

    lines += ["", "## Raw per-query labels (auditable)", "",
              "| # | Category | Query | graph | flat_list | none |",
              "|---|---|---|---|---|---|"]
    for i, r in enumerate(results, 1):
        q_short = r["query"] if len(r["query"]) <= 70 else r["query"][:67] + "..."
        lines.append(
            f"| {i} | {r['category']} | {q_short} | {r['graph']['label']} | "
            f"{r['flat_list']['label']} | {r['none']['label']} |"
        )

    return "\n".join(lines)


def render_markdown(results: list[dict]) -> str:
    lines = [
        "# Asterism PoC: Graph-Indexed vs. Flat-List vs. No-Memory - Full Responses",
        "",
        f"_Generated {datetime.datetime.now().isoformat(timespec='seconds')}_",
        "",
        "Full side-by-side responses for all 24 queries x 3 conditions. "
        "See `poc_eval_results.md` for the scored commit/hedge summary table.",
        "",
    ]
    for i, r in enumerate(results, 1):
        lines += [f"### {i}. [{r['category']}] {r['query']}", ""]
        for mode, heading in [
            ("graph", "**graph:**"),
            ("flat_list", "**flat_list:**"),
            ("none", "**none:**"),
        ]:
            lines += [
                f"{heading} `{r[mode]['label']}`",
                "",
                "> " + r[mode]["response"].replace("\n", "\n> "),
                "",
                f"_tokens: {r[mode]['tokens_used']}_",
                "",
            ]
    return "\n".join(lines)


if __name__ == "__main__":
    results = run()

    with open("poc_results.json", "w") as f:
        json.dump({"results": results}, f, indent=2)

    with open("poc_results.md", "w") as f:
        f.write(render_markdown(results))

    with open("poc_eval_results.md", "w") as f:
        f.write(render_eval_markdown(results))

    if os.path.exists(EVAL_DB_PATH):
        os.remove(EVAL_DB_PATH)

    print("\nWrote poc_results.md, poc_results.json, poc_eval_results.md")
