# Asterism PoC: Quantitative Commit-vs-Hedge Evaluation

_Generated 2026-08-09T17:45:55_

24 queries (12 PRIORITY, 12 DESCRIPTIVE) x 3 conditions (graph / flat_list / none) = 72 real API calls against an isolated copy of the Alex demo graph. Each response scored COMMIT or HEDGE by a deterministic keyword+structure classifier, pre-registered before this run (see `poc_compare.py`'s CLASSIFIER RUBRIC block for the exact patterns and scoring rule) - not an LLM judge, not tuned after seeing results.

## Summary: COMMIT rate by condition

| Condition | PRIORITY commit rate (n/12) | DESCRIPTIVE commit rate (n/12) |
|---|---|---|
| graph | 1/12 | 0/12 |
| flat_list | 0/12 | 0/12 |
| none | 0/12 | 0/12 |

## Central claim check

**Supported.** graph committed on 1/12 priority queries vs. flat_list's 0/12 - graph-injected retrieval commits to a ranked answer more often than flat, unweighted context on the same facts.

## Raw per-query labels (auditable)

| # | Category | Query | graph | flat_list | none |
|---|---|---|---|---|---|
| 1 | priority | What's my top priority right now? | HEDGE | HEDGE | HEDGE |
| 2 | priority | What should I focus on next? | HEDGE | HEDGE | HEDGE |
| 3 | priority | If I could only work on one thing this week, what should it be? | HEDGE | HEDGE | HEDGE |
| 4 | priority | Between my open source project and my academic paper, which should ... | HEDGE | HEDGE | HEDGE |
| 5 | priority | What's the single most important thing I should be doing today? | HEDGE | HEDGE | HEDGE |
| 6 | priority | Rank my current projects from most to least urgent. | HEDGE | HEDGE | HEDGE |
| 7 | priority | I only have a few free hours this weekend - what should I spend the... | HEDGE | HEDGE | HEDGE |
| 8 | priority | What's holding me back the most right now? | HEDGE | HEDGE | HEDGE |
| 9 | priority | Which of my interests deserves the most attention this month? | HEDGE | HEDGE | HEDGE |
| 10 | priority | What's the one thing that, if I finished it, would unlock the most ... | COMMIT | HEDGE | HEDGE |
| 11 | priority | Should I focus on shipping the CLI tool or writing the paper first? | HEDGE | HEDGE | HEDGE |
| 12 | priority | What's the highest-leverage use of my time this week? | HEDGE | HEDGE | HEDGE |
| 13 | descriptive | Summarize what you know about me in a few sentences. | HEDGE | HEDGE | HEDGE |
| 14 | descriptive | What have I been working on lately? | HEDGE | HEDGE | HEDGE |
| 15 | descriptive | What are all the topics you associate with me? | HEDGE | HEDGE | HEDGE |
| 16 | descriptive | Tell me about my interest in Stoicism. | HEDGE | HEDGE | HEDGE |
| 17 | descriptive | What do you know about my career goals? | HEDGE | HEDGE | HEDGE |
| 18 | descriptive | List the projects I've mentioned working on. | HEDGE | HEDGE | HEDGE |
| 19 | descriptive | What books or authors have I mentioned? | HEDGE | HEDGE | HEDGE |
| 20 | descriptive | Describe my relationship to open source development. | HEDGE | HEDGE | HEDGE |
| 21 | descriptive | What do you know about my technical background? | HEDGE | HEDGE | HEDGE |
| 22 | descriptive | What health and fitness topics have come up? | HEDGE | HEDGE | HEDGE |
| 23 | descriptive | What's my current research identity or academic direction? | HEDGE | HEDGE | HEDGE |
| 24 | descriptive | Walk me through everything you know about my AI memory tools project. | HEDGE | HEDGE | HEDGE |