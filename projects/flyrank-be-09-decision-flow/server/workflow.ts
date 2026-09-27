import { Inngest } from "inngest";
import { appendLog, updateRun } from "./store";
import { decide, configuredProvider } from "./ai";
import type { FlowEdge, FlowGraph, FlowNode, FlowRun, RunLogEntry } from "./types";

export const inngest = new Inngest({ id: "flowline-decision-studio" });

function outgoing(graph: FlowGraph, node: FlowNode): FlowEdge[] {
  return graph.edges.filter((edge) => edge.source === node.id);
}

function resolveNext(graph: FlowGraph, node: FlowNode, branch?: "YES" | "NO"): FlowEdge | undefined {
  const edges = outgoing(graph, node);
  if (node.type === "decision") return edges.find((edge) => edge.sourceHandle?.toUpperCase() === branch);
  return edges[0];
}

function safeStepPart(value: string): string {
  return value.replace(/[^a-zA-Z0-9_-]/g, "-").slice(0, 48) || "node";
}

async function execute(run: FlowRun, step: { run: (id: string, handler: () => Promise<unknown>) => Promise<any> }) {
  await updateRun(run.id, { status: "running", error: undefined });
  const nodes = new Map(run.graph.nodes.map((node) => [node.id, node]));
  const start = run.graph.nodes.find((node) => node.type === "start");
  if (!start) {
    await updateRun(run.id, { status: "failed", error: "The graph has no Start node." });
    return { status: "failed", reason: "missing-start" };
  }

  let current: FlowNode | undefined = start;
  let branch: "YES" | "NO" | undefined;
  let result = run.input;
  const visited = new Set<string>();
  let order = 0;

  while (current && order < 40) {
    if (visited.has(current.id)) {
      await updateRun(run.id, { status: "failed", error: `Cycle detected at ${current.data.label}.` });
      return { status: "failed", reason: "cycle-detected" };
    }
    visited.add(current.id);
    order += 1;
    const node = current;
    const startedAt = new Date().toISOString();
    try {
      const value = await step.run(`node-${String(order).padStart(2, "0")}-${safeStepPart(node.id)}`, async () => {
        let output = result;
        let decision: "YES" | "NO" | undefined;
        if (node.type === "decision") {
          decision = await decide(node.data, run.input);
          output = decision;
        } else if (node.type === "end") {
          output = node.data.note || node.data.label;
        } else {
          output = node.data.note || "Input accepted";
        }
        const entry: RunLogEntry = {
          id: `${run.id}-${order}-${node.id}`,
          order,
          nodeId: node.id,
          nodeLabel: node.data.label,
          nodeType: node.type,
          status: "completed",
          startedAt,
          finishedAt: new Date().toISOString(),
          output,
          branch: decision,
        };
        await appendLog(run.id, entry);
        return { output, decision };
      });
      result = String(value.output ?? "");
      branch = value.decision;
      if (node.type === "end") {
        await updateRun(run.id, { status: "completed", result, error: undefined });
        return { status: "completed", result, order };
      }
      const next = resolveNext(run.graph, node, branch);
      current = next ? nodes.get(next.target) : undefined;
      if (!current) {
        const reason = node.type === "decision"
          ? `The ${branch ?? "decision"} branch has no connected node.`
          : `Node “${node.data.label}” has no next node.`;
        await updateRun(run.id, { status: "failed", error: reason });
        return { status: "failed", reason };
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Step failed.";
      const entry: RunLogEntry = {
        id: `${run.id}-${order}-${node.id}-error`,
        order,
        nodeId: node.id,
        nodeLabel: node.data.label,
        nodeType: node.type,
        status: "failed",
        startedAt,
        finishedAt: new Date().toISOString(),
        error: message,
      };
      await appendLog(run.id, entry);
      await updateRun(run.id, { status: "failed", error: message });
      return { status: "failed", reason: message };
    }
  }

  const error = order >= 40 ? "Execution stopped after 40 steps to protect against runaway flows." : "The flow ended before reaching an End node.";
  await updateRun(run.id, { status: "failed", error });
  return { status: "failed", reason: error };
}

const runDecisionFlow = inngest.createFunction(
  { id: "run-decision-flow", retries: 1, triggers: [{ event: "decision-flow/run.requested" }] },
  async ({ event, step }) => {
    const runId = String(event.data.runId ?? "");
    const run = event.data.run as FlowRun | undefined;
    if (!runId || !run) return { status: "failed", reason: "Missing run payload." };
    await updateRun(runId, { status: "running", provider: configuredProvider() });
    return execute({ ...run, id: runId }, step);
  },
);

export const functions = [runDecisionFlow];
