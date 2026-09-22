# Otto — Frontend

A small React + Vite + TypeScript app for chatting with the Otto backend. It
gates on auth (login / register), then opens a chat UI with a sidebar to start
a new chat and browse previous chats.

## Stack

- **React 18** + **TypeScript**
- **Vite** dev server / bundler
- Plain CSS (no UI framework) — dark + light themes via `prefers-color-scheme`
- No router or state library; the app has two screens and uses React context

## Run it

```bash
cd frontend
cp .env.example .env        # optional — defaults work with the dev proxy
npm install
npm run dev                 # http://localhost:5173
```

The dev server proxies `/api/*` to the backend at `http://localhost:8000`
(see `vite.config.ts`), so start the backend first:

```bash
# from the repo root
docker compose up --build
```

## How it maps to the backend

| UI action        | Backend call                                              |
| ---------------- | --------------------------------------------------------- |
| Register         | `POST /api/v1/user/register` `{ email, password }`        |
| Log in           | `POST /api/v1/user/login` `{ email, password }`           |
| Send a message   | `POST /api/v1/user/chat` `{ message }` + `x-session-id`   |

Auth uses the header format the backend's `AuthMiddleware` expects:
`Authorization: Token <access_token>` (not `Bearer`).

### Endpoints that don't exist yet

This is a **scaffold** — a couple of things are stubbed on the backend, and the
frontend is written to light up automatically once they're implemented:

- **Assistant replies.** `POST /user/chat` currently returns only
  `{ session_id }`. The client already reads a `reply` / `message` field if the
  response includes one (`src/api/chat.ts`); until then it shows a placeholder
  bubble. The agent workflow that used to back this route has been removed, so
  implement a replacement behind `POST /user/chat` to get real answers.
- **Chat history / thread list.** There is no "list my conversations" endpoint.
  Threads are cached in `localStorage` (namespaced per user) so "previous chats"
  works today. `fetchThreads()` in `src/api/chat.ts` already probes
  `GET /user/chats` and falls back to the local cache on 404 — implement that
  route and swap the cache read for it.

## Project layout

```
frontend/
├── index.html
├── vite.config.ts          # dev server + /api proxy to :8000
├── src/
│   ├── main.tsx            # entry; wraps App in AuthProvider
│   ├── App.tsx             # auth gate: AuthPage vs ChatPage
│   ├── types.ts            # shapes mirrored from api/user/schemas.py
│   ├── storage.ts          # localStorage helpers (session + threads)
│   ├── api/
│   │   ├── client.ts       # fetch wrapper (Token auth, error handling)
│   │   ├── auth.ts         # register / login
│   │   └── chat.ts         # sendMessage / fetchThreads (with fallback)
│   ├── context/
│   │   └── AuthContext.tsx # session state + login/register/logout
│   ├── hooks/
│   │   └── useChats.ts     # thread list, new chat, send, persistence
│   ├── pages/
│   │   ├── AuthPage.tsx    # login / register form
│   │   └── ChatPage.tsx    # sidebar + chat window
│   └── components/
│       ├── Sidebar.tsx     # new chat + previous chats + logout
│       └── ChatWindow.tsx  # message list + composer
└── src/index.css           # all styles
```
