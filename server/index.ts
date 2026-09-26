import express from "express";
import { serve } from "inngest/express";
import { createRun, getRun, listRuns, updateRun } from "./store";
import { configuredProvider } from "./ai";
import { functions, inngest } from "./workflow";
import type { FlowGraph, FlowRun } from "./types";

const app = express();
const port = Number(process.env.PORT || 4000);
app.use(express.json({ limit: "1mb" }));
app.use("/api/inngest", serve({ client: inngest, functions }));

function validateGraph(value: unknown): { graph?: FlowGraph; error?: string } {
  if (!value || typeof value !== "object") return { error: "Graph must be a JSON object." };
  const graph = value as FlowGraph;
  if (!Array.isArray(graph.nodes) || !Array.isArray(graph.edges)) return { error: "Graph needs nodes and edges arrays." };
  if (graph.nodes.length < 2 || graph.nodes.length > 100) return { error: "Graph must contain 2–100 nodes." };
  if (graph.nodes.filter((node) => node?.type === "start").length !== 1) return { error: "Use exactly one Start node." };
  if (!graph.nodes.some((node) => node?.type === "end")) return { error: "Connect a path to an End node before running." };
  if (graph.nodes.some((node) => !node || !["start", "decision", "end"].includes(node.type) || typeof node.id !== "string" || typeof node.data?.label !== "string")) {
    return { error: "Every node needs a supported type, ID, and label." };
  }
  const ids = new Set(graph.nodes.map((node) => node.id));
  if (ids.size !== graph.nodes.length) return { error: "Node IDs must be unique." };
  for (const edge of graph.edges) {
    if (!ids.has(edge.source) || !ids.has(edge.target)) return { error: "Every connection must point to an existing node." };
    const source = graph.nodes.find((node) => node.id === edge.source);
    if (source?.type === "decision" && edge.sourceHandle !== "yes" && edge.sourceHandle !== "no") {
      return { error: `Connect both outputs on “${source.data.label}” as YES or NO.` };
    }
  }
  for (const node of graph.nodes.filter((candidate) => candidate.type === "decision")) {
    const branches = graph.edges.filter((edge) => edge.source === node.id).map((edge) => edge.sourceHandle);
    if (branches.filter((branch) => branch === "yes").length !== 1 || branches.filter((branch) => branch === "no").length !== 1) {
      return { error: `Connect exactly one YES output and one NO output on “${node.data.label}”.` };
    }
  }
  return { graph };
}

app.get("/api/health", (_request, response) => {
  response.json({ ok: true, provider: configuredProvider(), inngest: "registered" });
});

app.get("/api/runs", async (_request, response, next) => {
  try {
    response.json(await listRuns());
  } catch (error) {
    next(error);
  }
});

app.get("/api/runs/:id", async (request, response, next) => {
  try {
    const run = await getRun(request.params.id);
    if (!run) return response.status(404).json({ error: "Run not found." });
    response.json(run);
  } catch (error) {
    next(error);
  }
});

app.post("/api/runs", async (request, response, next) => {
  try {
    const validation = validateGraph(request.body?.graph);
    if (!validation.graph) return response.status(400).json({ error: validation.error });
    const input = typeof request.body?.input === "string" ? request.body.input.slice(0, 8_000) : "";
    const provider = configuredProvider();
    const run = await createRun({
      status: "queued",
      input,
      provider,
      graph: validation.graph,
    } as Omit<FlowRun, "id" | "createdAt" | "updatedAt" | "logs">);
    try {
      await inngest.send({ name: "decision-flow/run.requested", data: { runId: run.id, run } });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not reach the Inngest Dev Server.";
      await updateRun(run.id, { status: "failed", error: `Inngest event send failed: ${message}` });
      return response.status(503).json({ error: "Start the local Inngest Dev Server, then retry." });
    }
    response.status(202).json({ id: run.id, status: "queued" });
  } catch (error) {
    next(error);
  }
});

app.use((error: unknown, _request: express.Request, response: express.Response, _next: express.NextFunction) => {
  const message = error instanceof Error ? error.message : "Unexpected server error.";
  response.status(500).json({ error: message });
});

app.listen(port, "127.0.0.1", () => {
  console.log(`Flowline API ready at http://127.0.0.1:${port}`);
});
