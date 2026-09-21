import { api } from "./client";
import type { AuthResponse, Credentials, Session } from "../types";

function toSession(res: AuthResponse, email: string): Session {
  return {
    userId: res.user_id,
    email,
    accessToken: res.access_token,
    refreshToken: res.refresh_token,
    defaultSessionId: res.session_id,
  };
}

export async function register(creds: Credentials): Promise<Session> {
  const res = await api.post<AuthResponse>("/user/register", creds);
  return toSession(res, creds.email);
}

export async function login(creds: Credentials): Promise<Session> {
  const res = await api.post<AuthResponse>("/user/login", creds);
  return toSession(res, creds.email);
}
