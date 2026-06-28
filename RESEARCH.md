# Asterism — Research Contributions & Priority Record

**Author:** Bidit Das  
**GitHub:** https://github.com/biditdas18/asterism  
**First public commit:** June 28, 2026  
**License:** MIT  

---

## Overview

Asterism is a local-first personal knowledge graph that 
automatically constructs itself from LLM conversation 
exports and renders as an interactive star constellation.

This document establishes priority for five novel 
contributions introduced in this system.

---

## Novel Contributions

### 1. Hebbian Knowledge Graph for Personal AI Memory

Edges between concept nodes strengthen when traversed 
by LLM queries during a session (weight += 0.2 per 
traversal). Unused paths accumulate session exposure 
time and decay below a pruning threshold, disappearing 
from the graph entirely.

Inspired by Hebb (1949): "Neurons that fire together 
wire together." Applied here to human-LLM conversational 
data for the first time.

### 2. Session-Based TTL Decay

Decay counts only active session time, not wall-clock 
time. A node used yesterday but not today does not decay 
during the user's absence — only during active sessions 
where it was not traversed.

This mirrors biological memory consolidation during rest 
periods. Explicit design decision distinguishing Asterism 
from naive timestamp-based decay systems.

### 3. Four-Mechanic Biological Memory Model

A unified implementation of four neuroscience-inspired 
graph mechanics:

- **Hebbian strengthening** — traversed paths reinforce
- **Synaptic pruning** — unused nodes decay and disappear
- **Pathway optimization** — efficient shortcuts emerge 
  from usage patterns; competing paths resolved by weight
- **Chain healing** — graph integrity self-maintains 
  after node pruning via automatic bridge edge creation
- **Orphan rescue** — disconnected nodes bridged to 
  nearest semantically similar connected node via 
  Jaccard word-overlap scoring

No prior personal knowledge management system implements 
all four mechanics as a unified architecture.

### 4. Graph-as-Weighted-Index over LLM Flat Memory

Core architectural insight: LLM memory summaries 
(e.g. Claude's userMemories) function as an unindexed 
heap — flat text with no relational structure or 
priority weighting.

Asterism's knowledge graph functions as a B-tree 
equivalent over this heap:
- High-weight nodes = high-priority index entries
- Decayed nodes = removed index entries (underlying 
  memory data persists; retrieval priority removed)
- Graph traversal = query planning over memory space
- Hebbian decay = LRU-equivalent cache eviction policy

This framing — personal knowledge graph as weighted 
retrieval index over LLM memory — is novel and 
unimplemented in any prior system as of June 2026.

### 5. Automated Priority Inference from Conversational Data

The system infers what matters most to the user 
automatically from conversation history without 
explicit user declaration.

Signal: recency × frequency × co-occurrence → node weight

Result: high-weight nodes accurately reflect current 
user priorities. Fading nodes reflect declining interest.
Validated by: user inspection of rendered constellation 
matching self-reported priorities.

### 6. Causal Chain Topology

Conversations organized as directed causal chains 
representing evolution of thought over time, not flat 
topic clusters.

Chronological ordering of conversation exports preserves 
ideation trajectory. LLM clustering identifies causal 
relationships between conversations (A led to B led to C) 
rather than mere topical similarity.

Result: the graph encodes not just what the user thinks 
about, but how their thinking evolved.

---

## Prior Art Statement

To the best of the author's knowledge, no prior system 
implements the combination of contributions 2-6 applied 
to human-LLM conversational data as of the date of this 
commit.

Related but distinct prior work:
- Personal knowledge graphs (PKG): static, manually 
  populated, no decay mechanics
- RAG memory systems: similarity-based retrieval, 
  no temporal decay or causal structure
- Vector databases: distance-based indexing, no 
  Hebbian strengthening or biological decay
- Mem0, MemGPT: agent memory systems, no visual 
  constellation render, no session-based TTL, 
  no causal chain topology

---

## Citation

If you build on this work, please cite:

Bidit Das. "Asterism: A Hebbian Knowledge Graph as 
Weighted Retrieval Index for Personal LLM Memory." 
GitHub repository, June 2026. 
https://github.com/biditdas18/asterism

A formal arXiv preprint is in preparation.

---

*This document was committed on June 28, 2026 to 
establish public priority for the contributions 
described above.*
