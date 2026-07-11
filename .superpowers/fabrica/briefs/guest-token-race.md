# Brief — guest-token-race

## Dónde encaja
Campaña post-auditoría. La web es pública: el frontend usa guest tokens (`POST /api/auth/guest`). Hallazgos en `frontend/src/lib/api.ts`:
1. `ensureToken()` (línea ~36) y `refreshAccessToken()` (línea ~17) no deduplican llamadas concurrentes: N requests sin token → N POST a `/api/auth/guest` a la vez.
2. `ensureToken()` escribe `localStorage` con claves crudas `'auth_access_token'`/`'auth_expires_at'` (línea ~43) en vez de reusar `STORAGE_KEYS`/helpers de `frontend/src/lib/auth.ts` — DRY violation que se desincroniza en silencio.
3. (relacionado, arréglalo de paso) `window.location.replace('/login')` en líneas ~85 y ~167 ignora el base path `/ai-news` → en prod manda a un 404. Con el login descontinuado, elimina el redirect a /login: si el fetch de guest token falla, propaga el error al caller (la request falla y la página muestra su estado de error normal) — SIN retry loop ni backoff; el "reintento" es implícito: al limpiar la promise in-flight en el finally, la siguiente interacción del usuario vuelve a pedir token.

## Worktree y rama
- `/home/paul/Documentos/proyectos/backend/ai-news-platform/.worktrees/guest-token-race` (rama `fabrica/guest-token-race` desde origin/main). Usa `git -C`, nunca `cd &&`.
- PROHIBIDO: push, merge, tocar main.

## Tarea
1. Lee `frontend/src/lib/api.ts` y `frontend/src/lib/auth.ts` enteros.
2. Memoiza `ensureToken()` y `refreshAccessToken()` tras una única promise in-flight compartida (patrón single-flight): una variable top-level de módulo en api.ts, p.ej. `let inflightToken: Promise<void> | null = null` — si no es null, devuélvela; si es null, crea la promise, asígnala y límpiala a null en `finally`. Sin librerías nuevas.
3. Sustituye las claves crudas por un helper exportado desde auth.ts que use `STORAGE_KEYS` (p.ej. `storeGuestToken()`), reusando lo que ya exista.
4. Punto 3 del contexto (redirect /login).

## Criterio de aceptación (backlog item 4)
- Dos llamadas concurrentes a `ensureToken()` → UN solo fetch de guest token. Verifícalo con un test si el proyecto tiene infra de tests frontend; si no la hay, NO montes un framework de tests nuevo: verifica con un script/console harness y documenta la evidencia en el informe.
- `npm --prefix frontend run build` y `npm --prefix frontend run lint` en verde.

## Quality gate
- Oráculos en verde (tails). DRY sin over-engineering. Self code-review del diff.
- Commit: `fix(frontend): single-flight guest token fetch + shared storage keys [Track B]`.

## Informe
`.superpowers/fabrica/briefs/guest-token-race.report.md` en el repo PRINCIPAL: estado, commit, oráculos, evidencia del single-flight, decisión sobre el redirect. Mensaje final: 2 líneas.

## Memory packet (read_note solo si hace falta; wisdom-paul)
- [[Paul - perfil de trabajo]]
- [[desarrollo-agentico]]
