import { useEffect, useRef, useState, type FormEvent } from "react";
import type { ChatThread } from "../types";

interface Props {
  thread: ChatThread | undefined;
  sending: boolean;
  onSend: (text: string) => void;
}

export default function ChatWindow({ thread, sending, onSend }: Props) {
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  // Autoscroll to the newest message.
  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [thread?.messages.length, sending]);

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!draft.trim() || sending) return;
    onSend(draft);
    setDraft("");
  }

  const messages = thread?.messages ?? [];

  return (
    <main className="chat-window">
      <header className="chat-header">
        <h2>{thread?.title ?? "New chat"}</h2>
        {thread && (
          <span className="chat-session-id" title="Session id">
            {thread.sessionId.slice(0, 8)}
          </span>
        )}
      </header>

      <div className="messages" ref={scrollRef}>
        {messages.length === 0 && (
          <div className="empty-state">
            <div className="empty-mark">◆</div>
            <h3>Start the conversation</h3>
            <p>
              Ask anything. The agent keeps a memory of what you discuss —
              across this and previous sessions.
            </p>
          </div>
        )}

        {messages.map((m) => (
          <div
            key={m.id}
            className={`bubble-row ${m.role} ${m.error ? "error" : ""}`}
          >
            <div className="bubble">
              <div className="bubble-role">
                {m.role === "user" ? "You" : "Agent"}
              </div>
              <div className="bubble-content">{m.content}</div>
            </div>
          </div>
        ))}

        {sending && (
          <div className="bubble-row assistant">
            <div className="bubble">
              <div className="bubble-role">Agent</div>
              <div className="typing">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        )}
      </div>

      <form className="composer" onSubmit={submit}>
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) submit(e);
          }}
          placeholder="Message the agent…  (Enter to send, Shift+Enter for newline)"
          rows={1}
        />
        <button type="submit" disabled={!draft.trim() || sending}>
          Send
        </button>
      </form>
    </main>
  );
}
