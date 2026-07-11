# Brief — search-abort-controller

## Dónde encaja
Campaña post-auditoría. Hallazgo: `frontend/src/pages/Search.tsx` lanza búsquedas sin cancelación (0 usos de AbortController/signal); dos búsquedas rápidas pueden llegar desordenadas y una respuesta vieja pisa resultados nuevos.

## Worktree y rama
- Trabaja en `/home/paul/Documentos/proyectos/backend/ai-news-platform/.worktrees/search-abort-controller` (rama `fabrica/search-abort-controller` desde origin/main). Usa `git -C`, nunca `cd &&`.
- PROHIBIDO: push, merge, tocar main. Solo commits locales en tu rama.

## Tarea
1. Lee `frontend/src/pages/Search.tsx`, `frontend/src/pages/Chat.tsx` (patrón `abortRef` existente) y `frontend/src/lib/api.ts` (cómo acepta `signal` — Dashboard ya lo pasa vía react-query).
2. Aplica a Search el mismo patrón que ya usa el proyecto: abortar la request anterior antes de lanzar una nueva (abortRef) o, si Search puede expresarse con react-query como Dashboard, esa es la opción reuse-first — elige la que menos código nuevo introduzca y justifícalo en una línea.
3. Asegura que un abort no pinta estado de error en la UI (AbortError se ignora).

## Criterio de aceptación (backlog item 3)
- Búsqueda nueva cancela la anterior; AbortError no ensucia el estado.
- `npm --prefix frontend run build` y `npm --prefix frontend run lint` en verde.

## Quality gate
- Oráculos en verde (tails en el informe). Reuse-first (patrón existente, no inventes hook nuevo). Self code-review del diff.
- Commit: `fix(frontend): abort in-flight search requests to avoid stale results [Track A]`.

## Informe
`.superpowers/fabrica/briefs/search-abort-controller.report.md` en el repo PRINCIPAL: estado, commit, oráculos, patrón elegido. Mensaje final: 2 líneas.

## Memory packet (read_note solo si hace falta; wisdom-paul)
- [[Paul - perfil de trabajo]]
- [[desarrollo-agentico]]
