import type { ChatThread } from "../types";

interface Props {
  threads: ChatThread[];
  activeId: string;
  email: string;
  onNewChat: () => void;
  onSelect: (sessionId: string) => void;
  onDelete: (sessionId: string) => void;
  onLogout: () => void;
}

export default function Sidebar({
  threads,
  activeId,
  email,
  onNewChat,
  onSelect,
  onDelete,
  onLogout,
}: Props) {
  return (
    <aside className="sidebar">
      <div className="sidebar-top">
        <button className="new-chat-btn" onClick={onNewChat} type="button">
          <span className="plus">+</span> New chat
        </button>
      </div>

      <div className="thread-list">
        <div className="thread-list-label">Previous chats</div>
        {threads.length === 0 && (
          <div className="thread-empty">No conversations yet.</div>
        )}
        {threads.map((t) => (
          <div
            key={t.sessionId}
            className={`thread-item ${t.sessionId === activeId ? "active" : ""}`}
            onClick={() => onSelect(t.sessionId)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") onSelect(t.sessionId);
            }}
          >
            <div className="thread-item-body">
              <div className="thread-title">{t.title}</div>
              <div className="thread-meta">
                {new Date(t.updatedAt).toLocaleDateString(undefined, {
                  month: "short",
                  day: "numeric",
                })}{" "}
                · {t.messages.length} msg
              </div>
            </div>
            <button
              className="thread-delete"
              title="Delete chat"
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onDelete(t.sessionId);
              }}
            >
              ×
            </button>
          </div>
        ))}
      </div>

      <div className="sidebar-footer">
        <div className="user-badge" title={email}>
          <span className="user-avatar">{email.charAt(0).toUpperCase()}</span>
          <span className="user-email">{email}</span>
        </div>
        <button className="logout-btn" onClick={onLogout} type="button">
          Log out
        </button>
      </div>
    </aside>
  );
}
