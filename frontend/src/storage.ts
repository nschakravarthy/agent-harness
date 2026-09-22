import type { ChatThread, Session } from "./types";

// Small localStorage helpers. The auth session and chat threads are cached
// locally so the app is usable across reloads and so "previous chats" works
// before the backend exposes a history endpoint. Threads are namespaced per
// user so switching accounts doesn't leak conversations.

const SESSION_KEY = "otto.session";
const threadsKey = (userId: string) => `otto.threads.${userId}`;

// The app was renamed from "Memory Agent" to "Otto". Browsers that already
// visited the old build still hold data under the old prefix, so read it once
// and carry it over rather than silently logging everyone out. Drop this
// block (and the legacy helpers) once the old keys have aged out.
const LEGACY_SESSION_KEY = "memory-agent.session";
const legacyThreadsKey = (userId: string) => `memory-agent.threads.${userId}`;

function migrate(from: string, to: string): void {
  try {
    if (localStorage.getItem(to) !== null) return;
    const raw = localStorage.getItem(from);
    if (raw === null) return;
    localStorage.setItem(to, raw);
    localStorage.removeItem(from);
  } catch {
    // Private mode or a full quota: not worth failing a read over.
  }
}

migrate(LEGACY_SESSION_KEY, SESSION_KEY);

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
  // Threads are per-user, so the userId only becomes known here — which makes
  // this the first point at which that user's old key can be carried over.
  migrate(legacyThreadsKey(userId), threadsKey(userId));
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
