export const dynamic = "force-dynamic";

export async function GET() {
  return Response.json({
    status: "ok",
    app: "Signal Desk",
    model: "local-logistic-regression",
    sampleData: "synthetic",
    checkedAt: new Date().toISOString(),
  }, { headers: { "Cache-Control": "no-store" } });
}
