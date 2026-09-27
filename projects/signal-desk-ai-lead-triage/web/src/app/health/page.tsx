import { headers } from "next/headers";

export const dynamic = "force-dynamic";

export default async function HealthPage() {
  const requestHeaders = await headers();
  const host = requestHeaders.get("x-forwarded-host") ?? requestHeaders.get("host");
  const protocol = requestHeaders.get("x-forwarded-proto") ?? "http";

  if (!host) {
    return (
      <main className="page-content">
        <h1>Health check unavailable</h1>
        <p>The request did not include a host, so this page could not fetch its health endpoint.</p>
      </main>
    );
  }

  let result: { status: string; app: string; model: string; sampleData: string; checkedAt: string } | null = null;
  let error: string | null = null;

  try {
    const response = await fetch(`${protocol}://${host}/api/health`, { cache: "no-store" });
    if (!response.ok) throw new Error(`Health endpoint returned ${response.status}.`);
    result = await response.json();
  } catch (caught) {
    error = caught instanceof Error ? caught.message : "The health endpoint could not be reached.";
  }

  return (
    <main className="page-content">
      <header className="page-head">
        <div>
          <p className="eyebrow">System status</p>
          <h1>Health check</h1>
          <p>This page fetches the app health endpoint on the server for each request.</p>
        </div>
      </header>
      <section className="panel p-6" aria-live="polite">
        {result ? (
          <dl>
            <div><dt className="summary-label">Status</dt><dd className="summary-value">{result.status}</dd></div>
            <div><dt className="summary-label">App</dt><dd>{result.app}</dd></div>
            <div><dt className="summary-label">Scoring</dt><dd>{result.model}</dd></div>
            <div><dt className="summary-label">Data</dt><dd>{result.sampleData}</dd></div>
            <div><dt className="summary-label">Checked at</dt><dd className="mono">{result.checkedAt}</dd></div>
          </dl>
        ) : (
          <p role="alert">Could not fetch health data: {error}</p>
        )}
      </section>
    </main>
  );
}
