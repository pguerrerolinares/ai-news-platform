# Wire React Frontend to Real API — Design Doc

**Date**: 2026-02-24
**Status**: Approved
**Goal**: Replace mock data in all 4 React pages with real API calls. Add login page with JWT auth. Connect chat to real SSE streaming.

---

## Scope

- **Login page** with JWT auth (access + refresh tokens)
- **Auth context** (AuthProvider, useAuth hook, protected routes)
- **API client** (fetch wrapper with JWT headers, auto-refresh on 401)
- **Wire 4 pages** (Dashboard, Trending, Buscar, Chat) to real API endpoints
- **SSE streaming** for Chat (OpenAI-style events from POST /api/chat)

**Not in scope**: Analytics page, pagination, Archive page, new backend endpoints.

---

## Architecture

### New Files

| File | Purpose |
|------|---------|
| `frontend/src/lib/api.ts` | Fetch wrapper with JWT, base URL, error handling, auto-refresh |
| `frontend/src/lib/auth.ts` | Token storage (localStorage), login/logout/refresh functions |
| `frontend/src/hooks/use-auth.tsx` | AuthProvider context, useAuth hook, RequireAuth route guard |
| `frontend/src/pages/Login.tsx` | Login form (password field, submit, error state) |

### Modified Files

| File | Changes |
|------|---------|
| `frontend/src/lib/types.ts` | Add PaginatedResponse, AuthTokens, ChatEvent types |
| `frontend/src/App.tsx` | Add /login route, wrap routes in AuthProvider + RequireAuth |
| `frontend/src/pages/Dashboard.tsx` | Replace MOCK_ITEMS with `GET /api/items/today` |
| `frontend/src/pages/Trending.tsx` | Replace mock with `GET /api/items/trending` + `GET /api/items/top` |
| `frontend/src/pages/Buscar.tsx` | Replace mock filter with `GET /api/search?q=...&topic=...&sort_by=...` |
| `frontend/src/pages/Chat.tsx` | Replace mock setTimeout with real SSE via `POST /api/chat` |

---

## Auth Flow

1. User visits any page -> if no valid token, redirect to `/login`
2. Login: `POST /api/auth/token` with `{ password }` -> receive `{ access_token, refresh_token, expires_in, token_type }`
3. Tokens stored in localStorage: `access_token`, `refresh_token`, `expires_at` (computed from expires_in)
4. Every API call includes `Authorization: Bearer <access_token>` header
5. On 401 response: attempt `POST /api/auth/refresh` with `{ refresh_token }` -> if success, retry original request; if fail, redirect to login
6. Logout: clear localStorage tokens, redirect to `/login`

### Token Storage

```typescript
interface AuthTokens {
  access_token: string
  refresh_token: string
  expires_at: number  // Date.now() + expires_in * 1000
}
```

localStorage keys: `auth_access_token`, `auth_refresh_token`, `auth_expires_at`.

---

## API Client (`lib/api.ts`)

Thin fetch wrapper. No external dependencies.

### Functions

- `apiGet<T>(path: string, params?: Record<string, string>): Promise<{ data: T; totalCount: number | null }>`
  - Appends query params, adds JWT header, parses JSON
  - Reads `X-Total-Count` header when present
  - On 401: tries refresh, retries once

- `apiPost<T>(path: string, body: unknown): Promise<T>`
  - POST with JWT header, JSON body

- `apiStream(path: string, body: unknown): Promise<Response>`
  - POST that returns raw Response for SSE streaming (Chat)
  - JWT header included, no JSON parsing

### Base URL

`import.meta.env.VITE_API_URL ?? 'http://localhost:8000'`

Set in `.env.local` for development, in build env for production.

---

## Page Wiring

### Dashboard (`GET /api/items/today`)

- On mount: fetch `/api/items/today?limit=50`
- Loading state: skeleton or spinner
- Error state: error message with retry button
- Topic filter: client-side filter on fetched data (same as current mock behavior)
- Featured card: first item with highest score (same logic, real data)

### Trending

- On mount: fetch `/api/items/trending?limit=20` and `/api/items/top?limit=20` in parallel
- Two sections: "Trending" and "Top Scored" (same layout as current)

### Buscar (`GET /api/search`)

- On search submit: fetch `/api/search?q=<query>&topic=<topic>&sort_by=<sort>&limit=30`
- Display `X-Total-Count` as result count
- Loading state during search
- Empty state when no results

### Chat (`POST /api/chat` with SSE)

- On send: `POST /api/chat` with `{ message: "user text" }`
- Response is SSE stream. Parse with `ReadableStream` + `TextDecoder`:
  - `event: message` + `data: {"type":"token","content":"..."}` -> append to assistant message
  - `event: message` + `data: {"type":"sources","content":[...]}` -> store sources (optional display)
  - `event: error` + `data: {"error":{"code":"...","message":"..."}}` -> show error
  - `event: done` -> mark streaming complete
- Suggestion chips still present, but trigger real API calls instead of mock

---

## Environment

Add to `frontend/.env.local` (not committed):
```
VITE_API_URL=http://localhost:8000
```

Add to `frontend/.env.example` (committed):
```
VITE_API_URL=http://localhost:8000
```

---

## Error Handling

- Network errors: show "No se pudo conectar con el servidor" with retry
- 401 after refresh fails: redirect to login
- 429 (rate limit): show "Demasiadas peticiones, intenta de nuevo en unos segundos"
- Other 4xx/5xx: show error message from API response `error.message`
- All error text in Spanish (user-facing)

---

## What stays unchanged

- All Motion animations
- All Shadcn UI components
- NewsCard, FeaturedCard component props and rendering
- Theme toggle, nav, layout
- `constants.ts` (SOURCE_COLORS, TOPIC_LABELS match real data)
- `use-reduced-motion`, `use-mobile`, `use-theme` hooks
