import { useAuth } from "../context/AuthContext";
import { useChats } from "../hooks/useChats";
import Sidebar from "../components/Sidebar";
import ChatWindow from "../components/ChatWindow";
import type { Session } from "../types";

export default function ChatPage({ session }: { session: Session }) {
  const { logout } = useAuth();
  const {
    threads,
    activeThread,
    activeId,
    sending,
    startNewChat,
    selectChat,
    deleteChat,
    send,
  } = useChats(session);

  return (
    <div className="chat-layout">
      <Sidebar
        threads={threads}
        activeId={activeId}
        email={session.email}
        onNewChat={startNewChat}
        onSelect={selectChat}
        onDelete={deleteChat}
        onLogout={logout}
      />
      <ChatWindow thread={activeThread} sending={sending} onSend={send} />
    </div>
  );
}
