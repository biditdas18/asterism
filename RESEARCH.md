# Asterism — Development Record & Research Notes

**Author:** Bidit Das  
**GitHub:** https://github.com/biditdas18/asterism  
**First public commit:** June 28, 2026  
**License:** MIT  

---

## Overview

Asterism is a local-first personal knowledge graph that automatically
constructs itself from LLM conversation exports and renders as an
interactive star constellation.

This document is a dated record of what the system does and when each
part was built. It is a companion to the workshop paper
([`papers/asterism.tex`](papers/asterism.tex); an SSRN preprint is also
available), which is the authoritative source for anything empirical —
where this document and the paper disagree, the paper's numbers and
scoping win. Claims here about how the system compares to prior work are
deliberately scoped to what has actually been checked against named
systems, not asserted as established firsts; the paper's Related Work
section is the more careful version of that comparison and should be
read alongside this one.

---

## Components

### 1. Weighted Graph with Hebbian-Style Strengthening

Edges between concept nodes increment in weight when traversed by an
LLM query during a session (`weight += 0.2` per traversal). Paths that
go unused accumulate session exposure time and are pruned once that
exposure crosses a threshold, removing them from the graph.

The mechanism is edge-weight reinforcement on use plus threshold-based
removal on disuse — a simple, plainly algorithmic rule. We borrow the
name and the motivating intuition from Hebb (1949) and the "fire
together, wire together" phrasing popularized by Shatz (1992); this is
motivation for the design choice, not a claim about biological fidelity
or a claim that the technique itself is new. Applying weight-on-traversal
reinforcement to a personal, conversation-derived graph is the specific
thing being described here, not the reinforcement idea in general.

### 2. Session-Based TTL Decay

Decay counts active session time, not wall-clock time: a node unused
while the user is away does not decay during that absence, only during
active sessions where it goes untraversed. This is an explicit design
choice, made to distinguish "the user stepped away" from "the user
stopped caring" — a distinction a plain timestamp-based TTL cannot make
on its own. It is an engineering decision, not an empirically validated
claim; we have not measured how well it tracks a user's actual declining
interest against a ground truth.

### 3. Graph Maintenance Mechanics

Four maintenance routines run on a decay cycle, described here in plain
algorithmic terms (the biological framing above is motivation for #1
only; these four are graph-maintenance operations):

- **Edge-weight increments** — traversed edges gain weight; this is
  component 1, listed again here because the other three mechanics are
  downstream of it.
- **TTL-based pruning** — nodes/edges that cross their exposure or
  wall-clock threshold are deleted.
- **Bridge creation on pruning ("chain healing")** — when a node with
  both a parent and a child edge is about to be pruned, a direct
  parent→child edge is created first (weight = `min(parent_w, child_w) ×
  0.7`), so removing an intermediate node doesn't disconnect the nodes
  on either side of it. This is a local transitive-closure step over the
  node being removed, not a general transitive-closure computation over
  the whole graph.
- **Path-weight competition** — where both a direct edge A→C and a
  2-hop path A→B→C exist, the mechanic compares the direct edge's weight
  against the average of the two hop weights and adjusts accordingly
  (accelerating B's decay if the direct edge dominates, weakening the
  direct edge otherwise).
- **Orphan reconnection** — nodes with no path back to the user node
  (checked via BFS) are bridged to the most word-overlapping connected
  node (Jaccard similarity on label tokens), or have their decay
  accelerated if no similar node is found.

These are combined in one scheduler (`decay_scheduler.py`). We have not
done a literature search of personal-knowledge-graph or agent-memory
systems broad enough to say how common or uncommon this combination is,
so we make no claim about that here — see the paper's Related Work
section for the comparisons we *have* checked carefully (against Mem0,
MemGPT, and similarity-based retrieval).

### 4. Graph as a Priority Index over Flat LLM Memory

The system's central design claim: an unstructured "memory" summary (the
kind many LLM assistants now persist between sessions) behaves like an
unindexed heap — every fact has equal retrieval priority, and nothing
marks which facts currently matter most. Asterism's weighted graph plays
the role of an index over that heap, in the sense a B-tree indexes an
ordered file: node weight is the index key, high-weight nodes are
high-priority entries, and decay is index eviction, not deletion of the
underlying fact.

This framing is not just descriptive — it makes a falsifiable prediction
that the paper tests directly, now across five retrieval conditions (not
three) and three assistant models (not one), specifically to separate the
value of the *weighted structure* from the value of an explicit
"prioritize and commit" instruction that only the original `graph`
condition happened to carry. Across 5 independent runs of 12
priority-ranking queries each, mean COMMIT rate (of 12):

|                     | graph | flat_list_prioritized | flat_list | graph_neutral | none |
|---------------------|-------|------------------------|-----------|----------------|------|
| claude-sonnet-4-6   | 5.4   | 3.6                    | 3.6       | 8.8            | 0.0  |
| claude-opus-4-8     | 6.2   | 3.6                    | 1.6       | 5.8            | 1.0  |
| gpt-5.5-2026-04-23  | 6.6   | 6.6                    | 7.0       | 6.6            | 2.2  |

