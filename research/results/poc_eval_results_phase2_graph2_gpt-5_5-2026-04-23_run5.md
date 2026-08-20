# Asterism PoC Phase 2 / Graph 2 (Priya): `gpt-5.5-2026-04-23` (run 5/5)

_Generated 2026-08-12T05:33:55_

Assistant model under test: **`gpt-5.5-2026-04-23`**, run 5 of 5, against seed_graph_2's Priya persona (freelance designer/studio owner). temperature=1.0 pinned, reseed-per-call (E-fix), universal truncation/empty-response guard active. Same 12 graph-2 PRIORITY queries, same pre-registered COMMIT/HEDGE scorer (imported unchanged from `poc_compare_v2.py`, validated 11/11 on its held-out set once before this model's first run).

## COMMIT rate this run (PRIORITY, n=12)

| Condition | COMMIT rate |
|---|---|
| graph | 5/12 |
| flat_list_prioritized | 7/12 |
| flat_list | 5/12 |
| graph_neutral | 6/12 |
| none | 3/12 |

## Raw per-query labels (auditable)

| # | Query | graph | flat_list_prioritized | flat_list | graph_neutral | none |
|---|---|---|---|---|---|---|
| 1 | What's my top priority right now? | HEDGE | HEDGE | COMMIT | HEDGE | HEDGE |
| 2 | What should I focus on next? | COMMIT | COMMIT | COMMIT | COMMIT | HEDGE |
| 3 | If I could only work on one thing this week, what should ... | HEDGE | COMMIT | HEDGE | HEDGE | HEDGE |
| 4 | Between the bakery brand identity project and my mom's ca... | HEDGE | COMMIT | HEDGE | COMMIT | HEDGE |
| 5 | What's the single most important thing I should be doing ... | HEDGE | HEDGE | HEDGE | HEDGE | HEDGE |
| 6 | Rank my current projects from most to least urgent. | COMMIT | HEDGE | HEDGE | HEDGE | HEDGE |
| 7 | I only have a few free hours this weekend - what should I... | HEDGE | COMMIT | HEDGE | COMMIT | HEDGE |
| 8 | What's holding me back the most right now? | HEDGE | HEDGE | COMMIT | COMMIT | HEDGE |
| 9 | Which of my interests deserves the most attention this mo... | HEDGE | HEDGE | HEDGE | HEDGE | HEDGE |
| 10 | What's the one thing that, if I finished it, would unlock... | COMMIT | COMMIT | COMMIT | HEDGE | COMMIT |
| 11 | Should I focus on client work or my ceramics practice first? | COMMIT | COMMIT | COMMIT | COMMIT | COMMIT |
| 12 | What's the highest-leverage use of my time this week? | COMMIT | COMMIT | HEDGE | COMMIT | COMMIT |