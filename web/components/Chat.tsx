"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { streamChat, type Citation } from "@/lib/api";
import { Message, type ChatMessage } from "@/components/Message";

const SUGGESTIONS = [
  "How is the reciprocal rank fusion score computed?",
  "When are TA office hours?",
  "Can I use a late day on the final project?",
];

const SESSION_KEY = "gator-ta.session";

export function Chat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    setSessionId(window.sessionStorage.getItem(SESSION_KEY));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const updateLast = useCallback((patch: (m: ChatMessage) => ChatMessage) => {
    setMessages((prev) => {
      if (prev.length === 0) return prev;
      const next = prev.slice();
      next[next.length - 1] = patch(next[next.length - 1]);
      return next;
    });
  }, []);

  const send = useCallback(
    async (question: string) => {
      const trimmed = question.trim();
      if (!trimmed || busy) return;
      setError(null);
      setInput("");
      setBusy(true);
      setMessages((prev) => [
        ...prev,
        { id: `u-${Date.now()}`, role: "user", content: trimmed },
        { id: `a-${Date.now()}`, role: "assistant", content: "", citations: [], tools: [], streaming: true },
      ]);

      const controller = new AbortController();
      abortRef.current = controller;
      try {
        for await (const event of streamChat(trimmed, sessionId, controller.signal)) {
          switch (event.type) {
            case "session":
              setSessionId(event.session_id);
              window.sessionStorage.setItem(SESSION_KEY, event.session_id);
              break;
            case "citations":
              updateLast((m) => ({ ...m, citations: event.citations as Citation[] }));
              break;
            case "tool_call":
              updateLast((m) => ({ ...m, tools: [...(m.tools ?? []), event.name] }));
              break;
            case "token":
              updateLast((m) => ({ ...m, content: m.content + event.text }));
              break;
            case "done":
              updateLast((m) => ({ ...m, content: event.answer, messageId: event.message_id, streaming: false }));
              break;
            case "error":
              setError(event.message);
              updateLast((m) => ({ ...m, streaming: false }));
              break;
          }
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") setError((err as Error).message);
        updateLast((m) => ({ ...m, streaming: false }));
      } finally {
        setBusy(false);
        abortRef.current = null;
      }
    },
    [busy, sessionId, updateLast],
  );

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send(input);
    }
  };

  return (
    <section className="chat">
      <div className="messages">
        {messages.length === 0 ? (
          <div className="empty">
            <p>Try one of these:</p>
            {SUGGESTIONS.map((s) => (
              <button key={s} onClick={() => void send(s)}>
                {s}
              </button>
            ))}
          </div>
        ) : (
          messages.map((m) => <Message key={m.id} message={m} sessionId={sessionId} />)
        )}
        <div ref={bottomRef} />
      </div>
      {error && <p className="error">Something went wrong: {error}</p>}
      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          void send(input);
        }}
      >
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Ask a question about the course…"
          rows={1}
          disabled={busy}
        />
        <button type="submit" disabled={busy || !input.trim()}>
          {busy ? "…" : "Send"}
        </button>
      </form>
    </section>
  );
}
