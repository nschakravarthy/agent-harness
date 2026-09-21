import type { RefreshTokenResponse, Session } from "../types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

// Auth hooks registered by AuthContext so this low-level module can read the
// current session, persist refreshed tokens, and force logout on hard failure
// without importing React.
interface AuthHandlers {
  getSession: () => Session | null;
  onTokensRefreshed: (accessToken: string, refreshToken: string) => void;
  onAuthFailure: () => void;
}
let authHandlers: AuthHandlers | null = null;
export function registerAuthHandlers(handlers: AuthHandlers | null): void {
  authHandlers = handlers;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  // Extra headers (e.g. x-session-id for /chat).
  headers?: Record<string, string>;
  // Access token to send as `Authorization: Token <token>`.
  // The backend's AuthMiddleware expects the "Token " prefix (not "Bearer").
  token?: string | null;
  // Internal: set on the retry after a token refresh so we don't loop.
  _retried?: boolean;
}

// Single in-flight refresh shared across concurrent 401s, so a burst of
// requests triggers exactly one /user/refresh call.
let refreshInFlight: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  if (!authHandlers) return null;
  const session = authHandlers.getSession();
  if (!session?.refreshToken) return null;

  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const res = await request<RefreshTokenResponse>("/user/refresh", {
          method: "POST",
          body: { refresh_token: session.refreshToken },
          // Don't attach a token or attempt a nested refresh.
          _retried: true,
        });
        authHandlers?.onTokensRefreshed(res.access_token, res.refresh_token);
        return res.access_token;
      } catch {
        return null;
      } finally {
        refreshInFlight = null;
      }
    })();
  }
  return refreshInFlight;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, headers = {}, token, _retried } = opts;

  const finalHeaders: Record<string, string> = {
    Accept: "application/json",
    ...headers,
  };
  if (body !== undefined) {
    finalHeaders["Content-Type"] = "application/json";
  }
  if (token) {
    finalHeaders["Authorization"] = `Token ${token}`;
  }

  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      method,
      headers: finalHeaders,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (err) {
    throw new ApiError(0, `Network error: ${(err as Error).message}`);
  }

  // Access token likely expired — refresh once and retry the request. Only
  // for authenticated calls (had a token) that haven't already been retried.
  if (res.status === 401 && token && !_retried) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      return request<T>(path, { ...opts, token: newToken, _retried: true });
    }
    // Refresh failed (refresh token missing/expired) — force re-login.
    authHandlers?.onAuthFailure();
  }

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      if (data?.detail) {
        detail =
          typeof data.detail === "string"
            ? data.detail
            : JSON.stringify(data.detail);
      }
    } catch {
      // response had no JSON body; keep the default message
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string, session?: Session | null) =>
    request<T>(path, { token: session?.accessToken }),

  post: <T>(
    path: string,
    body: unknown,
    session?: Session | null,
    headers?: Record<string, string>,
  ) =>
    request<T>(path, {
      method: "POST",
      body,
      token: session?.accessToken,
      headers,
    }),
};

export { BASE_URL };
