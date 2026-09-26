import type { Edge, Node } from "@xyflow/react";

export type NodeKind = "start" | "decision" | "end";
export interface FlowNodeData extends Record<string, unknown> {
  label: string;
  prompt: string;
  mockDecision: "YES" | "NO";
  note: string;
}
export type FlowNode = Node<FlowNodeData, NodeKind>;
export type FlowEdge = Edge;
export interface FlowGraph {
  nodes: FlowNode[];
  edges: FlowEdge[];
}

export interface RunLogEntry {
  id: string;
  order: number;
  nodeId: string;
  nodeLabel: string;
  nodeType: NodeKind;
  status: "completed" | "failed";
  startedAt: string;
  finishedAt: string;
  output?: string;
  branch?: "YES" | "NO";
  error?: string;
}
export interface FlowRun {
  id: string;
  status: "queued" | "running" | "completed" | "failed";
  createdAt: string;
  updatedAt: string;
  input: string;
  provider: "mock" | "openai";
  graph: FlowGraph;
  logs: RunLogEntry[];
  result?: string;
  error?: string;
}

export function starterGraph(): FlowGraph {
  const nodes: FlowNode[] = [
    { id: "start", type: "start", position: { x: 72, y: 232 }, data: { label: "Incoming request", prompt: "", mockDecision: "YES", note: "Request received" } },
    { id: "decision", type: "decision", position: { x: 360, y: 232 }, data: { label: "Qualify request", prompt: "Should this request be routed to the priority team? Return YES or NO.", mockDecision: "YES", note: "" } },
    { id: "approved", type: "end", position: { x: 704, y: 100 }, data: { label: "Priority queue", prompt: "", mockDecision: "YES", note: "Routed to the priority team" } },
    { id: "review", type: "end", position: { x: 704, y: 354 }, data: { label: "Manual review", prompt: "", mockDecision: "YES", note: "Sent to manual review" } },
  ];
  const edges: FlowEdge[] = [
    { id: "e-start-decision", source: "start", target: "decision", type: "smoothstep", animated: false },
    { id: "e-yes-approved", source: "decision", sourceHandle: "yes", target: "approved", type: "smoothstep", label: "YES", labelStyle: { fill: "#087f68", fontWeight: 700 }, labelBgStyle: { fill: "#e8f6f2" } },
    { id: "e-no-review", source: "decision", sourceHandle: "no", target: "review", type: "smoothstep", label: "NO", labelStyle: { fill: "#b66a2d", fontWeight: 700 }, labelBgStyle: { fill: "#fff3e7" } },
  ];
  return { nodes, edges };
}

export function graphProblems(graph: FlowGraph): string[] {
  const problems: string[] = [];
  const starts = graph.nodes.filter((node) => node.type === "start");
  if (starts.length !== 1) problems.push("Use exactly one Start node.");
  if (!graph.nodes.some((node) => node.type === "end")) problems.push("Add at least one End node.");
  for (const node of graph.nodes.filter((candidate) => candidate.type === "decision")) {
    const branches = graph.edges.filter((edge) => edge.source === node.id).map((edge) => edge.sourceHandle);
    for (const branch of ["yes", "no"] as const) {
      const count = branches.filter((candidate) => candidate === branch).length;
      if (count === 0) problems.push(`${node.data.label}: connect its ${branch.toUpperCase()} output.`);
      if (count > 1) problems.push(`${node.data.label}: use exactly one ${branch.toUpperCase()} output.`);
    }
    if (branches.some((branch) => branch !== "yes" && branch !== "no")) {
      problems.push(`${node.data.label}: connections must use YES or NO outputs.`);
    }
  }
  const ids = new Set(graph.nodes.map((node) => node.id));
  if (ids.size !== graph.nodes.length) problems.push("Node IDs must be unique.");
  if (graph.edges.some((edge) => !ids.has(edge.source) || !ids.has(edge.target))) problems.push("Remove connections to missing nodes.");
  return problems;
}
