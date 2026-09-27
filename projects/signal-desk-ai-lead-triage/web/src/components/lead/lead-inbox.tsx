"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

type LeadSummary = {
  id: string;
  name: string;
  company: string;
  service: string;
  budget: string;
  timeline: string;
  source: string;
  status: string;
  created: string;
  description: string;
  score: number;
};

const filters = [
  { key: "all", label: "All requests" },
  { key: "strong", label: "Strong signal" },
  { key: "context", label: "Needs context" },
  { key: "early", label: "Early / mismatch" },
] as const;

function scoreTone(score: number) {
  return score >= 66 ? "" : score >= 42 ? "mid" : "low";
}

export function LeadInbox({ leads }: { leads: LeadSummary[] }) {
  const [filter, setFilter] = useState<(typeof filters)[number]["key"]>("all");
  const filtered = useMemo(() => leads.filter((lead) => {
    if (filter === "strong") return lead.score >= 66;
    if (filter === "context") return lead.score >= 42 && lead.score < 66;
    if (filter === "early") return lead.score < 42;
    return true;
  }), [leads, filter]);

  return (
    <section className="panel" aria-labelledby="inbox-title">
      <div className="panel-head">
        <div><h2 className="panel-title" id="inbox-title">Recent requests</h2><p className="panel-subtitle">Select a request to review its context and signals.</p></div>
        <span className="signal-tag">{filtered.length} shown</span>
      </div>
      <div className="filter-bar" role="group" aria-label="Filter lead requests">
        {filters.map((item) => <button className="filter-chip" type="button" key={item.key} aria-pressed={filter === item.key} onClick={() => setFilter(item.key)}>{item.label}</button>)}
      </div>
      {filtered.length ? <div className="lead-list">
        {filtered.map((lead) => (
          <Link className={`lead-row ${lead.score >= 66 ? "is-priority" : ""}`} href={`/leads/${lead.id}`} key={lead.id} aria-label={`Open ${lead.company} request, signal ${lead.score} out of 100`}>
            <span>
              <span className="lead-name">{lead.name}<span className="lead-company"> · {lead.company}</span></span>
              <span className="lead-excerpt">{lead.description}</span>
              <span className="lead-meta"><span className="signal-tag">{lead.service}</span><span>{lead.timeline}</span><span>{lead.source}</span><span>{lead.created}</span></span>
            </span>
            <span className={`score-pill ${scoreTone(lead.score)}`} aria-label={`Fit signal ${lead.score} out of 100`}>{lead.score}<small>/100</small></span>
          </Link>
        ))}
      </div> : <div className="empty-screen" style={{ minHeight: 240, padding: 20 }}><div><h3>No requests in this group</h3><p>Choose another filter to return to the inbox.</p><button className="button secondary" type="button" onClick={() => setFilter("all")}>Show all requests</button></div></div>}
    </section>
  );
}
