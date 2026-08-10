# Asterism PoC (cross-model): Commit-vs-Hedge Evaluation — `gpt-5.5-2026-04-23` (run 1/5)

_Generated 2026-08-10T15:18:18_

Assistant model under test: **`gpt-5.5-2026-04-23`**, run 1 of 5 independent runs. Everything else held fixed: same seeded demo graph (freshly reseeded this run), same 12 PRIORITY queries, same 3 inject conditions (graph/flat_list/none), same pre-registered COMMIT/HEDGE scorer (imported unchanged from `poc_compare_v2.py`, validated 11/11 on its held-out set once before this model's first run). No per-run target — see the aggregate file for the across-run distribution this run contributes to.

## COMMIT rate this run (PRIORITY, n=12)

| Condition | COMMIT rate |
|---|---|
| graph | 4/12 |
| flat_list | 6/12 |
| none | 2/12 |

graph-flat_list gap this run: **-2**

## Raw per-query labels (auditable)

| # | Query | graph | flat_list | none |
|---|---|---|---|---|
| 1 | What's my top priority right now? | HEDGE | HEDGE | HEDGE |
| 2 | What should I focus on next? | HEDGE | HEDGE | HEDGE |
| 3 | If I could only work on one thing this week, what should it be? | HEDGE | HEDGE | HEDGE |
| 4 | Between my open source project and my academic paper, which should I pri... | HEDGE | COMMIT | HEDGE |
| 5 | What's the single most important thing I should be doing today? | HEDGE | HEDGE | HEDGE |
| 6 | Rank my current projects from most to least urgent. | HEDGE | HEDGE | HEDGE |
| 7 | I only have a few free hours this weekend - what should I spend them on? | COMMIT | COMMIT | HEDGE |
| 8 | What's holding me back the most right now? | HEDGE | COMMIT | HEDGE |
| 9 | Which of my interests deserves the most attention this month? | HEDGE | COMMIT | HEDGE |
| 10 | What's the one thing that, if I finished it, would unlock the most progr... | COMMIT | COMMIT | HEDGE |
| 11 | Should I focus on shipping the CLI tool or writing the paper first? | COMMIT | HEDGE | COMMIT |
| 12 | What's the highest-leverage use of my time this week? | COMMIT | COMMIT | COMMIT |