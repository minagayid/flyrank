import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  addEdge,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlow,
  useEdgesState,
  useNodesState,
  type Connection,
  type Edge,
  type NodeTypes,
} from "@xyflow/react";
import {
  Activity, AlertCircle, ArrowDownToLine, Bot, Check, ChevronDown,
  CircleHelp, Clock3, Download, Flag, GitBranch, GitCommitHorizontal,
  History, Layers3, LoaderCircle, Play, Plus, Save, Sparkles, Upload, Workflow,
  X,
} from "lucide-react";
import FlowNodeCard from "@/components/FlowNodeCard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";
import { graphProblems, starterGraph, type FlowGraph, type FlowNode, type FlowRun } from "@/lib/workflow";

const STORAGE_KEY = "flowline:decision-graph:v1";
const NODE_TYPES: NodeTypes = { start: FlowNodeCard, decision: FlowNodeCard, end: FlowNodeCard };

function initialGraph(): FlowGraph {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      const parsed = JSON.parse(saved) as FlowGraph;
      if (Array.isArray(parsed.nodes) && Array.isArray(parsed.edges) && parsed.nodes.length) return parsed;
    }
  } catch {
    // A corrupt local draft falls back to the included example flow.
  }
  return starterGraph();
}

function relativeTime(value: string): string {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  return `${Math.floor(seconds / 3600)}h ago`;
}

function statusClass(status: string): string {
  return `status-pill status-${status}`;
}

