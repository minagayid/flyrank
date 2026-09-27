# Learning notes

## React Flow graph model

The canvas stores nodes and edges as data. A custom node exposes connection handles; a decision node gives its two source handles stable IDs (`yes` and `no`). The edge records the selected handle, so execution can route from the graph itself without a separate branch table. This makes the canvas and runtime share one source of truth.

## Inngest durable steps

The API sends an event rather than doing workflow work inside the request. Inngest receives the event and invokes the function; each visited node runs inside `step.run()`. A step name includes the traversal order and node ID. Inngest can checkpoint and retry that step while the application maintains a separate product-level trace for people using the editor.

## Dynamic traversal

The runner starts at the Start node, finds outgoing edges, evaluates a decision, and chooses the edge whose source handle matches the result. It maintains a visited-node set and a maximum step count to catch cycles and runaway paths. A missing next node is recorded as a failed run instead of silently appearing successful.

## Constraining model output

The mock is a fixed per-node YES/NO setting, which makes local acceptance predictable. The optional model adapter asks for one token, sets temperature to zero, then rejects any response except the exact values YES or NO. Prompting alone cannot guarantee a schema, so the server validates the response before selecting a branch.

## Local persistence

The graph is autosaved in browser `localStorage`; users can also export a JSON copy. Execution history is server-side JSON so it survives a server restart. An atomic temporary-file rename avoids leaving a partially written history file after an interrupted write.

## Learning resources

- React Flow custom nodes and handles: https://reactflow.dev/learn/customization/custom-nodes
- Inngest function steps and the local Dev Server: https://www.inngest.com/docs/learn/inngest-functions and https://www.inngest.com/docs/local-development
- OpenAI TypeScript SDK: https://github.com/openai/openai-node
