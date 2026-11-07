"use client";

import { useState } from "react";
import { sendFeedback, type Citation } from "@/lib/api";
import { Citations } from "@/components/Citations";

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  messageId?: string;
  citations?: Citation[];
  tools?: string[];
  streaming?: boolean;
};

export function Message({ message, sessionId }: { message: ChatMessage; sessionId: string | null }) {
  const [rating, setRating] = useState<1 | -1 | null>(null);

  const rate = async (value: 1 | -1) => {
    if (!sessionId || !message.messageId || rating === value) return;
    setRating(value);
    try {
      await sendFeedback(sessionId, message.messageId, value);
    } catch {
      setRating(null);
    }
  };

  if (message.role === "user") {
    return <div className="message user">{message.content}</div>;
  }

  const citedNumbers = new Set(
    Array.from(message.content.matchAll(/\[(\d+)\]/g), (m) => Number(m[1])),
  );
  const cited = (message.citations ?? []).filter((c) => citedNumbers.has(c.n));

  return (
    <div className="message assistant">
      {message.tools && message.tools.length > 0 && (
        <div className="tool">looked up: {message.tools.join(", ")}</div>
      )}
      <span className={message.streaming ? "cursor" : undefined}>{message.content}</span>
      {!message.streaming && cited.length > 0 && <Citations citations={cited} />}
      {!message.streaming && message.messageId && (
        <div className="meta">
          <span>Was this helpful?</span>
          <button className={rating === 1 ? "active" : undefined} onClick={() => void rate(1)}>
            Yes
          </button>
          <button className={rating === -1 ? "active" : undefined} onClick={() => void rate(-1)}>
            No
          </button>
        </div>
      )}
    </div>
  );
}
