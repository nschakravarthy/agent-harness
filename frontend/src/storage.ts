import type { ChatThread, Session } from "./types";

// Small localStorage helpers. The auth session and chat threads are cached
// locally so the app is usable across reloads and so "previous chats" works
// before the backend exposes a history endpoint. Threads are namespaced per
// user so switching accounts doesn't leak conversations.

const SESSION_KEY = "memory-agent.session";
const threadsKey = (userId: string) => `memory-agent.threads.${userId}`;

export function loadSession(): Session | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

export function saveSession(session: Session): void {
  localStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

export function clearSession(): void {
  localStorage.removeItem(SESSION_KEY);
}

export function loadThreads(userId: string): ChatThread[] {
  try {
    const raw = localStorage.getItem(threadsKey(userId));
    return raw ? (JSON.parse(raw) as ChatThread[]) : [];
  } catch {
    return [];
  }
}

export function saveThreads(userId: string, threads: ChatThread[]): void {
  localStorage.setItem(threadsKey(userId), JSON.stringify(threads));
}
