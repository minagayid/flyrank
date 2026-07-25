# Portfolio Evidence Editor

Live tool: https://minagayid.github.io/flyrank/agent/

## What it does

Portfolio Evidence Editor turns public-safe project notes into a structured case-study draft for a job seeker or early-career builder. It keeps the evidence visible, highlights risky absolute language, and places an explicit human fact-check gate before publication.

It is intentionally deterministic. It does not call an external language model or upload notes.

## Setup

No installation is required.

1. Open the live URL in a current browser.
2. Choose the intended audience.
3. Paste public-safe notes using the labels `Problem`, `Role`, `Method`, `Evidence`, `Limitation`, and `Next step`.
4. Press **Build evidence-first draft**.
5. Verify the draft and the claim audit before using any text.

To run locally, download `agent/index.html` and open it in a browser. The tool has no build step, package manager, API key, or server dependency.

## Usage example

```text
Problem: Content teams cannot inspect every page.
Role: I designed a public-safe review queue and documented the decision boundary.
Method: I compared a transparent rule with a regularized score on the same held-out slice.
Evidence: Precision at 10 was 0.60 for the rule and 0.80 for the comparison score.
Limitation: This is directional decision support, not causal evidence.
Next step: A reviewer checks intent and SERP context before any content change.
```

The result is a six-part draft plus a claim audit that lists numeric tokens and risky absolute terms.

## Architecture

```text
public-safe notes
      ↓
label parser ──→ missing-section prompts
      ↓
case-study formatter
      ↓
numeric-token + risky-language audit
      ↓
human fact-check gate
      ↓
optional publication
```

All processing runs in the browser. There is no backend or database.

## v2 evaluation

Five public-safe test cases were reviewed:

| Test | Expected behavior | Result |
|---|---|---|
| Complete labeled notes | Produce every case section | Pass |
| Missing evidence line | Show a missing-evidence prompt | Pass |
| Absolute claim such as “guaranteed” | Flag before publication | Pass |
| Numeric result | Surface numeric tokens for checking | Pass |
| Empty input | Refuse to draft | Pass |

The most important improvement from v1 is that missing evidence is now visible in the output instead of being silently smoothed over.

## Guardrails

- Never invent metrics, testimonials, clients, or screenshots.
- Do not paste private client, patient, credential, or account data.
- A clean language audit is not proof that a claim is true.
- A human verifies every metric, privacy boundary, and publication decision.
- The tool structures supplied notes; it does not research missing facts.

## Limitations

- The parser expects simple labeled lines.
- The risky-language list is small and cannot detect every unsupported implication.
- It does not understand domain context or verify sources.
- It does not save projects or collaborate across devices.
- Browser speech used by the guided demo varies by operating system and may require a user click.

## Guided live demo

Open the live tool and press **Start narrated demo**. It performs an end-to-end run with voice narration, explains the privacy boundary, demonstrates the claim audit, names the deterministic design decision, and states the human-review limitation. A transcript and five-minute showcase outline are stored in the Week 8 storytelling notebook.
