# Build log

## Scope

Created the assignment project at `work/assignments/BE-09-decision-flow/` as a standalone React + TypeScript / Express + Inngest app. It uses React Flow for the editor, Shadcn-style checked-in UI primitives, Inngest for durable node steps, the OpenAI SDK as an opt-in adapter, and deterministic local mocks by default.

## Build notes

- AI assistance was used to plan and implement this project, review API shapes, and draft documentation. The result must be reviewed and understood by the learner before submission.
- The UI offers decision and outcome nodes, editable prompts, YES/NO handles, autosave, JSON import/export, validation, sample inputs, history, and step logs.
- Each dynamic traversal step is executed with Inngest `step.run()`. Run history is persisted locally in `data/runs.json`.
- The pinned local Dev Server CLI is a dev dependency. Its reviewed postinstall downloads the matching release archive from `cli.inngest.com`, falling back to the official Inngest GitHub release; the binary stays in ignored `node_modules` and is not redistributed.
- Model calls are opt-in through process environment variables only. This project does not load `.env` files. No credentials were inspected or used.
- The public repo was created after the local implementation was built, with one initial commit; this is not a staged commit history. The public tree was checked for `.env`, local run data, build output, and dependencies; none were present.

## Verification record

The final TypeScript/Vite production build passed. Local Inngest integration passed both deterministic branches after a casing bug in edge-handle matching was found and fixed. Exact output and the manual verification limits are in [EVIDENCE.md](./EVIDENCE.md). A green local mock run does not prove that a real model provider is configured.

On 2026-09-26, a run initiated from the browser editor completed after the separately launched local Inngest Dev Server was available. Its visible three-step trace reached the Priority queue through the YES branch. A preceding attempt without the listener produced the expected local retry message.

A release review found that duplicate YES or NO edges could pass the editor's readiness check even though the API rejects them. The editor now requires exactly one of each branch, matching the API. The TypeScript/Vite production build passed again after this fix; final output is recorded in [EVIDENCE.md](./EVIDENCE.md).

Published at https://github.com/minagayid/flyrank-be-09-decision-flow. The initial source commit `55e6586` was pushed to public `main`; at first publication, local and remote `main` matched. The public tree check found no `.env`, local run data, generated build output, or dependency folders. FlyRank assignment BE-09 (`CUSTOM-MQRZWERX-A807D436`) shows **Submitted**, waiting for review, as of 2026-09-26. The reviewer note discloses AI assistance, mock-model use, and lack of live deployment/model call.
