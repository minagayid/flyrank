"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import type { QualificationResult } from "@/lib/ai/qualifier";
import type { SampleLead } from "@/lib/data/leads";

type ChatMessage = { id: string; role: "user" | "assistant"; text: string; streaming?: boolean };
type ToolState = "input-streaming" | "input-available" | "output-available" | "output-error";
type ToolStatus = { state: ToolState; message?: string; output?: QualificationResult };
type EventPayload = { type: string; state?: ToolState; message?: string; text?: string; output?: QualificationResult };

const suggestions = ["Why did this score well?", "What should I ask next?", "Which details are still missing?"];

function id() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
}

function ToolStatePanel({ status }: { status: ToolStatus }) {
  const title: Record<ToolState, string> = {
    "input-streaming": "Reading the request",
    "input-available": "Request checked · scoring in progress",
    "output-available": "Qualification result ready",
    "output-error": "Analysis stopped",
  };
  const description: Record<ToolState, string> = {
    "input-streaming": "The tool is receiving the lead context.",
    "input-available": "The request passed the input check and is being scored locally.",
    "output-available": "A typed result is ready to review alongside the original request.",
    "output-error": status.message ?? "No score came back. Keep the draft and retry.",
  };

  return <section className="tool-state" data-state={status.state} aria-label={`Qualification tool: ${title[status.state]}`}>
    <div className="tool-state-title">{title[status.state]}</div>
    <p>{description[status.state]}</p>
    {status.output && <div className="tool-score"><span>{status.output.label}</span><strong>{status.output.score}/100</strong></div>}
    {status.output && <ul className="evidence-list" aria-label="Model evidence">{status.output.supportingSignals.slice(0, 2).map((signal) => <li key={signal}><span className="evidence-dot" aria-hidden="true" />{signal}</li>)}{status.output.cautions.slice(0, 1).map((signal) => <li key={signal}><span className="evidence-dot caution" aria-hidden="true" />{signal}</li>)}</ul>}
  </section>;
}

