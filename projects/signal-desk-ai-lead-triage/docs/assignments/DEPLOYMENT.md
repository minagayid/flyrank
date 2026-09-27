# Production deployment preparation

## Ready locally

- App Router pages, health endpoint, server-side request validation, output size limit, development-only fault controls, and README run instructions.
- No provider API key is required. The default classifier and training data are local and synthetic.
- `.env.example` contains an empty optional key placeholder only; no secret value is required or committed.
- The API applies a per-process short-term rate limit. Replace it with a shared limiter before running multiple production instances.

## Before publication

1. Run lint, typecheck, unit/component tests, coverage, production build, and browser end-to-end check from `web/`.
2. Capture the actual audit reports and verify the capstone's Lighthouse/accessibility thresholds.
3. Review the diff and secret scan, then publish the approved public repository. This project is at `https://github.com/minagayid/signal-desk-ai-lead-triage`; `main` and both workflow branches are pushed, and hosted CI passed.
4. Configure any provider key only if the product's model is intentionally changed. Keep it in the deployment platform's secret store; do not use `.env.example` for credentials.
5. Publish a preview, smoke test `/`, `/leads/northline`, `/health`, and `/api/qualify`, and capture the public URL and build revision.
6. Update the portal with the confirmed repository and deployment links after review.

## Rollback

Keep the last known-good deployment active while the preview is checked. If the inbox, lead page, health route, or streaming endpoint fails, stop promotion and restore the previous deployment from the host's deployment history. Re-run the four smoke checks and preserve the failed revision and logs without exposing request content or secrets.

## Current boundary

The public GitHub repository and hosted CI are verified. The Chrome session has no Vercel sign-in and no other deployment provider is configured, so no live preview or production URL exists yet. FlyRank now shows 14/14 frontend assignments submitted or complete and the track capstone as Submitted; mentor review is pending. Deployment-dependent submissions explicitly state that the live URL is missing. This document is a checklist, not proof of deployment.
