# Capstone deployment checklist

- [x] One-paragraph product brief in `SPEC.md`.
- [x] Product routes, design tokens, and a live health endpoint/page.
- [x] AI tool schema and local streaming flow with explicit limitations.
- [x] Six or more meaningful component tests and coverage threshold (20 tests; 88.81% lines in the configured component scope).
- [x] Primary-flow browser end-to-end test (5 checks each in Chromium and Firefox; 10 passed).
- [x] Public repository, production build, local browser smoke test, and hosted CI on `main` plus both workflow branches.
- [x] Lighthouse performance score of 85 or higher, with reports saved (96 inbox, 97 lead review).
- [x] Automated keyboard dialog path, 320 px reflow, and reduced-motion checks in Chromium and Firefox.
- [ ] WAVE and manual screen-reader review with evidence saved.
- [x] Select and publish the public repository: `https://github.com/minagayid/signal-desk-ai-lead-triage`.
- [ ] Sign in to a deployment host and connect the repository.
- [ ] Deploy preview and verify the public build.
- [x] Submit the current portfolio entry and evidence links to the Frontend capstone portal (status: Submitted, 2026-09-26; mentor review pending).
- [ ] Add the production URL after host sign-in, deployment, and public smoke checks; update the portal submission.

## Rollback

Keep the previous production deployment until the preview smoke test passes. If the new revision fails, restore the previous deployment in hosting history, check the inbox, lead detail, health page, and stream endpoint, and record the failing revision. No deployment exists yet, so this plan has not been exercised.
