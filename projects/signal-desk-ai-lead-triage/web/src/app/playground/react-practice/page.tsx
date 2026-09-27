"use client";

import { useMemo, useState } from "react";

const sampleLeads = [
  { name: "Northline Studio", service: "Identity system", budget: 8200, fit: "Strong" },
  { name: "Stillwater Objects", service: "Small ecommerce refresh", budget: 3900, fit: "Review" },
  { name: "Field Notes Press", service: "Editorial templates", budget: 5600, fit: "Strong" },
];

export default function ReactPracticePage() {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const filtered = useMemo(
    () => sampleLeads.filter((lead) => `${lead.name} ${lead.service}`.toLowerCase().includes(query.toLowerCase())),
    [query],
  );

  return (
    <main className="page-content">
      <header className="page-head">
        <div>
          <p className="eyebrow">Assignment · React practice</p>
          <h1>Small components, clear state</h1>
          <p>A standalone React exercise: filter synthetic leads, inspect one, and keep selection state predictable.</p>
        </div>
      </header>
      <section className="panel p-6" aria-labelledby="practice-heading">
        <h2 id="practice-heading" className="text-xl font-semibold">Lead list</h2>
        <label className="mt-5 block max-w-md text-sm font-medium" htmlFor="lead-search">Search by studio or service</label>
        <input
          id="lead-search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Try “identity”"
          className="mt-2 min-h-11 w-full max-w-md rounded-md border border-slate-300 px-3"
        />
        <ul className="mt-5 grid gap-3">
          {filtered.map((lead) => (
            <li key={lead.name}>
              <button
                type="button"
                className="w-full rounded-md border border-slate-200 p-4 text-left hover:bg-slate-50 focus-visible:outline-2"
                aria-pressed={selected === lead.name}
                onClick={() => setSelected((current) => current === lead.name ? null : lead.name)}
              >
                <span className="flex flex-wrap items-center justify-between gap-2 font-semibold">
                  {lead.name}<span className="mono text-xs font-normal">{lead.fit} fit · ${lead.budget.toLocaleString()}</span>
                </span>
                <span className="mt-1 block text-sm text-slate-600">{lead.service}</span>
              </button>
            </li>
          ))}
          {filtered.length === 0 ? <li className="text-sm text-slate-600">No sample leads match that search.</li> : null}
        </ul>
        <p className="mt-5 text-sm" aria-live="polite">
          {selected ? `${selected} selected for review.` : "Choose a lead to see the selection state."}
        </p>
      </section>
    </main>
  );
}