export default function App() {
  const initial = useMemo(initialGraph, []);
  const [nodes, setNodes, onNodesChange] = useNodesState<FlowNode>(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initial.edges);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [input, setInput] = useState("A customer asks for an expedited refund after a duplicate charge.");
  const [runs, setRuns] = useState<FlowRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [pending, setPending] = useState(false);
  const [health, setHealth] = useState<"checking" | "online" | "offline">("checking");
  const importRef = useRef<HTMLInputElement>(null);
  const graph: FlowGraph = useMemo(() => ({ nodes, edges }), [nodes, edges]);
  const problems = useMemo(() => graphProblems(graph), [graph]);
  const selectedNode = nodes.find((node) => node.id === selectedNodeId);
  const selectedRun = runs.find((run) => run.id === selectedRunId);

  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(graph)); } catch { /* Storage may be unavailable in private mode. */ }
  }, [graph]);

  const refreshRuns = useCallback(async () => {
    try {
      const response = await fetch("/api/runs");
      if (response.ok) setRuns(await response.json() as FlowRun[]);
    } catch { /* The API health indicator covers local service availability. */ }
  }, []);

  useEffect(() => {
    void refreshRuns();
    fetch("/api/health").then((response) => setHealth(response.ok ? "online" : "offline")).catch(() => setHealth("offline"));
  }, [refreshRuns]);

  useEffect(() => {
    if (!selectedRunId) return;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let alive = true;
    const poll = async () => {
      try {
        const response = await fetch(`/api/runs/${selectedRunId}`);
        if (response.ok) {
          const current = await response.json() as FlowRun;
          if (alive) {
            setRuns((previous) => [current, ...previous.filter((run) => run.id !== current.id)]);
            if (current.status === "queued" || current.status === "running") timer = setTimeout(poll, 900);
          }
        }
      } catch { if (alive) timer = setTimeout(poll, 1500); }
    };
    void poll();
    return () => { alive = false; if (timer) clearTimeout(timer); };
  }, [selectedRunId]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const typing = target?.tagName === "INPUT" || target?.tagName === "TEXTAREA" || target?.isContentEditable;
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        localStorage.setItem(STORAGE_KEY, JSON.stringify({ nodes, edges }));
        setNotice("Flow saved on this device.");
      }
      if ((event.key === "Backspace" || event.key === "Delete") && !typing && selectedNodeId) {
        const selected = nodes.find((node) => node.id === selectedNodeId);
        if (selected && selected.type !== "start") {
          setNodes((current) => current.filter((node) => node.id !== selected.id));
          setEdges((current) => current.filter((edge) => edge.source !== selected.id && edge.target !== selected.id));
          setSelectedNodeId(null);
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [edges, nodes, selectedNodeId, setEdges, setNodes]);

  const onConnect = useCallback((connection: Connection) => {
    const source = nodes.find((node) => node.id === connection.source);
    if (!connection.source || !connection.target) return;
    if (source?.type === "decision" && connection.sourceHandle !== "yes" && connection.sourceHandle !== "no") {
      setNotice("Connect from one of the labeled YES / NO ports.");
      return;
    }
    const branch = connection.sourceHandle?.toUpperCase();
    const edge = {
      ...connection,
      id: `e-${connection.source}-${connection.sourceHandle ?? "out"}-${connection.target}-${Date.now()}`,
      type: "smoothstep",
      label: source?.type === "decision" ? branch : undefined,
      labelStyle: { fill: branch === "NO" ? "#b66a2d" : "#087f68", fontWeight: 700 },
      labelBgStyle: { fill: branch === "NO" ? "#fff3e7" : "#e8f6f2" },
    } as Edge;
    setEdges((current) => addEdge(edge, current));
    setNotice("");
  }, [nodes, setEdges]);

  const addNode = (type: "decision" | "end") => {
    const id = `${type}-${Math.random().toString(36).slice(2, 7)}`;
    const count = nodes.filter((node) => node.type === type).length + 1;
    const data = type === "decision"
      ? { label: `Decision ${count}`, prompt: "Should this request be approved? Return YES or NO.", mockDecision: "YES" as const, note: "" }
      : { label: `Outcome ${count}`, prompt: "", mockDecision: "YES" as const, note: "Workflow complete" };
    setNodes((current) => [...current, { id, type, position: { x: 280 + count * 54, y: 130 + count * 72 }, data }]);
    setSelectedNodeId(id);
    setNotice(`${type === "decision" ? "Decision" : "Outcome"} node added. Connect it to your flow.`);
  };

  const updateSelected = (key: keyof FlowNode["data"], value: string) => {
    if (!selectedNodeId) return;
    setNodes((current) => current.map((node) => node.id === selectedNodeId ? { ...node, data: { ...node.data, [key]: value } } : node));
  };

  const saveGraph = () => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(graph));
      setNotice("Flow saved on this device.");
    } catch { setNotice("This browser could not save local storage."); }
  };

  const loadStarter = () => {
    const example = starterGraph();
    setNodes(example.nodes);
    setEdges(example.edges);
    setSelectedNodeId(null);
    setNotice("Starter flow restored.");
  };

  const exportGraph = () => {
    const blob = new Blob([JSON.stringify(graph, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "flowline-decision-flow.json";
    anchor.click();
    URL.revokeObjectURL(url);
    setNotice("Flow JSON exported.");
  };

  const importGraph = async (file?: File) => {
    if (!file) return;
    try {
      const parsed = JSON.parse(await file.text()) as FlowGraph;
      if (!Array.isArray(parsed.nodes) || !Array.isArray(parsed.edges) || !parsed.nodes.length) throw new Error("Expected a graph with nodes and edges arrays.");
      setNodes(parsed.nodes);
      setEdges(parsed.edges);
      setSelectedNodeId(null);
      setNotice("Flow imported. Review validation before running.");
    } catch (error) {
      setNotice(error instanceof Error ? `Import failed: ${error.message}` : "Import failed: invalid JSON.");
    } finally {
      if (importRef.current) importRef.current.value = "";
    }
  };

  const runFlow = async () => {
    if (problems.length || pending) return;
    setPending(true);
    setNotice("");
    try {
      const response = await fetch("/api/runs", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ graph, input }),
      });
      const body = await response.json() as { id?: string; error?: string };
      if (!response.ok || !body.id) throw new Error(body.error || "Could not start the run.");
      setSelectedRunId(body.id);
      setNotice("Run queued with Inngest. Live step updates appear below.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not start the run.");
    } finally { setPending(false); }
  };

  const clearNotice = () => setNotice("");

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-lockup">
          <div className="brand-mark"><Workflow size={18} strokeWidth={2.4} /></div>
          <div><div className="brand-name">flowline</div><div className="brand-caption">DECISION STUDIO</div></div>
        </div>
        <div className="workspace-label">WORKSPACE</div>
        <button className="workspace-switch"><span className="workspace-avatar">S</span><span className="workspace-copy"><strong>Sandbox</strong><small>Personal workspace</small></span><ChevronDown size={14} /></button>
        <div className="side-section-title">BUILD</div>
        <button className="side-link active"><Workflow size={15} /><span>Decision flow</span><span className="side-dot" /></button>
        <button className="side-link" onClick={() => setNotice("Execution history is shown in the right-hand panel.")}><History size={15} /><span>Run history</span><span className="side-count">{runs.length}</span></button>
        <div className="side-section-title side-section-spaced">CANVAS TOOLS</div>
        <button className="side-link" onClick={() => addNode("decision")}><Bot size={15} /><span>Add decision</span><kbd>D</kbd></button>
        <button className="side-link" onClick={() => addNode("end")}><Flag size={15} /><span>Add outcome</span><kbd>O</kbd></button>
        <div className="sidebar-spacer" />
        <Card className="sidebar-tip">
          <CardContent>
            <div className="tip-icon"><Sparkles size={14} /></div>
            <strong>Build with confidence</strong>
            <p>Every node runs as a durable Inngest step, with a replayable log.</p>
            <a href="https://www.inngest.com/docs/learn/inngest-functions" target="_blank" rel="noreferrer">How it works <ArrowDownToLine size={12} /></a>
          </CardContent>
        </Card>
        <div className="sidebar-footer"><span className={`connection-light ${health}`} />{health === "online" ? "API connected" : health === "offline" ? "API unavailable" : "Checking local API"}<span>·</span><span>v1.0.0</span></div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumbs"><span>Sandbox</span><span className="crumb-slash">/</span><strong>Decision flow</strong><span className="draft-badge">LOCAL DRAFT</span></div>
          <div className="top-actions">
            <div className="provider-state"><span className="provider-dot" /><span>Mock AI</span><span className="provider-divider" /><span>On-device</span></div>
            <Button variant="outline" size="sm" onClick={saveGraph}><Save size={14} /> Save</Button>
            <Button onClick={runFlow} disabled={Boolean(problems.length) || pending || health !== "online"} size="sm" className="run-top"><Play size={13} fill="currentColor" />{pending ? "Starting…" : "Run flow"}</Button>
          </div>
        </header>

        <section className="editor-toolbar">
          <div className="editor-heading"><div className="flow-avatar"><GitBranch size={16} /></div><div><h1>Customer request routing</h1><p>Edited locally <span>·</span> Autosaved on this device</p></div></div>
          <div className="toolbar-actions">
            <Button variant="ghost" size="sm" onClick={() => addNode("decision")}><Plus size={14} /> Decision</Button>
            <Button variant="ghost" size="sm" onClick={() => addNode("end")}><Plus size={14} /> Outcome</Button>
            <span className="toolbar-separator" />
            <Button variant="ghost" size="sm" onClick={exportGraph}><Download size={14} /> Export</Button>
            <Button variant="ghost" size="sm" onClick={() => importRef.current?.click()}><Upload size={14} /> Import</Button>
            <input ref={importRef} hidden type="file" accept="application/json,.json" onChange={(event) => void importGraph(event.target.files?.[0])} />
          </div>
        </section>

        <div className="editor-body">
          <section className="canvas-column">
            <div className="canvas-topline"><span className="canvas-label"><span className="live-dot" /> VISUAL EDITOR</span><div className="canvas-actions"><button onClick={loadStarter} title="Restore example flow"><GitCommitHorizontal size={14} /> Restore example</button><span className="canvas-divider" /><span>{nodes.length} nodes <b>·</b> {edges.length} connections</span></div></div>
            <div className="canvas-wrap">
              <ReactFlow
                nodes={nodes}
                edges={edges}
                nodeTypes={NODE_TYPES}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={onConnect}
                onNodeClick={(_event, node) => setSelectedNodeId(node.id)}
                onPaneClick={() => setSelectedNodeId(null)}
                fitView
                fitViewOptions={{ padding: 0.22 }}
                minZoom={0.25}
                maxZoom={1.5}
                defaultEdgeOptions={{ type: "smoothstep", style: { stroke: "#a8b5c7", strokeWidth: 1.7 } }}
                proOptions={{ hideAttribution: true }}
              >
                <Background variant={BackgroundVariant.Dots} gap={20} size={1.25} color="#dce3ec" />
                <Controls position="bottom-left" showInteractive={false} />
                <MiniMap position="bottom-right" pannable zoomable nodeStrokeWidth={3} maskColor="rgba(247,249,252,.75)" />
              </ReactFlow>
              <div className="canvas-hint"><span className="hint-drag">⠿</span> Drag from a port to connect nodes <span>·</span> Select a node to edit</div>
            </div>
            <div className="validation-bar">
              <div className={`validation-icon ${problems.length ? "invalid" : "valid"}`}>{problems.length ? <AlertCircle size={14} /> : <Check size={14} />}</div>
              <div className="validation-copy"><strong>{problems.length ? `${problems.length} flow check${problems.length === 1 ? "" : "s"} to resolve` : "Flow is ready to run"}</strong><span>{problems.length ? problems[0] : "Both decision branches connect to an outcome."}</span></div>
              <button className="validation-detail" onClick={() => setNotice(problems.length ? problems.join(" ") : "Graph validation passed: one Start node, both decision branches connected, and an End node present.")}><CircleHelp size={14} /> Details</button>
            </div>
          </section>

          <aside className="inspector">
            {selectedNode ? (
              <Card className="inspector-card">
                <CardHeader><div className="inspector-title-row"><div><div className="overline">NODE SETTINGS</div><CardTitle>{selectedNode.type === "decision" ? "Decision node" : selectedNode.type === "start" ? "Start node" : "Outcome node"}</CardTitle></div><button className="icon-quiet" onClick={() => setSelectedNodeId(null)} aria-label="Close node settings"><X size={15} /></button></div></CardHeader>
                <CardContent>
                  <label className="field-label" htmlFor="node-label">Node name</label>
                  <Input id="node-label" value={selectedNode.data.label} onChange={(event) => updateSelected("label", event.target.value)} maxLength={64} />
                  {selectedNode.type === "decision" ? <>
                    <label className="field-label field-spaced" htmlFor="node-prompt">Decision prompt</label>
                    <Textarea id="node-prompt" value={selectedNode.data.prompt} onChange={(event) => updateSelected("prompt", event.target.value)} rows={4} maxLength={800} />
                    <div className="helper-text">The model response is constrained to YES or NO.</div>
                    <label className="field-label field-spaced" htmlFor="mock-decision">Local mock response</label>
                    <select id="mock-decision" className="field-input select-input" value={selectedNode.data.mockDecision} onChange={(event) => updateSelected("mockDecision", event.target.value)}>
                      <option value="YES">YES · follow the upper branch</option><option value="NO">NO · follow the lower branch</option>
                    </select>
                    <div className="mock-hint"><Sparkles size={13} /> Deterministic mock · no model call</div>
                  </> : <>
                    <label className="field-label field-spaced" htmlFor="node-note">{selectedNode.type === "start" ? "Entry note" : "Outcome message"}</label>
                    <Textarea id="node-note" value={selectedNode.data.note} onChange={(event) => updateSelected("note", event.target.value)} rows={3} maxLength={300} />
                  </>}
                  <div className="inspector-actions"><Button variant="outline" size="sm" onClick={() => setSelectedNodeId(null)}>Done</Button>{selectedNode.type !== "start" && <Button variant="danger" size="sm" onClick={() => { setNodes((current) => current.filter((node) => node.id !== selectedNode.id)); setEdges((current) => current.filter((edge) => edge.source !== selectedNode.id && edge.target !== selectedNode.id)); setSelectedNodeId(null); }}>Remove node</Button>}</div>
                </CardContent>
              </Card>
            ) : (
              <Card className="inspector-card run-card">
                <CardHeader><div className="overline">TEST YOUR FLOW</div><CardTitle>Run a scenario</CardTitle><p className="card-subtitle">Send a sample input through the graph and inspect each durable step.</p></CardHeader>
                <CardContent>
                  <label className="field-label" htmlFor="run-input">Sample input</label>
                  <Textarea id="run-input" value={input} onChange={(event) => setInput(event.target.value)} rows={4} maxLength={8000} placeholder="What should your workflow decide?" />
                  <div className="input-meta"><span>Used as the model context</span><span>{input.length}/8,000</span></div>
                  <div className="run-provider-note"><span className="mock-pill"><Sparkles size={11} /> MOCK</span><span>Predictable and free · choose YES / NO in node settings</span></div>
                  <Button className="run-full" disabled={Boolean(problems.length) || pending || health !== "online"} onClick={runFlow}><Play size={14} fill="currentColor" />{pending ? "Starting run…" : "Run this flow"}<span className="shortcut-key">↵</span></Button>
                  {health !== "online" && <div className="server-needed"><AlertCircle size={13} /> Start the local API and Inngest Dev Server to execute.</div>}
                </CardContent>
              </Card>
            )}

            <div className="history-heading"><div><div className="overline">OBSERVABILITY</div><h2><Activity size={15} /> Recent runs</h2></div><button onClick={() => { void refreshRuns(); setSelectedRunId(null); }}>Refresh</button></div>
            {runs.length === 0 ? (
              <div className="empty-history"><div className="empty-history-icon"><Clock3 size={17} /></div><strong>No runs yet</strong><span>Start a flow to see its ordered step log here.</span></div>
            ) : (
              <div className="run-list">
                {runs.slice(0, 5).map((run) => <button key={run.id} className={`run-item ${selectedRunId === run.id ? "selected" : ""}`} onClick={() => setSelectedRunId(run.id)}>
                  <span className={`run-status-icon ${run.status}`}>{run.status === "running" || run.status === "queued" ? <LoaderCircle size={13} className="spin" /> : run.status === "completed" ? <Check size={13} /> : <AlertCircle size={13} />}</span>
                  <span className="run-item-copy"><strong>{run.status === "completed" ? run.result || "Completed" : run.status === "failed" ? "Flow failed" : "Flow run"}</strong><small>{run.logs.length} steps <span>·</span> {relativeTime(run.createdAt)}</small></span>
                  <span className={statusClass(run.status)}>{run.status}</span>
                </button>)}
              </div>
            )}

            {selectedRun && <Card className="execution-card">
              <CardHeader><div className="execution-title"><div><div className="overline">RUN DETAILS</div><CardTitle>Execution trace</CardTitle></div><span className={statusClass(selectedRun.status)}>{selectedRun.status}</span></div><div className="execution-meta"><span><Clock3 size={12} /> {new Date(selectedRun.createdAt).toLocaleTimeString()}</span><span><Layers3 size={12} /> {selectedRun.provider} provider</span></div></CardHeader>
              <CardContent>
                {selectedRun.error && <div className="error-callout"><AlertCircle size={14} />{selectedRun.error}</div>}
                {selectedRun.logs.length === 0 ? <div className="trace-empty">Waiting for the first durable step…</div> : <div className="trace-list">{selectedRun.logs.map((log) => <div className="trace-row" key={log.id}>
                  <div className={`trace-marker ${log.status}`}>{log.status === "completed" ? <Check size={11} /> : <X size={11} />}</div>
                  <div className="trace-main"><div className="trace-name"><span>{String(log.order).padStart(2, "0")}</span><strong>{log.nodeLabel}</strong>{log.branch && <em className={log.branch === "YES" ? "branch-yes" : "branch-no"}>{log.branch}</em>}</div><small>{log.error || log.output || log.nodeType}</small></div>
                </div>)}</div>}
                {selectedRun.status === "completed" && <div className="result-callout"><Check size={14} /><span><strong>Flow completed</strong>{selectedRun.result && <small>{selectedRun.result}</small>}</span></div>}
              </CardContent>
            </Card>}
          </aside>
        </div>
        <footer className="app-footer"><span><span className={`connection-light ${health}`} /> {health === "online" ? "Local API connected" : health === "offline" ? "Local API offline" : "Connecting"}</span><span><GitCommitHorizontal size={13} /> Changes stay in this browser until exported</span><button onClick={() => setNotice("Flowline is a local learning project. The default mock uses no external AI service.")}><CircleHelp size={13} /> About</button></footer>
      </main>

      {notice && <div className="toast-message" role="status"><span>{notice}</span><button aria-label="Dismiss message" onClick={clearNotice}><X size={14} /></button></div>}
    </div>
  );
}
