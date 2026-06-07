type HistoryTurn = { role: "user" | "assistant"; content: string };

/**
 * Build a prompt that includes conversation history so the droid has context
 * of prior turns (simulated continuity across one-shot exec calls).
 */
export function buildPrompt(message: string, history: HistoryTurn[]): string {
  if (!history || history.length === 0) {
    return message;
  }

  const historyBlock = history
    .map(
      (turn) =>
        `${turn.role === "user" ? "User" : "Assistant"}: ${turn.content}`
    )
    .join("\n\n");

  return [
    "<conversation_history>",
    historyBlock,
    "</conversation_history>",
    "",
    `User: ${message}`,
    "",
    "Continue the conversation. The latest user request is shown after the history. Use the conversation history for context of prior turns.",
  ].join("\n");
}
