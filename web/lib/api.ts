/**
 * Client for the GatorTA API. `/chat` streams server-sent events over a POST body, which the
 * EventSource API cannot do, so the stream is parsed by hand from a fetch ReadableStream.
 */

export type Citation = {
  n: number;
  chunk_id: number;
  label: string;
  heading: string;
  source: string;
  page: number | null;
  snippet: string;
};

export type ChatEvent =
  | { type: "session"; session_id: string }
  | { type: "citations"; citations: Citation[] }
  | { type: "tool_call"; name: string; arguments: Record<string, unknown> }
  | { type: "token"; text: string }
  | { type: "done"; message_id: string; answer: string; tool_rounds: number }
  | { type: "error"; message: string };

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") ?? "http://localhost:8000";

/** Split a buffer of SSE text into complete `data:` payloads, returning the unparsed remainder. */
export function parseSseChunk(buffer: string): { events: ChatEvent[]; rest: string } {
  const events: ChatEvent[] = [];
  let rest = buffer;
  let boundary = rest.indexOf("\n\n");
  while (boundary !== -1) {
    const frame = rest.slice(0, boundary);
    rest = rest.slice(boundary + 2);
    for (const line of frame.split("\n")) {
      if (line.startsWith("data: ")) {
        events.push(JSON.parse(line.slice(6)) as ChatEvent);
      }
    }
    boundary = rest.indexOf("\n\n");
  }
  return { events, rest };
}

export async function* streamChat(
  question: string,
  sessionId: string | null,
  signal?: AbortSignal,
): AsyncGenerator<ChatEvent> {
  const response = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, session_id: sessionId }),
    signal,
  });
  if (!response.ok || !response.body) {
    throw new Error(`chat request failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const { events, rest } = parseSseChunk(buffer);
    buffer = rest;
    for (const event of events) yield event;
  }
}

export async function sendFeedback(
  sessionId: string,
  messageId: string,
  rating: 1 | -1,
  comment = "",
): Promise<void> {
  const response = await fetch(`${API_BASE}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message_id: messageId, rating, comment }),
  });
  if (!response.ok) throw new Error(`feedback failed: ${response.status}`);
}
