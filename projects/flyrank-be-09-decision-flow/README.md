# Flowline Decision Studio

A local decision-flow builder for the BE-09 “Build an AI Decision Flow with React Flow + Inngest” assignment. Build a graph, choose a YES/NO route, trigger each visited node as a durable Inngest step, and inspect the ordered run trace.

## What it includes

- **React Flow canvas:** add and edit decision and outcome nodes; drag labeled YES/NO ports to connect branches.
- **Local graph storage:** automatic browser `localStorage` save, explicit save, example restore, and JSON import/export.
- **Durable execution:** an Express API sends `decision-flow/run.requested`; an Inngest function traverses the graph dynamically and calls `step.run()` for each visited node.
- **Run history:** JSON-file persistence under `data/runs.json`, execution order, per-node output, branch choice, status, and errors.
- **Deterministic mock AI:** each decision node selects a fixed YES or NO response. The default does not make a model call or need an account.
- **Optional OpenAI-compatible adapter:** the server uses the OpenAI SDK only when `DECISION_PROVIDER=openai` and `OPENAI_API_KEY` are explicitly present. The response is accepted only if it is exactly `YES` or `NO`.
- **Shadcn/ui patterns:** local Button, Card, and Input primitives use the shadcn component layout and variant conventions, with Radix Slot and class-variance-authority; `components.json` records the component aliases and style.

### Extra polish

1. Pre-run graph validation explains missing YES/NO branches and other structural problems.
2. A seeded example flow and step-by-step execution trace make the first run inspectable immediately.
3. Keyboard shortcuts: `Ctrl/Cmd+S` saves locally; `Delete` or `Backspace` removes the selected non-Start node.
4. Error states appear in the run history and trace; traversal stops on missing branches, cycles, or 40 visited nodes.
5. The layout adapts to narrower desktop windows and includes a minimap, zoom controls, connection state, and accessible form labels.

## Run locally

Requirements: Node.js 20+ and npm. No deployment, paid provider, or Inngest account is required. The Inngest Dev Server is a separate local process. The pinned `inngest-cli` npm package installs its official CLI binary into this project's development dependencies during `npm install`.

From this folder, open three terminals:

**Terminal 1 — app and API** (PowerShell):

```powershell
$env:INNGEST_DEV = "1"
npm install
npm run dev
```

**Terminal 2 — local Inngest Dev Server:**

```powershell
npm run dev:inngest
```

The CLI's postinstall downloads the matching release archive over HTTPS from Inngest's CLI CDN (with GitHub Releases as fallback). The CLI/server is licensed separately under Inngest's SSPL / Apache 2.0 Future License terms; this project does not redistribute or publish it. In the observed Windows run, the Dev Server reported a `0.0.0.0:8288` listener. Keep it on a trusted machine/network and stop it after local development; the app API itself binds to `127.0.0.1:4000`.

**Open the app:** `http://127.0.0.1:5173`
**Inngest run console:** `http://127.0.0.1:8288`

Keep both processes running when pressing **Run flow**. The API binds to `127.0.0.1:4000`; it stores run history in `data/runs.json`, which is ignored by Git. Do not expose the development API or Inngest console to a public network.

Build the client and type-check the server with:

```powershell
npm run build
```

## Optional live model adapter

Live model calls are off by default. The app does not load `.env` files. Configure variables in the server terminal only if you already have an authorized compatible API key and want to make a live call:

```powershell
$env:DECISION_PROVIDER = "openai"
$env:OPENAI_API_KEY = "your-local-key"
$env:OPENAI_BASE_URL = "https://api.openai.com/v1"
$env:OPENAI_MODEL = "gpt-4o-mini"
$env:INNGEST_DEV = "1"
npm run dev
```

For a compatible endpoint, use its base URL and model. Never commit credentials. `.env.example` contains placeholders only and is not loaded. No key or paid service is included with this project.

## Runtime behavior

One graph execution begins at the Start node. Regular connections continue directly; a Decision node asks the selected provider for exactly YES or NO, then follows the edge attached to that handle. An End node completes the run. Each visited node is an Inngest step with a stable order-based name. Errors are captured in the trace and stop traversal. The 40-step limit and visited-node check prevent runaway graphs.

The local mock is deliberately deterministic: `Local mock response` on each decision node chooses the result. It demonstrates traversal and durable step history, but it is not semantic language-model reasoning. Choose the live adapter only when local credentials are available and you accept any provider cost.

## Learning and evidence

See [LEARNING_NOTES.md](./LEARNING_NOTES.md), [BUILDLOG.md](./BUILDLOG.md), and [EVIDENCE.md](./EVIDENCE.md). The evidence file records actual checks and their limits; it does not claim a live-model run.

## References

- [React Flow custom nodes](https://reactflow.dev/learn/customization/custom-nodes) and [custom handles](https://reactflow.dev/learn/customization/handles)
- [Inngest Express quick start](https://www.inngest.com/docs/getting-started/express-quick-start), [local development](https://www.inngest.com/docs/local-development), and [step.run](https://www.inngest.com/docs/reference/typescript/v3/functions/step-run)
- [OpenAI Node SDK](https://github.com/openai/openai-node)
- [Inngest CLI/server license](https://github.com/inngest/inngest/blob/main/LICENSE.md)
