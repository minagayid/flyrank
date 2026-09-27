# Signal Desk — capstone portfolio entry

## Project brief

Signal Desk is a lead-triage workspace for independent creative studios and small client-facing teams that need to review incomplete project inquiries and choose a useful next step. A logistic-regression model trained on synthetic examples surfaces evidence about fit and urgency, plus open questions; a person reviews the result and edits any follow-up. The project explores how AI can make triage clearer without rejecting people or sending messages automatically.

## Live application

**Status:** Not deployed. A production URL is not available yet. The public repository is not a substitute for the required working live application. Deployment is pending sign-in to an existing hosting account and a production smoke check.

## Repository and README

- [Public GitHub repository](https://github.com/minagayid/signal-desk-ai-lead-triage)
- [Setup, architecture, AI behavior, environment, and limitations](../../README.md)
- Run locally from `web/` with `npm install` and `npm run dev`.

## Testing evidence

- [Test and quality record](../assignments/TESTING.md): 20 unit/component tests, 88.81% line coverage in the configured scope, production build, and 10 browser checks across Chromium and Firefox.
- [Latest hosted GitHub Actions run for `main`](https://github.com/minagayid/signal-desk-ai-lead-triage/actions/runs/36191444331); workflow runs also passed on `workflow/vague-prompt` and `workflow/precise-prompt`.
- [Lead workspace screenshot](../assets/signal-desk-lead-review.png) shows the real local application with synthetic sample data.

## Performance and accessibility audit

- [Audit record](../assignments/AUDIT.md): Lighthouse mobile scores were 96 performance / 100 accessibility for the inbox and 97 / 98 for the lead workspace.
- [Inbox Lighthouse JSON report](../audits/lighthouse-inbox-2026-09-25.json) · [Lead workspace Lighthouse JSON report](../audits/lighthouse-lead-2026-09-25.json).
- The axe scan reported zero violations across six routes in Chromium and Firefox; keyboard dialog, reduced-motion, and 320 px checks also passed.
- An audit found the chat placeholder color had 3.14:1 contrast on white. It was changed from `#849590` to `#606f6b`, which measures 5.27:1 on white and 4.74:1 on the app's `#eff4f1` paper.
- WAVE and manual screen-reader review have not been completed. Lighthouse was run locally; no stable public URL exists for a deployment comparison.

## Deployment and operation

- [Deployment preparation and current status](../assignments/DEPLOYMENT.md)
- [Capstone deployment checklist](DEPLOY-CHECKLIST.md): public repository and hosted CI are complete; host sign-in, live deploy, and public smoke check remain open.
- Failures preserve the user's request and offer retry/recovery states; the documented rollback is to restore the previous deployment, but no deployment exists yet and the rollback has not been exercised.

## Reflection

- [Capstone reflection](REFLECTION.md) covers the hardest implementation trade-offs, limitations, and next steps.

## Current gaps

The portfolio entry and evidence links were submitted to FlyRank on 2026-09-26; the portal shows **Submitted**, with mentor review pending. The capstone does not yet meet the live-deployment requirement. The deployment URL, FE-01 AI-assistant screenshot, and WAVE/manual screen-reader evidence remain outstanding.
