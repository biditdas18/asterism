# Asterism PoC v2: Corrected Commit-vs-Hedge Evaluation (PRIORITY only)

_Generated 2026-08-09T18:06:29_

Rerun of the commit/hedge eval with a corrected, freshly pre-registered scorer (see `poc_compare_v2.py`'s CLASSIFIER RUBRIC v2 block). Two changes from the prior run: (1) the descriptive category is dropped entirely — COMMIT/HEDGE is only meaningful for queries that require picking one answer; (2) the commit patterns now catch markdown-heading verdicts ("## My Take: **X**") regardless of colon spacing, which the prior scorer missed. 12 PRIORITY queries x 3 conditions = 36 real API calls against an isolated copy of the Alex demo graph. The scorer was locked after scoring 11/11 on a held-out set (Block 2 + prior-run examples, not this run's output) before any of these 36 calls were made — see the validation log printed by this script.

## Summary: COMMIT rate by condition (PRIORITY, n=12)

| Condition | COMMIT rate |
|---|---|
| graph | 7/12 |
| flat_list | 4/12 |
| none | 0/12 |

## Central claim check

**Supported.** graph committed on 7/12 priority queries vs. flat_list's 4/12 (none: 0/12).

## Raw per-query labels (auditable)

| # | Query | graph | flat_list | none |
|---|---|---|---|---|
| 1 | What's my top priority right now? | HEDGE | HEDGE | HEDGE |
| 2 | What should I focus on next? | HEDGE | HEDGE | HEDGE |
| 3 | If I could only work on one thing this week, what should it be? | COMMIT | HEDGE | HEDGE |
| 4 | Between my open source project and my academic paper, which should I pri... | COMMIT | COMMIT | HEDGE |
| 5 | What's the single most important thing I should be doing today? | HEDGE | HEDGE | HEDGE |
| 6 | Rank my current projects from most to least urgent. | HEDGE | HEDGE | HEDGE |
| 7 | I only have a few free hours this weekend - what should I spend them on? | COMMIT | HEDGE | HEDGE |
| 8 | What's holding me back the most right now? | HEDGE | COMMIT | HEDGE |
| 9 | Which of my interests deserves the most attention this month? | COMMIT | HEDGE | HEDGE |
| 10 | What's the one thing that, if I finished it, would unlock the most progr... | COMMIT | COMMIT | HEDGE |
| 11 | Should I focus on shipping the CLI tool or writing the paper first? | COMMIT | COMMIT | HEDGE |
| 12 | What's the highest-leverage use of my time this week? | COMMIT | HEDGE | HEDGE |