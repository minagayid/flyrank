import Link from "next/link";
import { LeadInbox } from "@/components/lead/lead-inbox";
import { getLeadSummaries } from "@/lib/data/leads";
import { extractFeatures, type FeatureKey } from "@/lib/ai/features";

export default function Home() {
  const leads = getLeadSummaries();
  const urgent = leads.filter((lead) => lead.timeline === "Within 4 weeks").length;
  const average = Math.round(leads.reduce((sum, lead) => sum + lead.score, 0) / leads.length);
  const cueConfig: Array<{ key: FeatureKey; label: string }> = [
    { key: "concrete_scope", label: "Clear scope" },
    { key: "budget_stated", label: "Budget stated" },
    { key: "near_term", label: "Near-term timing" },
  ];
  const cueCounts = cueConfig.map((cue) => ({
    ...cue,
    count: leads.filter((lead) => extractFeatures(lead)[cue.key] === 1).length,
  }));

  return (
    <main className="page-content">
      <div className="page-head">
        <div>
          <p className="eyebrow">STUDIO INTAKE</p>
          <h1>Lead review</h1>
          <p>Read the request first. Use the model&apos;s signals to decide what deserves a closer look.</p>
        </div>
        <Link className="button" href="/playground/react-practice">Explore the practice build <span aria-hidden="true">↗</span></Link>
      </div>

      <section className="summary-strip" aria-label="Lead overview">
        <div className="summary-cell"><span className="summary-label">Open requests</span><strong className="summary-value">{leads.length.toString().padStart(2, "0")}</strong><span className="summary-detail">Synthetic sample inbox</span></div>
        <div className="summary-cell"><span className="summary-label">Needs a reply soon</span><strong className="summary-value">{urgent.toString().padStart(2, "0")}</strong><span className="summary-detail">Timeline within four weeks</span></div>
        <div className="summary-cell"><span className="summary-label">Mean fit signal</span><strong className="summary-value">{average}<small style={{ fontSize: 13, fontWeight: 500 }}>/100</small></strong><span className="summary-detail">Model estimate, not a decision</span></div>
        <div className="summary-cell"><span className="summary-label">Model</span><strong className="summary-value" style={{ fontSize: 18 }}>Local</strong><span className="summary-detail">No external provider or key</span></div>
      </section>

      <div className="inbox-layout">
        <LeadInbox leads={leads} />
        <aside className="panel signal-map" aria-labelledby="signal-map-title">
          <h2 id="signal-map-title">What the model looks for</h2>
          <p>Rule matches in the four synthetic sample requests.</p>
          {cueCounts.map((cue) => <div className="map-row" key={cue.key}><span className="map-label">{cue.label}</span><div className="bar-track" aria-hidden="true"><div className={`bar-fill ${cue.key === "near_term" ? "attention" : ""}`} style={{ width: `${leads.length ? Math.round(cue.count / leads.length * 100) : 0}%` }} /></div><span className="map-count" aria-label={`${cue.count} of ${leads.length} synthetic examples`}>{String(cue.count).padStart(2, "0")}</span></div>)}
          <div className="proof-note"><strong>Keep the human in the loop</strong>Scores summarize synthetic examples. Check the original request and ask before drawing a conclusion.</div>
          <nav className="practice-links" aria-label="Frontend assignment exercises">
            <Link href="/playground/accessibility">Accessible widgets</Link>
            <Link href="/playground/motion">Motion states</Link>
            <Link href="/playground/3d">3D scene</Link>
            <Link href="/playground/shader">Shader hero</Link>
          </nav>
        </aside>
      </div>
    </main>
  );
}
