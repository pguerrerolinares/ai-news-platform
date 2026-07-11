# Informe — guest-token-race

## Estado
Completado. Rama `fabrica/guest-token-race` en el worktree, commit `98c2126`. Sin push/merge (según lo pactado).

## Cambios
- `frontend/src/lib/api.ts`: `ensureToken()` y `refreshAccessToken()` memoizan una promise in-flight compartida (`inflightGuestToken`, `inflightRefresh`) a nivel de módulo — patrón single-flight: si hay una en curso se reutiliza, si no se crea y se limpia en `finally`.
- `frontend/src/lib/auth.ts`: nuevo helper `storeGuestToken(accessToken, expiresIn)` que usa `STORAGE_KEYS`. `ensureToken()` ya no escribe `'auth_access_token'`/`'auth_expires_at'` a pelo.
- Se eliminó `window.location.replace('/login')` en `request()` y `apiStream()` (líneas ~85/~167 originales). Con el login descontinuado, un 401 no recuperable ahora simplemente lanza `ApiError('Session expired')` tras `clearTokens()` — sin redirect roto por el base path `/ai-news`.
- Efecto colateral intencional (pedido explícito del brief): `ensureToken()` ya no traga en silencio el fallo del fetch de guest token; si `/api/auth/guest` falla, el error se propaga al caller (la request falla con su `ApiError` normal). No hay retry loop ni backoff — el "reintento" es implícito: al limpiar `inflightGuestToken` en el `finally`, la siguiente interacción del usuario vuelve a pedir token.

## Oráculos
- `npm --prefix frontend run build` → verde (tsc -b + vite build, sin warnings nuevos, solo el aviso de chunk size preexistente).
- `npm --prefix frontend run lint` → 10 errores, todos preexistentes (`button.tsx`, `sidebar.tsx`, `tabs.tsx`, `toggle.tsx`, `use-auth.tsx`, `use-theme.tsx`, `Dashboard.tsx`, `Trending.tsx`), verificado con `git stash` sobre el mismo worktree antes de mis cambios → mismos 10 errores. Ninguno toca `api.ts`/`auth.ts`.

## Evidencia single-flight
No hay infra de tests frontend (sin vitest/jest, `node_modules` no estaba instalado — se corrió `bun install`). Se verificó con un script harness (`bun run`) que mockea `localStorage` y `fetch` globales, importa el `api.ts` real del worktree y dispara 3 `apiGet()` concurrentes sin token:

```
guest token fetches triggered: 1
concurrent apiGet calls resolved: 3
PASS: single-flight dedup works
```

Antes del fix, cada una de las 3 llamadas hubiera disparado su propio POST a `/api/auth/guest` (N fetches). Con el fix, 1 solo fetch sirve a las 3.

## Decisión sobre el redirect /login
Eliminado sin reemplazo, tal como pide el brief (login descontinuado). El único comportamiento nuevo es que un fallo real de guest-token-fetch ya no queda enmascarado — antes se tragaba y la request seguía sin token (fallando más adelante con un 401 confuso); ahora falla de inmediato con un error claro y trazable.
