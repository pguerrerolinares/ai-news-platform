# M15: API Contract Polish — Design Doc

**Goal:** Improve SSE chat contract, integrate refresh tokens in frontend, update Angular
services for M14 features, and clean up schemas/OpenAPI docs.

**Context:** M14 added pagination (X-Total-Count), refresh tokens, stats endpoints, and
standardized errors on the backend. The frontend doesn't use any of these yet. The chat
SSE contract lacks event types and message IDs. This milestone bridges the gap before
the visual redesign (M16).

---

## 1. Chat SSE — OpenAI-style Events

**Problem:** Chat SSE uses only `data:` lines. The frontend parses JSON to distinguish
token/error/sources/done. No message ID for correlation or debugging.

**New contract:**

```
event: message
data: {"id":"msg_<hex12>","type":"token","content":"Las"}

event: message
data: {"id":"msg_<hex12>","type":"token","content":" herramientas"}

event: message
data: {"id":"msg_<hex12>","type":"sources","content":[{id, title, url, topic}]}

event: error
data: {"id":"msg_<hex12>","error":{"code":"LLM_TIMEOUT","message":"..."}}

event: done
data: {"id":"msg_<hex12>"}
```

**Implementation:**
- Generate `id` with `uuid4().hex[:12]` at stream start, prefix `msg_`
- Each `yield` prepends `event: <type>\n` before `data:`
- Error events use `event: error` instead of `event: message`
- `[DONE]` replaced by `event: done` with JSON payload
- Update `chat.ts` parser to use event types

**Files:** `src/rag/chat.py`, `web/src/app/pages/chat.ts`

---

## 2. Frontend Auth — Refresh Tokens

**Problem:** Frontend `auth.service.ts` expects `{access_token}` only. Does not use
`TokenResponseV2` (refresh_token, expires_in) from M14. No auto-refresh on 401.

**Changes:**

### auth.service.ts
- Login stores `access_token`, `refresh_token`, `expires_in` in localStorage
- New `refreshToken()` method: `POST /api/auth/refresh {refresh_token}`
- `isAuthenticated()` uses stored expiry for quick check
- `logout()` clears all three keys

### auth.interceptor.ts
- On 401 response: attempt `refreshToken()`
- If refresh succeeds: retry original request with new access token
- If refresh fails: redirect to login, clear tokens
- Skip refresh attempt for auth endpoints (`/api/auth/*`)

**Files:** `web/src/app/services/auth.service.ts`, `web/src/app/interceptors/auth.interceptor.ts`

---

## 3. Frontend Service Updates (M14 Features)

**Problem:** `news.service.ts` doesn't use M14's pagination (offset, sort_by,
X-Total-Count) or stats endpoints.

**Changes:**

### news.service.ts
- `searchItems`: add `offset`, `sort_by` params
- `getTodayItems`: add `offset` param
- `getBriefings`: add `offset` param
- All list methods return `{ items: T[], totalCount: number }` by reading
  `X-Total-Count` from response headers
- New methods: `getStatsSummary()`, `getStatsBySource()`, `getStatsByTopic()`,
  `getStatsByDate(days?)`

### models/news-item.ts
- Add `PaginatedResponse<T>` interface: `{ items: T[], totalCount: number }`

**Files:** `web/src/app/services/news.service.ts`, `web/src/app/models/news-item.ts`

---

## 4. Schema Cleanup + OpenAPI Docs

**Problem:** Dead schemas, inconsistent response models, missing OpenAPI error docs.

**Changes:**
- Delete `TokenResponse` (replaced by `TokenResponseV2`)
- Move `ChatRequest` from `routes/chat.py` to `schemas.py` (consistency)
- Add `CountResponse` schema for `/api/items/count`
- Add `responses={401: {"model": ErrorWrapper}}` to all JWT-protected endpoints
- Add `responses={404: {"model": ErrorWrapper}}` to briefings `/{date}` endpoint

**Files:** `src/api/schemas.py`, `src/api/routes/chat.py`, all route files

---

## 5. Chat fetch → AuthService

**Problem:** `chat.ts` uses raw `fetch()` reading token directly from localStorage.
This bypasses the Angular interceptor and won't benefit from auto-refresh.

**Change:** Replace direct `localStorage.getItem` with `AuthService.getToken()`.
Keep `fetch()` for SSE (Angular HttpClient doesn't support streaming), but get
the token through the service.

**Files:** `web/src/app/pages/chat.ts`

---

## Scope Summary

| Section | Tasks (est.) | Risk |
|---------|-------------|------|
| 1. Chat SSE events | 3 | Track A (low) |
| 2. Frontend auth refresh | 4 | Track B (medium) |
| 3. Frontend service updates | 3 | Track A (low) |
| 4. Schema cleanup + OpenAPI | 2 | Track A (low) |
| 5. Chat fetch → AuthService | 1 | Track A (low) |
| **Total** | **~13 tasks** | |

## Out of Scope (M16)

- Briefings redesign (query news_items by date, remove daily_briefings dependency)
- New endpoints for analytics/charts
- Pagination UI controls
- Visual redesign

---

*Design approved: 21 de febrero de 2026*
