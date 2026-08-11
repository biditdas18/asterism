# Asterism PoC Phase 2 (instruction vs. structure): `claude-opus-4-8` (run 5/5)

_Generated 2026-08-10T23:53:39_

Assistant model under test: **`claude-opus-4-8`**, run 5 of 5. temperature=1.0 pinned, reseed-per-call (E-fix), universal truncation/empty-response guard active. Same seeded demo graph, same 12 PRIORITY queries, same pre-registered COMMIT/HEDGE scorer (imported unchanged from `poc_compare_v2.py`, validated 11/11 on its held-out set once before this model's first run).

## COMMIT rate this run (PRIORITY, n=12)

| Condition | COMMIT rate |
|---|---|
| graph | 4/12 |
| flat_list_prioritized | 4/12 |
| flat_list | 2/12 |
| graph_neutral | 5/12 |
| none | 2/12 |

## Raw per-query labels (auditable)

| # | Query | graph | flat_list_prioritized | flat_list | graph_neutral | none |
|---|---|---|---|---|---|---|
| 1 | What's my top priority right now? | COMMIT | HEDGE | HEDGE | HEDGE | COMMIT |
| 2 | What should I focus on next? | HEDGE | HEDGE | HEDGE | COMMIT | HEDGE |
| 3 | If I could only work on one thing this week, what should ... | COMMIT | COMMIT | HEDGE | HEDGE | COMMIT |
| 4 | Between my open source project and my academic paper, whi... | HEDGE | HEDGE | HEDGE | HEDGE | HEDGE |
| 5 | What's the single most important thing I should be doing ... | HEDGE | HEDGE | HEDGE | COMMIT | HEDGE |
| 6 | Rank my current projects from most to least urgent. | HEDGE | HEDGE | HEDGE | HEDGE | HEDGE |
| 7 | I only have a few free hours this weekend - what should I... | COMMIT | HEDGE | HEDGE | HEDGE | HEDGE |
| 8 | What's holding me back the most right now? | HEDGE | HEDGE | HEDGE | HEDGE | HEDGE |
| 9 | Which of my interests deserves the most attention this mo... | HEDGE | COMMIT | COMMIT | COMMIT | HEDGE |
| 10 | What's the one thing that, if I finished it, would unlock... | HEDGE | HEDGE | COMMIT | COMMIT | HEDGE |
| 11 | Should I focus on shipping the CLI tool or writing the pa... | HEDGE | COMMIT | HEDGE | HEDGE | HEDGE |
| 12 | What's the highest-leverage use of my time this week? | COMMIT | COMMIT | HEDGE | COMMIT | HEDGE |