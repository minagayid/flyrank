export type NodeKind = "start" | "decision" | "end";

export interface FlowNodeData extends Record<string, unknown> {
  label: string;
  prompt: string;
  mockDecision: "YES" | "NO";
  note: string;
}

export interface FlowNode {
  id: string;
  type: NodeKind;
  position: { x: number; y: number };
  data: FlowNodeData;
}

export interface FlowEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string | null;
  targetHandle?: string | null;
}

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
