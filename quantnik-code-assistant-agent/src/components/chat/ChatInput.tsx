import React from "react";
import Spinner from "../Spinner";

type Props = {
  textareaRef: React.RefObject<HTMLTextAreaElement>;
  onSubmit: (event: React.FormEvent) => void;
  autoGrow: () => void;
  disabled?: boolean;
  disabledPlaceholder?: string;
  loading: boolean;
  spinnerText: string;
  commandOutput: Array<{ id?: string; content: string; isHtml?: boolean; tone?: "muted" | "dark" }>;
};

export default function ChatInput({
  textareaRef,
  onSubmit,
  autoGrow,
  disabled = false,
  disabledPlaceholder = "Complete repository lock setup to start chatting...",
  loading,
  spinnerText,
  commandOutput
}: Props) {
  const [isInfoExpanded, setIsInfoExpanded] = React.useState(true);
  const secondaryLogRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (!isInfoExpanded) return;
    const el = secondaryLogRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [commandOutput, isInfoExpanded]);

  const clearInput = () => {
    if (!textareaRef.current) return;
    textareaRef.current.value = "";
    autoGrow();
    textareaRef.current.focus();
  };

  return (
    <form className="chat-input" onSubmit={onSubmit}>
      <div className="chat-input-row">
        <textarea
          ref={textareaRef}
          placeholder={disabled ? disabledPlaceholder : "Enter your prompt here..."}
          onInput={autoGrow}
          disabled={disabled}
          onKeyDown={(event) => {
            if (disabled) return;
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              onSubmit(event as unknown as React.FormEvent);
            }
          }}
          rows={1}
        />
        <button type="submit" className="chat-send-btn" aria-label="Send message" disabled={disabled}>
          ➤
        </button>
        <button type="button" className="chat-reset-btn" aria-label="Clear input" onClick={clearInput} disabled={disabled}>
          ↻
        </button>
      </div>
      <div className={`chat-secondary-box ${isInfoExpanded ? "expanded" : "collapsed"}`}>
        <button
          type="button"
          className="chat-secondary-toggle"
          aria-expanded={isInfoExpanded}
          onClick={() => setIsInfoExpanded((prev) => !prev)}
        >
          <span className="chat-secondary-title">Command Output</span>
          <span className="chat-secondary-chevron" aria-hidden="true">
            {isInfoExpanded ? "▾" : "▸"}
          </span>
        </button>
        <div ref={secondaryLogRef} className="chat-secondary-content" role="region" aria-label="Command output">
          {commandOutput.length ? (
            commandOutput.map((entry, index) => (
              <div
                key={entry.id ?? `${index}-${entry.content.slice(0, 24)}`}
                className="chat-msg"
                data-role="debug"
                data-tone={entry.tone ?? "muted"}
                dangerouslySetInnerHTML={{ __html: entry.content }}
              />
            ))
          ) : (
            <div className="chat-secondary-empty">Awaiting command execution output...</div>
          )}
          {loading && <Spinner status={spinnerText} />}
        </div>
      </div>
    </form>
  );
}

