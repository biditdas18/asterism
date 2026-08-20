# Asterism PoC Phase 2 / Graph 2 (Priya): `claude-opus-4-8` (run 4/5)

_Generated 2026-08-12T04:06:06_

Assistant model under test: **`claude-opus-4-8`**, run 4 of 5, against seed_graph_2's Priya persona (freelance designer/studio owner). temperature=1.0 pinned, reseed-per-call (E-fix), universal truncation/empty-response guard active. Same 12 graph-2 PRIORITY queries, same pre-registered COMMIT/HEDGE scorer (imported unchanged from `poc_compare_v2.py`, validated 11/11 on its held-out set once before this model's first run).

## COMMIT rate this run (PRIORITY, n=12)

| Condition | COMMIT rate |
|---|---|
| graph | 4/12 |
| flat_list_prioritized | 2/12 |
| flat_list | 0/12 |
| graph_neutral | 2/12 |
| none | 0/12 |

## Raw per-query labels (auditable)

| # | Query | graph | flat_list_prioritized | flat_list | graph_neutral | none |
|---|---|---|---|---|---|---|
| 1 | What's my top priority right now? | COMMIT | HEDGE | HEDGE | HEDGE | HEDGE |
| 2 | What should I focus on next? | COMMIT | HEDGE | HEDGE | HEDGE | HEDGE |
| 3 | If I could only work on one thing this week, what should ... | HEDGE | COMMIT | HEDGE | COMMIT | HEDGE |
| 4 | Between the bakery brand identity project and my mom's ca... | HEDGE | HEDGE | HEDGE | HEDGE | HEDGE |
| 5 | What's the single most important thing I should be doing ... | HEDGE | HEDGE | HEDGE | HEDGE | HEDGE |
| 6 | Rank my current projects from most to least urgent. | HEDGE | HEDGE | HEDGE | HEDGE | HEDGE |
| 7 | I only have a few free hours this weekend - what should I... | COMMIT | HEDGE | HEDGE | HEDGE | HEDGE |
| 8 | What's holding me back the most right now? | HEDGE | HEDGE | HEDGE | HEDGE | HEDGE |
| 9 | Which of my interests deserves the most attention this mo... | COMMIT | COMMIT | HEDGE | HEDGE | HEDGE |
| 10 | What's the one thing that, if I finished it, would unlock... | HEDGE | HEDGE | HEDGE | HEDGE | HEDGE |
| 11 | Should I focus on client work or my ceramics practice first? | HEDGE | HEDGE | HEDGE | HEDGE | HEDGE |
| 12 | What's the highest-leverage use of my time this week? | HEDGE | HEDGE | HEDGE | COMMIT | HEDGE |