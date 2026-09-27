import { draftReply } from "@/lib/ai/qualifier";
import { executeQualifyLead, qualifyLeadInput } from "@/lib/ai/qualify-tool";

export const runtime = "nodejs";
export const maxDuration = 30;

const requests = new Map<string, { count: number; resetAt: number }>();
const WINDOW_MS = 60_000;
const MAX_REQUESTS_PER_WINDOW = 20;
const MAX_BODY_BYTES = 6_000;

function allowed(request: Request) {
  const now = Date.now();
  const forwarded = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  const key = forwarded || "local";
  const previous = requests.get(key);
  if (!previous || previous.resetAt <= now) {
    requests.set(key, { count: 1, resetAt: now + WINDOW_MS });
    return true;
  }
  if (previous.count >= MAX_REQUESTS_PER_WINDOW) return false;
  previous.count += 1;
  return true;
}

function errorResponse(message: string, status: number, retryAfter?: number) {
  return Response.json({ error: message, retryAfter }, {
    status,
    headers: retryAfter ? { "Retry-After": String(retryAfter) } : undefined,
  });
}

export async function POST(request: Request) {
  if (!allowed(request)) return errorResponse("You've reached the short-term demo limit. Wait a minute and try again.", 429, 60);
  const rawBody = await request.text();
  if (new TextEncoder().encode(rawBody).byteLength > MAX_BODY_BYTES) return errorResponse("This request is too long. Keep the lead note under 1,200 characters.", 413);

  let raw: unknown;
  try {
    raw = JSON.parse(rawBody);
  } catch {
    return errorResponse("The request could not be read. Keep your draft and try again.", 400);
  }

  const parsed = qualifyLeadInput.safeParse(raw);
  if (!parsed.success) return errorResponse("Add a short request description and a question before analyzing.", 400);

  const scenario = raw && typeof raw === "object" && "demoFailure" in raw ? (raw as { demoFailure?: string }).demoFailure : undefined;
  if (scenario && process.env.NODE_ENV === "production") return errorResponse("Failure simulations are available in local development only.", 403);

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const encoder = new TextEncoder();
      const send = (value: Record<string, unknown>) => controller.enqueue(encoder.encode(`data: ${JSON.stringify(value)}\n\n`));
      const pause = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));
      try {
        send({ type: "tool-state", state: "input-streaming", tool: "qualifyLead" });
        await pause(100);
        if (scenario === "tool") throw new Error("The local scoring model was asked to return an invalid result.");
        send({ type: "tool-state", state: "input-available", tool: "qualifyLead", input: parsed.data });
        const result = await executeQualifyLead(parsed.data);
        send({ type: "tool-state", state: "output-available", tool: "qualifyLead", output: result });
        const reply = draftReply(result, parsed.data.question);
        const pieces = reply.match(/\S+\s*/g) ?? [reply];
        for (const [index, piece] of pieces.entries()) {
          if (request.signal.aborted) break;
          if (scenario === "mid-stream" && index > 5) throw new Error("The example stream stopped unexpectedly.");
          send({ type: "assistant-delta", text: piece });
          await pause(22);
        }
        if (!request.signal.aborted) send({ type: "done" });
      } catch {
        if (!request.signal.aborted) send({ type: "tool-state", state: "output-error", tool: "qualifyLead", message: "The analysis stopped before a result was ready. Your request is still here; retry when ready." });
      } finally {
        try { controller.close(); } catch { /* The client may have cancelled the stream. */ }
      }
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
