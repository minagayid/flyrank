# Test and quality record

## Commands

Run from `web/`:

```text
npm run train
npm run lint
npm run typecheck
npm run test
npm run coverage
npm run e2e
npm run build
```

The unit and component suite uses Vitest, Testing Library, and synthetic fixtures. The browser suite uses Playwright Chromium and Firefox with the app's local model; no real AI provider is configured. The Chromium e2e run captures a real local lead detail screenshot at `outputs/signal-desk-lead-review.png`.

## Latest local run

| Check | Result | Evidence |
|---|---|---|
| Model training | Passed: logistic regression, 38 synthetic examples | `src/lib/ai/model-weights.json` |
| TypeScript | Passed: `npm run typecheck` | Local run on 2026-09-25 |
| Unit/component tests | Passed: 6 files, 20 tests | `npm run test`, local run on 2026-09-25 |
| Component coverage | Passed: 88.81% lines, 84.74% statements, 85.36% functions; configured thresholds met | `npm run coverage`; scope is inbox, accessibility widgets, and stateful button |
| Lint | Passed with no warnings | `npm run lint`, local run on 2026-09-25 |
| Playwright E2E | Passed: 5 checks in each of Chromium and Firefox (10 total), including streamed lead review, health fetch, six-route axe scan, keyboard dialog path, and 320 px/reduced-motion checks | `npm run e2e`, production build on 2026-09-25 |
| Production build | Passed; 11 app routes generated | `npm run build`, local run on 2026-09-25 |
| Lighthouse mobile profile | Inbox: 96 performance / 100 accessibility; lead review: 97 / 98 | [Inbox JSON](../audits/lighthouse-inbox-2026-09-25.json), [lead JSON](../audits/lighthouse-lead-2026-09-25.json); 2026-09-25 |
| Hosted CI | Passed on `main`, `workflow/vague-prompt`, and `workflow/precise-prompt` | [Latest main run](https://github.com/minagayid/signal-desk-ai-lead-triage/actions/runs/36191444331); local run date 2026-09-26 |

Lighthouse ran against the local production server with Playwright Chromium. These are single-run local measurements, not a baseline comparison or a guarantee for other devices. The axe scan reports zero violations for six routes in both Chromium and Firefox. Keyboard dialog handling, a 320 px no-horizontal-overflow check on three routes, and reduced-motion behavior passed in both browsers. WAVE and manual screen-reader review remain separate checks.
