# Brief — purga-auth-muerto (implementación)

## Fuente de verdad
La spec `/home/paul/Documentos/proyectos/backend/ai-news-platform/.superpowers/fabrica/specs/purga-auth-muerto.spec.md`. LÉELA ENTERA antes de tocar nada. Este brief solo añade contexto operativo; en conflicto, manda la spec. Los kill-criteria K1-K5 de la spec §6 son vinculantes: si se dispara uno, PARA, documenta en el informe y termina (no improvises).

## Worktree y rama
- `/home/paul/Documentos/proyectos/backend/ai-news-platform/.worktrees/purga-auth-muerto`, rama `fabrica/purga-auth-muerto`. Usa `git -C`, nunca `cd &&`.
- La base YA incluye las ramas `fabrica/guest-token-race` (single-flight en api.ts/auth.ts) y el commit de `fabrica/retirar-chat-frontend` (cherry-picked). El K4 de la spec está resuelto por el orquestador: NO rebases ni merges nada; trabaja sobre el HEAD actual tal cual.
- Consecuencia práctica sobre la spec §2.2: `api.ts` ya tiene `doRefreshAccessToken` + `inflightRefresh` (single-flight) — TODO el aparato de refresh muere igualmente (funciones, promise, y la rama de retry-refresh en `request()`); el single-flight del GUEST token (`inflightGuestToken`, `fetchGuestToken`, `storeGuestToken`) SOBREVIVE, es el mecanismo vivo. En `auth.ts` conserva `storeGuestToken` y las STORAGE_KEYS de access/expiry; muere lo de refresh_token e `isGuestToken` según spec.
- PROHIBIDO: push, merge, tocar main.

## Orden de trabajo sugerido
1. Backend (spec §1): ficheros enteros → cirugía auth.py → app.py → models → schemas → scheduler → pyproject.
2. Migración 018 (spec §3) — commit separado con `[Track C]`.
3. Frontend (spec §2, con la consecuencia práctica de arriba).
4. Config/env (spec §5).
5. Tests (spec §4): borra los que mueren, edita los que se editan.

Commits atómicos por bloque (backend / migración / frontend / tests+config), conventional commits, `[Track B]` salvo la migración `[Track C]`.

## Entorno
- Python: no hay venv en el worktree; usa `uv venv` + `uv pip install -e ".[api,pipeline,dev]"` dentro del worktree (patrón ya usado por otro executor) — necesario porque pyproject cambia (muere `webauthn`, `passlib`).
- DB para alembic: hay un Postgres docker corriendo en `127.0.0.1:5432` (contenedor `ai-news-platform-db-1`). Copia el `.env` del repo principal al worktree si alembic lo necesita (está gitignored, NO lo commitees). OJO: esa DB es la de desarrollo — el ciclo `upgrade head` + `check` + `downgrade -1` + `upgrade head` de la spec §3 es aceptable ahí (tablas de auth descontinuadas), pero NO toques tablas de noticias.
- Frontend: `bun install` en el worktree (bun es el package manager, bun.lock tracked); regenera `bun.lock` al quitar `@simplewebauthn/browser`.

## Criterio de aceptación
El de la spec §7, literal (los 6 puntos). Sobre e2e: intenta `pytest tests/e2e/` (requiere build en `frontend/dist` — génералo tú); si la infra de Playwright no está disponible en el worktree, documenta EXACTAMENTE qué corrió y qué no — no lo declares verde sin correrlo.

## Quality gate
- Todos los oráculos de spec §7.1-7.5 con tails pegados en el informe.
- Self code-review del diff completo antes de reportar (busca: imports muertos, referencias colgantes en tests, drift entre pyproject y lock).

## Informe
`.superpowers/fabrica/briefs/purga-auth-muerto.report.md` en el repo PRINCIPAL: estado, commits, oráculos, desviaciones de la spec (si las hay, con motivo), kill-criteria evaluados. Mensaje final: 3 líneas máximo.

## Memory packet (read_note solo si hace falta; wisdom-paul)
- [[Paul - perfil de trabajo]] — no over-engineering; reversibilidad
- [[doctrina-agentes]]
- [[desarrollo-agentico]]
