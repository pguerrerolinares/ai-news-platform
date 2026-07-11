# Informe — search-abort-controller

## Estado
Completo. `frontend/src/pages/Search.tsx` ahora cancela la búsqueda anterior antes de lanzar una nueva vía `AbortController`; `AbortError` se ignora silenciosamente (no pisa `error` ni `results`), y el `finally` solo limpia `loading` si el controller sigue siendo el vigente.

## Commit
`36c942e` en `fabrica/search-abort-controller` (worktree `.worktrees/search-abort-controller`):
`fix(frontend): abort in-flight search requests to avoid stale results [Track A]`

## Patrón elegido
Reuse-first: mismo patrón `abortRef` que ya usa `Chat.tsx`, no react-query. `apiGet` ya acepta `signal` (usado por Dashboard vía react-query), así que solo hizo falta pasar el signal y el guard de abort — menos código nuevo que introducir react-query en Search.

## Oráculos
- `npm run build`: verde (tsc + vite build OK, dist generado).
- `npm run lint`: 10 errores preexistentes en archivos no tocados (tabs.tsx, toggle.tsx, use-auth.tsx, use-theme.tsx, Dashboard.tsx, Trending.tsx, y un `Math.random` en otro componente) — confirmado baseline idéntico en `main` (mismo comando, mismos 10 errores). `Search.tsx`: 0 errores de lint.
- Self code-review del diff: correcto, análogo a Chat.tsx.

Nota: no había `node_modules` en el worktree; se symlinkeó temporalmente desde el repo principal para correr build/lint y se borró antes de commitear (no quedó rastro en el árbol de trabajo).