export function LeadWorkspace({ lead }: { lead: SampleLead }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [toolStatus, setToolStatus] = useState<ToolStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [jumpVisible, setJumpVisible] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const pinned = useRef(true);
  const activeRequest = useRef<AbortController | null>(null);
  const loadedStorage = useRef(false);
  const storageKey = `signal-desk:${lead.id}:conversation`;

  useEffect(() => {
    const loadTimer = window.setTimeout(() => {
      try {
        const stored = sessionStorage.getItem(storageKey);
        if (stored) setMessages(JSON.parse(stored) as ChatMessage[]);
      } catch {
        try { sessionStorage.removeItem(storageKey); } catch { /* Storage can be unavailable in a private context. */ }
      } finally {
        loadedStorage.current = true;
      }
    }, 0);
    return () => {
      window.clearTimeout(loadTimer);
      activeRequest.current?.abort();
    };
  }, [storageKey]);

  useEffect(() => {
    if (!loadedStorage.current) return;
    try { sessionStorage.setItem(storageKey, JSON.stringify(messages)); } catch { /* Storage may be unavailable in a private context. */ }
  }, [messages, storageKey]);

  useEffect(() => {
    if (pinned.current && scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, toolStatus]);

  const sendQuestion = useCallback(async (rawQuestion: string, retry = false, demoFailure?: string) => {
    const text = rawQuestion.trim();
    if (!text || sending) return;
    const assistantId = id();
    setError(null);
    setToolStatus({ state: "input-streaming" });
    setSending(true);
    if (!retry) setMessages((current) => [...current, { id: id(), role: "user", text }, { id: assistantId, role: "assistant", text: "", streaming: true }]);
    else setMessages((current) => [...current.filter((message) => !(message.role === "assistant" && message.streaming)), { id: assistantId, role: "assistant", text: "", streaming: true }]);
    setQuestion("");
    const controller = new AbortController();
    activeRequest.current = controller;

    try {
      const response = await fetch("/api/qualify", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify({ ...lead, question: text, demoFailure }),
        signal: controller.signal,
      });
      if (!response.ok || !response.body) {
        const data = await response.json().catch(() => ({})) as { error?: string };
        throw new Error(data.error ?? "The analysis could not start. Your draft is ready to retry.");
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let failed = false;
      const handle = (eventText: string) => {
        const line = eventText.split("\n").find((item) => item.startsWith("data: "));
        if (!line) return;
        let event: EventPayload;
        try { event = JSON.parse(line.slice(6)) as EventPayload; } catch { return; }
        if (event.type === "tool-state" && event.state) {
          setToolStatus({ state: event.state, message: event.message, output: event.output });
          if (event.state === "output-error") failed = true;
        }
        if (event.type === "assistant-delta" && event.text) {
          setMessages((current) => current.map((message) => message.id === assistantId ? { ...message, text: message.text + event.text } : message));
        }
        if (event.type === "done") setMessages((current) => current.map((message) => message.id === assistantId ? { ...message, streaming: false } : message));
      };

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() ?? "";
        events.forEach(handle);
      }
      if (buffer.trim()) handle(buffer);
      if (failed) {
        setMessages((current) => current.flatMap((message) => {
          if (message.id !== assistantId) return [message];
          return message.text.trim() ? [{ ...message, streaming: false }] : [];
        }));
        setQuestion(text);
        setError("The scoring tool stopped. Your question is still in the box.");
      }
    } catch (reason) {
      if (reason instanceof DOMException && reason.name === "AbortError") {
        setMessages((current) => current.map((message) => message.id === assistantId ? { ...message, streaming: false } : message));
      } else {
        setMessages((current) => current.filter((message) => message.id !== assistantId));
        setQuestion(text);
        setError(reason instanceof Error ? reason.message : "The request stopped unexpectedly. Your question is still in the box.");
        setToolStatus({ state: "output-error", message: "The request did not finish. Retry the preserved question when ready." });
      }
    } finally {
      activeRequest.current = null;
      setSending(false);
    }
  }, [lead, sending]);

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void sendQuestion(question);
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendQuestion(question);
    }
  }

  const result = toolStatus?.output;
  const nextQuestion = result?.openQuestions[0] ?? "Which result matters most to the project?";
  const draft = `Thanks for sharing this with us. Before we suggest a scope, could you tell us ${nextQuestion.toLowerCase()} We can then propose a focused next step.`;

  return <div className="detail-grid">
    <div className="detail-stack">
      <section className="panel intake-card" aria-labelledby="request-title">
        <div className="intake-head"><div><p className="eyebrow">{lead.status} · {lead.source} · {lead.created}</p><h2 id="request-title">{lead.name}</h2><div className="intake-company">{lead.company}</div></div><span className="signal-tag">Sample record</span></div>
        <div className="perforation" aria-hidden="true" />
        <p className="quote-label">ORIGINAL REQUEST · SYNTHETIC EXAMPLE</p>
        <blockquote className="request-copy">“{lead.description}”</blockquote>
        <div className="intake-facts">
          <div><span className="fact-label">SERVICE</span><span className="fact-value">{lead.service}</span></div>
          <div><span className="fact-label">BUDGET</span><span className="fact-value">{lead.budget}</span></div>
          <div><span className="fact-label">TIMELINE</span><span className="fact-value">{lead.timeline}</span></div>
        </div>
      </section>

      {result && <section className="panel score-card" aria-labelledby="score-title">
        <div className="score-card-head"><h2 id="score-title">Fit signal</h2><span className="signal-tag">{result.model}</span></div>
        <div className="score-number">{result.score}<small style={{ fontSize: 14, fontWeight: 500 }}>/100</small></div>
        <div className="score-context">{result.label} · check the evidence before prioritizing.</div>
        <ul className="evidence-list">{result.supportingSignals.map((signal) => <li key={signal}><span className="evidence-dot" aria-hidden="true" />{signal}</li>)}{result.cautions.map((signal) => <li key={signal}><span className="evidence-dot caution" aria-hidden="true" />{signal}</li>)}</ul>
        <p className="model-disclaimer">Model trained on synthetic examples. Its score is not calibrated against real client outcomes.</p>
      </section>}

      <section className="panel next-step" aria-labelledby="next-step-title">
        <h2 id="next-step-title">Possible next step</h2>
        <p>An editable draft based on the details still missing. It is never sent automatically.</p>
        <div className="draft-box">{draft}</div>
        <div className="draft-actions"><span className="status-message">Review and edit before using</span><Link className="ghost-link" href="/playground/accessibility">Review keyboard patterns</Link></div>
      </section>
    </div>

    <section className="panel chat-card" aria-labelledby="assistant-title">
      <div className="panel-head"><div><h2 className="panel-title" id="assistant-title">Request assistant</h2><p className="panel-subtitle">Local model · no provider key or external API call</p></div>{sending && <button className="button secondary" type="button" onClick={() => activeRequest.current?.abort()}>Stop</button>}</div>
      <div className="chat-log" ref={scrollRef} role="log" aria-label="Conversation with the request assistant" aria-live="polite" aria-relevant="additions text" onScroll={(event) => { const element = event.currentTarget; pinned.current = element.scrollHeight - element.scrollTop - element.clientHeight < 90; setJumpVisible(!pinned.current); }}>
        {!messages.length ? <div className="chat-empty"><div><h3>Ask about this request</h3><p>The model can summarize visible evidence and suggest a question to clarify.</p><div className="suggestions">{suggestions.map((suggestion) => <button className="suggestion" key={suggestion} type="button" onClick={() => setQuestion(suggestion)}>{suggestion}</button>)}</div></div></div> : messages.map((message) => <div className={`message ${message.role}`} key={message.id}><div className="message-label">{message.role === "user" ? "YOU" : "SIGNAL DESK · LOCAL MODEL"}</div><div className="message-bubble" aria-live={message.streaming ? "polite" : undefined}>{message.text}{message.streaming && <span className="stream-cursor" aria-label="Response streaming" />}</div></div>)}
        {jumpVisible && <button className="suggestion" type="button" onClick={() => { if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight; pinned.current = true; setJumpVisible(false); }}>Jump to latest</button>}
      </div>
      {toolStatus && <div style={{ padding: "0 16px" }}><ToolStatePanel status={toolStatus} /></div>}
      {error && <div className="chat-error" role="alert">{error}<button type="button" onClick={() => void sendQuestion(question, true)}>Retry</button></div>}
      <form className="chat-compose" onSubmit={onSubmit}>
        <label className="sr-only" htmlFor={`question-${lead.id}`}>Ask about this lead</label>
        <textarea id={`question-${lead.id}`} value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={onKeyDown} placeholder="Ask what stands out or what to clarify…" maxLength={400} aria-describedby={`question-help-${lead.id}`} />
        <button className="button accent" type="submit" disabled={sending || !question.trim()}>{sending ? "Working…" : "Analyze"}</button>
      </form>
      <p className="chat-footnote" id={`question-help-${lead.id}`}>Enter to analyze · Shift + Enter for a new line · Up to 400 characters</p>
      {process.env.NODE_ENV !== "production" && <div style={{ display: "flex", gap: 7, padding: "0 16px 14px" }}><span className="status-message">Local failure demos:</span><button className="suggestion" type="button" disabled={sending} onClick={() => { setQuestion("What should I ask next?"); void sendQuestion("What should I ask next?", false, "tool"); }}>Tool error</button><button className="suggestion" type="button" disabled={sending} onClick={() => { setQuestion("Why did this score well?"); void sendQuestion("Why did this score well?", false, "mid-stream"); }}>Stop mid-stream</button></div>}
    </section>
  </div>;
}
