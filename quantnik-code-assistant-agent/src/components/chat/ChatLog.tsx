import React from "react";
import { renderMarkdown } from "../../lib/markdown";

type Turn = {
  id?: string;
  role: "user" | "assistant" | "meta";
  content: string;
  isHtml?: boolean;
  tone?: "muted" | "dark";
};

type Props = {
  logRef: React.RefObject<HTMLDivElement>;
  messages: Turn[];
};

export default function ChatLog({ logRef, messages }: Props) {
  return (
    <div ref={logRef} className="chat-log" aria-live="polite">
      {messages.map((turn, index) => {
        const role = turn.role === "meta" ? "debug" : turn.role;
        const assistantText = turn.role === "assistant" ? turn.content.trim().toLowerCase() : "";
        const isAssistantError =
          turn.role === "assistant" &&
          (assistantText.startsWith("error:") ||
            assistantText.includes("timed out") ||
            assistantText.startsWith("command exited with code") ||
            assistantText.includes("agent stalled without progress"));
        if (turn.role === "assistant" || (turn.role === "meta" && turn.isHtml)) {
          return (
            <div
              key={turn.id ?? index}
              className="chat-msg"
              data-role={role}
              data-error={isAssistantError ? "true" : undefined}
              data-tone={turn.role === "meta" ? turn.tone ?? "muted" : undefined}
              dangerouslySetInnerHTML={{ __html: turn.role === "assistant" ? renderMarkdown(turn.content) : turn.content }}
            />
          );
        }
        return (
          <div key={turn.id ?? index} className="chat-msg" data-role={role}>
            {turn.content}
          </div>
        );
      })}
    </div>
  );
}

