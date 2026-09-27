import { memo } from "react";
import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";
import { Bot, CirclePlay, Flag, Sparkles } from "lucide-react";
import type { FlowNodeData } from "@/lib/workflow";

function FlowNodeCard({ id, data, type, selected }: NodeProps<Node<FlowNodeData>>) {
  const decision = type === "decision";
  const start = type === "start";
  const Icon = start ? CirclePlay : decision ? Bot : Flag;
  return (
    <div className={`flow-node flow-node-${type}${selected ? " selected" : ""}`}>
      {!start && <Handle className="node-handle" type="target" position={Position.Left} id="in" />}
      <div className="flow-node-topline">
        <span className="node-icon"><Icon size={15} /></span>
        <span className="node-kind">{start ? "TRIGGER" : decision ? "AI DECISION" : "OUTCOME"}</span>
        {decision && <span className="node-ai"><Sparkles size={11} /> AI</span>}
        <span className="node-id">{id.slice(0, 5)}</span>
      </div>
      <div className="flow-node-title">{data.label}</div>
      <div className="flow-node-copy">{start ? data.note || "Workflow entry point" : decision ? data.prompt || "Choose a decision prompt" : data.note || "Workflow destination"}</div>
      {decision ? (
        <div className="branch-ports">
          <div className="branch-port yes"><span>YES</span><Handle className="node-handle yes-handle" type="source" position={Position.Right} id="yes" /></div>
          <div className="branch-port no"><span>NO</span><Handle className="node-handle no-handle" type="source" position={Position.Right} id="no" /></div>
        </div>
      ) : start ? (
        <Handle className="node-handle" type="source" position={Position.Right} id="out" />
      ) : null}
    </div>
  );
}

export default memo(FlowNodeCard);
