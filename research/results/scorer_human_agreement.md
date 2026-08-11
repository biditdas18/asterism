# Scorer-Human Agreement (Task 2)

Cohen's kappa between the frozen v2 COMMIT/HEDGE scorer's labels and a human
rater's labels, on `research/results/sonnet_phase2_run1_human_eval.csv` (36
rows: sonnet Phase 2 run 1, graph/flat_list/none, 12 queries each). The scorer
was **not retuned** based on these results — this file records agreement with
an already-frozen instrument, not a calibration step.

## Script output (captured verbatim from `python research/score_agreement.py`)

```
n = 36
raw agreement = 30/36 = 83.3%
Cohen's kappa = 0.640

Confusion (scorer -> human):
  scorer=COMMIT  human=COMMIT : 10
  scorer=COMMIT  human=HEDGE  : 2
  scorer=HEDGE   human=COMMIT : 4
  scorer=HEDGE   human=HEDGE  : 20
```

## The 6 disagreements

| Condition | Query | scorer | human | Response (first ~220 chars) |
|---|---|---|---|---|
| graph | What's my top priority right now? | HEDGE | COMMIT | "Based on your knowledge graph, here's what's rising to the top: **Your highest-priority focus right now is Open Source Development**, specifically centered around building an **AI Memory Tool**..." |
| graph | If I could only work on one thing this week, what should it be? | HEDGE | COMMIT | "Great question. Let me traverse your graph to find the highest-leverage answer. TRAVERSAL: Alex -> Open Source Development -> AI Memory Tools -> Python project ideation -> Package structure design -> PyPI packaging stra..." |
| graph | Rank my current projects from most to least urgent. | HEDGE | COMMIT | "# Project Priority Ranking Based on your knowledge graph, here's how I'd rank your active projects: --- ## 🔴 Tier 1 — Most Urgent **1. Asterism / AI Memory Tool (CLI)** TRAVERSAL: AI Memory Tools -> CLI Tools -> Clic..." |
| graph | What's the one thing that, if I finished it, would unlock the most progress? | HEDGE | COMMIT | "TRAVERSAL: Alex -> Open Source Development -> AI Memory Tools -> CLI Tools -> Package structure design -> PyPI packaging strategy **Ship the package.** Getting Asterism (or whatever you're calling the tool) onto PyPI i..." |
| flat_list | If I could only work on one thing this week, what should it be? | COMMIT | HEDGE | "That's a great forcing-function question. Based on what I know about your work, let me reason through it: ## My recommendation: **The conference paper / arXiv submission** Here's why it likely edges everything else out..." |
| flat_list | Between my open source project and my academic paper, which should I prioritize? | COMMIT | HEDGE | "That's a real tension you've been sitting with. Based on what you've shared across both tracks, here's how I'd think through it: ## What You've Built Toward **Open Source Side** - You've done substantial work: package..." |

## Directional bias

The 6 disagreements are not random noise — they point one way:

- **4/6 are scorer=HEDGE / human=COMMIT, all in the `graph` condition.** The
  scorer under-counts real commits specifically in the condition the paper's
  central claim depends on. Each of these 4 responses names a specific,
  weight-justified answer (e.g. "**Your highest-priority focus right now is
  Open Source Development**", "**Ship the package.**") in a phrasing the
  frozen regex patterns don't happen to catch.
- **2/6 are scorer=COMMIT / human=HEDGE, both in `flat_list`.** The scorer
  over-counts commits in the condition the paper's claim is compared against.

Both directions push the same way: **the measured graph-vs-flat_list gap is
biased toward the null**, i.e. the scorer is making the graph's advantage
look smaller than a human rater would, not larger. This is a conservative
bias for the paper's claim, not a favorable one, and is reported as found —
the scorer was not adjusted in response to it.
