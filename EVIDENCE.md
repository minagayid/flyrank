# Evidence and acceptance status

## Assignment mapping

| Requirement | Implementation | Evidence status |
|---|---|---|
| React Flow canvas | Custom Start, Decision, and Outcome nodes; editable via inspector | TypeScript/Vite build passed |
| Add/edit/connect nodes | Decision and Outcome toolbar actions; named YES/NO source handles | Build passed; browser drag/edit interaction not manually exercised |
| Local graph save/load and JSON import/export | Browser `localStorage`, example restore, JSON file controls | Build passed; browser storage/import/export interaction not manually exercised |
| Inngest step per visited node | Dynamic traversal wraps each node in a named `step.run()` | Local Dev Server registered one function; both branch runs completed with three ordered steps |
| YES/NO-only decision output | Mock is fixed YES/NO; optional OpenAI SDK adapter rejects other outputs | YES and NO mock routes passed; live model not used |
| Order, logs, history, and error handling | JSON run store and trace UI; cycle, missing-branch, model-error, and step-limit handling | Two successful local traces were returned with ordered logs; API restart persistence was not separately tested |
| Three or more polish extras | Validation (including exactly one YES and one NO output per decision), seeded graph, trace/history, keyboard shortcuts, responsive view, minimap | Included and type-checked; manual UI behavior not fully exercised |

## Actual checks

### Build

Command: `npm run build`

Observed final output after matching client validation to the API's exact YES/NO branch count:

```text
> be-09-decision-flow@1.0.0 build
> tsc --noEmit && vite build
vite v7.3.6 building client environment for production...
✓ 1914 modules transformed.
dist/index.html                   0.56 kB │ gzip:   0.34 kB
dist/assets/index-D6SY3H23.css   34.96 kB │ gzip:   7.34 kB
dist/assets/index-o8mGArfc.js   464.31 kB │ gzip: 148.19 kB
✓ built in 7.66s
```

### Local Inngest integration

The API health endpoint returned `{"ok":true,"provider":"mock","inngest":"registered"}`. `GET /api/inngest` returned `mode=dev` and `function_count=1`; the Inngest Dev Server UI returned HTTP 200. A local POST `/api/runs` probe exercised each mock branch:

```text
CHOICE=YES STATUS=completed ORDER=Incoming request > Qualify request > Priority queue BRANCH=YES RESULT=Routed to priority ERROR=
CHOICE=NO STATUS=completed ORDER=Incoming request > Qualify request > Manual review BRANCH=NO RESULT=Sent to review ERROR=
```

The first attempt exposed a case mismatch between uppercase model outputs and lowercase React Flow handle IDs; the runner now normalizes the handle comparison. The final results above are after that fix. The API and Inngest processes were stopped after the probe.

### Browser run

On 2026-09-26, opened the local editor, confirmed the seeded four-node / three-connection graph and API indicator, and ran the sample input through the UI with the Inngest Dev Server active. The newest visible run completed with an ordered trace: Incoming request → Qualify request (YES) → Priority queue. The first UI attempt, before starting the separate local Dev Server, showed a retry message and did not complete; starting the listener allowed the subsequent run to finish. This is a deterministic mock-provider run, not a live LLM evaluation.

## Limitations

- The project uses AI-assisted implementation. The learner should review and explain the architecture and code before presenting it as personal learning work.
- The default deterministic mock proves routing behavior, not semantic LLM quality.
- The live OpenAI-compatible adapter has not been called; no key was available or inspected.
- Deployment status is local only; public repository and portal submission status are recorded in the build log after publication.
- Local graph persistence controls compile but were not manually exercised in a browser; server restart persistence was not separately checked.
