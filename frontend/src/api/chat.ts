import { api, ApiError } from "./client";
import type {
  ChatResponse,
  MessageResponse,
  Session,
  SessionResponse,
} from "../types";

/**
 * Persist a user's chat message on the backend.
 *
 *   POST /api/v1/conversation/message
 *   headers: Authorization: Token <access>
 *   body:    { session_id, content }
 *   returns: { message_id, session_id, content, role, created_at }
 *
 * Called every time the user sends a message so the Message table records it.
 */
export async function postMessage(
  sessionId: string,
  content: string,
  session: Session,
): Promise<MessageResponse> {
  return api.post<MessageResponse>(
    "/conversation/message",
    { session_id: sessionId, content },
    session,
  );
}

/**
 * Create a new conversation session on the backend.
 *
 *   POST /api/v1/conversation/session
 *   headers: Authorization: Token <access>
 *   body:    (none — the user is taken from the auth token)
 *   returns: { session_id }
 *
 * The returned id is used as the thread key and later sent as the
 * `x-session-id` header when messages are posted to /chat.
 */
export async function createSession(session: Session): Promise<string> {
  const res = await api.post<SessionResponse>(
    "/conversation/session",
    undefined,
    session,
  );
  return res.session_id;
}

/**
 * Send a message to the agent.
 *
 * Backend contract today (api/user/routes.py):
 *   POST /api/v1/user/chat
 *   headers: Authorization: Token <access>, x-session-id: <sessionId>
 *   body:    { message }
 *   returns: { session_id }   <-- stub; no reply text yet
 *
 * Once the backend wires the LangGraph workflow into this endpoint it should
 * return the assistant's reply. We read `reply` / `message` if present and
 * otherwise show a placeholder so the UI is usable against the current stub.
 */
export async function sendMessage(
  sessionId: string,
  message: string,
  session: Session,
): Promise<string> {
  const res = await api.post<ChatResponse>(
    "/user/chat",
    { message },
    session,
    { "x-session-id": sessionId },
  );

  const reply = res.reply ?? res.message;
  if (reply) return reply;

  return "_(The backend accepted the message but doesn't return a reply yet. Wire the agent workflow into POST /user/chat to see real responses.)_";
}

/**
 * Fetch previous chat threads for the user.
 *
 * There is no history endpoint yet. We attempt a conventional route and fall
 * back to `null` so the caller can use locally-cached threads instead. When
 * the backend adds e.g. `GET /user/chats`, this will start returning data
 * with no other changes.
 */
export async function fetchThreads(
  session: Session,
): Promise<unknown[] | null> {
  try {
    return await api.get<unknown[]>("/user/chats", session);
  } catch (err) {
    if (err instanceof ApiError && (err.status === 404 || err.status === 0)) {
      return null; // endpoint not implemented — use local cache
    }
    throw err;
  }
}
