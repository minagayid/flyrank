# FL-04 — Automation Workflow v2

## Workflow

Goal: turn a draft portfolio artifact into a short readiness decision.

1. Read the artifact and identify its stated deliverable.
2. Check three gates: a clear outcome, verifiable evidence/link, and an honest limitation.
3. Return `READY` or `REVISE`, followed by at most three precise fixes. A human checks every result before publishing.

## Exact prompt and configuration

**Prompt**

> Review the artifact below for portfolio submission. Check only: (1) clear outcome, (2) verifiable evidence or link, and (3) an honest limitation. Return READY or REVISE, then no more than three specific fixes. Do not invent missing evidence. Artifact: {{artifact_text}}

**Configuration:** ChatGPT, one artifact per run, no external browsing, temperature/default settings unchanged, human approval required before any edit or submission.

## Five real runs

| Run | Artifact | Result | Short output / action |
|---|---|---|---|
| 1 | Week 3 identity kit | READY | Fonts, hex palette, asset link, and style note were explicit. |
| 2 | Week 3 image curation | READY | Final set and rejection reasoning were present; real-photo preference was stated. |
| 3 | Week 3 content map | READY | Claim, page-to-CTA path, and honest gather list were present. |
| 4 | Empty-but-live page | REVISE | Added source/live links and a screenshot requirement to the companion note. |
| 5 | Three Roads rationale | READY | Three free options, tradeoffs, one choice, maintenance, display, and backend status were covered. |

## Time comparison

Manual checklist review took about 4–5 minutes per artifact. The prompt-based pass took about 1–2 minutes each, including human verification: roughly 15 minutes saved across five runs.

## Known failure and review rule

The workflow can mistake confident prose for evidence and cannot prove a link works without browsing. Therefore a human must open every link, confirm the artifact exists, and reject any invented claim before publishing.