Structure alone (`graph_neutral` vs. `flat_list`, no instruction on either
side) shows a real, positive effect for both Claude models (+5.2 sonnet,
+4.2 opus) — that is the part that replicates. GPT-5.5 shows no effect
from either structure or instruction: its four non-`none` conditions are
statistically indistinguishable. A further check (`correctness_analysis.md`)
confirms the added decisiveness is *accurate*, not just confident, for all
three models — though flagged honestly, sonnet's plain `graph` condition
is still wrong more often than not in absolute terms (54%). See the paper
and [`README.md`](README.md#research--evaluation) for the full
methodology, the pre-registered commit/hedge scoring rule, the 11/11
held-out scorer validation, and the κ=0.640 scorer-human agreement check.

### 5. Priority Inference from Conversation History

The system infers what currently matters to the user from conversation
history — recency and frequency of traversal drive node weight — without
requiring the user to declare priorities explicitly.

The claim that this produces *useful* prioritization is the one tested
in component 4 above: the measured effect is that the resulting weights
let the model commit to a ranked answer more often than an unweighted
view of the same facts, and (per the correctness check) commit to the
*correct* answer more often too — not that the weights perfectly track
the user's true priorities, which we have not validated against
independent ground truth.

### 6. Chronological / Causal Conversation Grouping

When importing a conversation export, `crawler.py` prompts an LLM to
group conversation titles into a hierarchy where the leaf-level "chain"
reflects the causal/chronological order conversations occurred in,
rather than grouping by topic similarity alone. The intent is for the
resulting graph to encode something about how the user's thinking
progressed, not only what they discussed. This is implemented but not
independently evaluated — we have not measured how accurately the
LLM-inferred chains match the user's actual reasoning trajectory.

### 7. Entity Resolution and Its Measured Ceiling

Because the graph is populated automatically from extracted triples, the
same concept surfaces under multiple phrasings across sessions
("AI Memory Tools" / "AI memory tooling" / ...), which fragments the
weight signal if left unresolved. Resolution runs in two stages: a
normalized exact/prefix match, then a local embedding-similarity fallback
(compact CPU model, no network calls) for variants that don't share a
prefix.

We measured where the embedding stage stops working rather than assuming
it works: reworded/reordered phrasings that reuse the same vocabulary
score high (0.92–0.98 cosine similarity) and merge correctly, but true
synonym substitution — different words for the same thing, e.g. "LLM
requires GPUs" vs. "Large Language Models need graphics processors" —
scores 0.58–0.80, indistinguishable from genuinely unrelated concepts at
any single threshold. The operating threshold (0.92) is calibrated
conservatively: it eliminates rewording-driven fragmentation but
deliberately does not attempt to merge synonym pairs it cannot reliably
tell apart from merely-related ones. This ceiling is a limitation of the
current unsupervised approach, not a solved problem; closing it would
need a supervised equivalence model or an LLM-based check.

### 8. Fact Supersession

When a new edge contradicts an existing one from the same source with
the same relationship label but a different target (e.g. "uses Postgres"
→ "uses SQLite"), the prior edge is marked superseded by the new one and
its TTL is dropped so it's eligible for pruning rather than lingering
alongside the current fact. Superseded edges are excluded from default
context injection but not deleted — they remain queryable for explicit
"what did I used to think" queries. The rule is scoped narrowly
(same source, same relationship, different target) and does not attempt
open-ended contradiction detection.

Adding this filter to the retrieval read path has a measured cost:
mean retrieval latency increased 12–18% across the benchmarked graph
sizes (e.g. 30.1ms → 35.2ms at ~10,000 nodes) — a real, non-zero cost of
correctness, still well within the interactive budget since retrieval
stays a small fraction of an end-to-end round-trip that includes a model
call.

---

## Relationship to Prior Work

This section names the specific systems we compared against and how;
it is not a claim of exhaustive prior-art review.

- **Mem0, MemGPT** — both are agent/conversational memory systems whose
  primary function is recall and context-window management. Asterism's
  point of difference is emphasis, not existence: it treats
  *prioritization* as the function under test, and the three-condition
  comparison (component 4) is designed specifically to separate that
  from the recall benefit those systems target. Neither, to our
  knowledge, ships a visual constellation render or a session-based
  (as opposed to wall-clock) TTL, but we have not run a feature-by-feature
  audit of either codebase.
- **Retrieval-augmented generation (RAG)** — RAG answers "what is
  relevant to this query" via per-query similarity search. Asterism's
  weighting answers a different question — "what is persistently
  important to this user" — accumulated across sessions rather than
  computed per query. The two are complementary, not competing.
- **Static personal knowledge graphs** — typically manually populated,
  without decay or automatic weight maintenance.
- **Vector databases** — distance-based retrieval, without the
  traversal-strengthening or TTL-decay dynamics described in components
  1–3.

---

## Citation

If you build on this work, please cite:

Bidit Das. "Asterism: A Hebbian-Weighted Knowledge Graph as a Priority
Index over Long-Term LLM Memory." GitHub repository, June 2026.
https://github.com/biditdas18/asterism

A workshop paper draft is included in this repository
([`papers/asterism.tex`](papers/asterism.tex), PDF alongside it), and a
preprint is available via SSRN.

---

*This document's contribution list was first committed on June 28, 2026,
as a dated record of what had been built by that point. It has since
been revised (most recently to align its claims with the workshop
paper's measured results) without altering that original commit date.*
