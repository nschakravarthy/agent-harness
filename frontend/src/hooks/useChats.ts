import { useCallback, useEffect, useRef, useState } from "react";
import type { ChatThread, Message, Session } from "../types";
import { loadThreads, saveThreads } from "../storage";
import { createSession, postMessage, sendMessage } from "../api/chat";
import { ApiError } from "../api/client";

// Generate an id without pulling in a dependency.
function uid(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.floor(Math.random() * 1e9)}`;
}

function newThread(sessionId?: string, persisted = false): ChatThread {
  const now = new Date().toISOString();
  return {
    sessionId: sessionId ?? uid(),
    title: "New chat",
    createdAt: now,
    updatedAt: now,
    messages: [],
    persisted,
  };
}

function deriveTitle(text: string): string {
  const trimmed = text.trim().replace(/\s+/g, " ");
  return trimmed.length > 40 ? `${trimmed.slice(0, 40)}…` : trimmed || "New chat";
}

export function useChats(session: Session) {
  // True only when we had to seed a fresh thread (no stored history). The
  // login-issued session_id isn't backed by a Session row, so on mount we
  // swap in a real backend session for it (see effect below).
  const seededRef = useRef(false);
  const [threads, setThreads] = useState<ChatThread[]>(() => {
    const existing = loadThreads(session.userId);
    if (existing.length > 0) return existing;
    // Seed with the session_id issued at login so the UI has a thread
    // immediately; the effect below replaces it with a backend-backed id.
    seededRef.current = true;
    return [newThread(session.defaultSessionId)];
  });
  const [activeId, setActiveId] = useState<string>(
    () => threads[0]?.sessionId ?? "",
  );
  const [sending, setSending] = useState(false);

  // Back the freshly-seeded thread with a real Session row so the first chat
  // (like every "New chat") is keyed on a backend-created session id.
  useEffect(() => {
    if (!seededRef.current) return;
    seededRef.current = false;
    (async () => {
      let sessionId: string;
      try {
        sessionId = await createSession(session);
      } catch {
        return; // keep the login-seeded id if the request fails
      }
      setThreads((prev) => {
        // Only swap while the seeded thread is still the lone, untouched one.
        if (prev.length !== 1 || prev[0].messages.length > 0) return prev;
        const oldId = prev[0].sessionId;
        setActiveId((cur) => (cur === oldId ? sessionId : cur));
        return [{ ...prev[0], sessionId, persisted: true }];
      });
    })();
    // Run once on mount for this user's session.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Persist on every change, namespaced per user.
  const userId = session.userId;
  useEffect(() => {
    saveThreads(userId, threads);
  }, [userId, threads]);

  const activeThread =
    threads.find((t) => t.sessionId === activeId) ?? threads[0];

  const patchThread = useCallback(
    (sessionId: string, fn: (t: ChatThread) => ChatThread) => {
      setThreads((prev) =>
        prev.map((t) => (t.sessionId === sessionId ? fn(t) : t)),
      );
    },
    [],
  );

  // Guard against overlapping session-creation requests (e.g. double-clicks).
  const creating = useRef(false);

  const startNewChat = useCallback(async () => {
    if (creating.current) return;
    // Reuse an existing empty thread rather than piling up blanks.
    const empty = threads.find((t) => t.messages.length === 0);
    if (empty) {
      setActiveId(empty.sessionId);
      return;
    }
    creating.current = true;
    try {
      // Ask the backend to create a Session row and use its id as the thread
      // key (later sent as x-session-id on /chat). Fall back to a local id so
      // the UI still works if the endpoint is unavailable.
      let sessionId: string | undefined;
      try {
        sessionId = await createSession(session);
      } catch {
        sessionId = undefined;
      }
      // Mark persisted only when the backend actually created the Session row.
      const t = newThread(sessionId, sessionId !== undefined);
      setActiveId(t.sessionId);
      setThreads((prev) => [t, ...prev]);
    } finally {
      creating.current = false;
    }
  }, [threads, session]);

  const selectChat = useCallback((sessionId: string) => {
    setActiveId(sessionId);
  }, []);

  const deleteChat = useCallback(
    (sessionId: string) => {
      setThreads((prev) => {
        const remaining = prev.filter((t) => t.sessionId !== sessionId);
        const next = remaining.length > 0 ? remaining : [newThread()];
        if (sessionId === activeId) setActiveId(next[0].sessionId);
        return next;
      });
    },
    [activeId],
  );

  // Guard against overlapping sends stepping on each other's thread.
  const inFlight = useRef(false);

  const send = useCallback(
    async (text: string) => {
      const content = text.trim();
      if (!content || inFlight.current || !activeThread) return;
      inFlight.current = true;
      setSending(true);

      const oldId = activeThread.sessionId;

      // Ensure the thread is backed by a real backend Session row before we
      // persist the message — the /message route has a FK on session_id, and
      // login-seeded / locally-generated ids have no Session row. If needed,
      // create the session now and store the returned id on the thread. If the
      // session can't be created, block the send rather than post to a
      // nonexistent session (which would fail the FK anyway).
      let threadId = oldId;
      if (!activeThread.persisted) {
        try {
          threadId = await createSession(session);
          patchThread(oldId, (t) => ({
            ...t,
            sessionId: threadId,
            persisted: true,
          }));
          setActiveId((cur) => (cur === oldId ? threadId : cur));
        } catch {
          const errMsg: Message = {
            id: uid(),
            role: "assistant",
            content:
              "⚠️ Couldn't start a session — your message wasn't sent. Please try again.",
            createdAt: new Date().toISOString(),
            error: true,
          };
          patchThread(oldId, (t) => ({
            ...t,
            messages: [...t.messages, errMsg],
            updatedAt: errMsg.createdAt,
          }));
          inFlight.current = false;
          setSending(false);
          return;
        }
      }

      const userMsg: Message = {
        id: uid(),
        role: "user",
        content,
        createdAt: new Date().toISOString(),
      };

      patchThread(threadId, (t) => ({
        ...t,
        title: t.messages.length === 0 ? deriveTitle(content) : t.title,
        messages: [...t.messages, userMsg],
        updatedAt: userMsg.createdAt,
      }));

      try {
        // Persist the user's message to the Message table before asking the
        // agent for a reply. A persistence failure shouldn't block the chat,
        // so it's surfaced via the catch below only if it throws.
        await postMessage(threadId, content, session);
        const reply = await sendMessage(threadId, content, session);
        const botMsg: Message = {
          id: uid(),
          role: "assistant",
          content: reply,
          createdAt: new Date().toISOString(),
        };
        patchThread(threadId, (t) => ({
          ...t,
          messages: [...t.messages, botMsg],
          updatedAt: botMsg.createdAt,
        }));
      } catch (err) {
        const detail =
          err instanceof ApiError && err.status === 0
            ? "Couldn't reach the server."
            : err instanceof Error
              ? err.message
              : "Failed to send message.";
        const errMsg: Message = {
          id: uid(),
          role: "assistant",
          content: `⚠️ ${detail}`,
          createdAt: new Date().toISOString(),
          error: true,
        };
        patchThread(threadId, (t) => ({
          ...t,
          messages: [...t.messages, errMsg],
          updatedAt: errMsg.createdAt,
        }));
      } finally {
        inFlight.current = false;
        setSending(false);
      }
    },
    [activeThread, patchThread, session],
  );

  // Most-recently-updated first for the sidebar.
  const orderedThreads = [...threads].sort((a, b) =>
    b.updatedAt.localeCompare(a.updatedAt),
  );

  return {
    threads: orderedThreads,
    activeThread,
    activeId,
    sending,
    startNewChat,
    selectChat,
    deleteChat,
    send,
  };
}
