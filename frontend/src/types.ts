// Shapes mirrored from the backend (api/user/schemas.py).

export interface AuthResponse {
  user_id: string;
  access_token: string;
  refresh_token: string;
  session_id: string;
  token_type: string;
  expires_in: number; // seconds
}

export interface Credentials {
  email: string;
  password: string;
}

// Response from POST /api/v1/user/refresh — new tokens from a refresh token.
export interface RefreshTokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

// What we keep in localStorage to survive reloads.
export interface Session {
  userId: string;
  email: string;
  accessToken: string;
  refreshToken: string;
  // The session_id returned at login — used as the default chat session.
  defaultSessionId: string;
}

// A single chat message in the UI.
export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  // ISO timestamp, set client-side.
  createdAt: string;
  // Optimistic messages that haven't been confirmed by the server.
  pending?: boolean;
  error?: boolean;
}

// A conversation thread. `sessionId` is what the backend keys on
// (sent as the `x-session-id` header on /chat).
export interface ChatThread {
  sessionId: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messages: Message[];
  // True once `sessionId` is backed by a backend-created Session row (as
  // opposed to a login-seeded or locally-generated id). The /message and
  // /chat routes key on a real session id, so we only post once this is set.
  persisted?: boolean;
}

// Response from POST /api/v1/conversation/session — creates a Session row
// and returns its id (api/conversation/schemas.py).
export interface SessionResponse {
  session_id: string;
}

// Response from POST /api/v1/conversation/message — persists a user's
// message and returns the stored row (api/conversation/schemas.py).
export interface MessageResponse {
  message_id: string;
  session_id: string;
  content: string;
  role: string;
  created_at: string;
}

// Response from POST /api/v1/user/chat (currently a stub: { session_id }).
export interface ChatResponse {
  session_id: string;
  // Anticipated fields once the backend actually generates a reply.
  reply?: string;
  message?: string;
}
