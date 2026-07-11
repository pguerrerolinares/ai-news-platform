# Brief — retirar-chat-frontend

## Dónde encaja
Campaña post-auditoría: la web es pública (guest-only); el login de usuarios (OTP/WebAuthn) está descontinuado. El chat RAG exige login completo, así que hoy está muerto en producción. Se retira del frontend. El backend NO se toca (POST /api/chat y src/rag/ los consume el servidor MCP).

## Worktree y rama
- Trabaja en `/home/paul/Documentos/proyectos/backend/ai-news-platform/.worktrees/retirar-chat-frontend` (ya creado, rama `fabrica/retirar-chat-frontend` desde origin/main). Usa `git -C <worktree>`, nunca `cd &&`.
- PROHIBIDO: push, merge, tocar main. Solo commits locales en tu rama.

## Tarea
1. En `frontend/src/App.tsx`: eliminar las rutas `/chat` y `/settings` y el bloque `RequireAuth`. Si `AuthProvider`/`RequireAuth` (hooks/use-auth) quedan sin ningún consumidor, elimina también su import/wrapper de App.tsx — pero NO borres todavía los ficheros de hooks/páginas Login/Settings/Chat en masa: eso es de otro item (purga-auth-muerto). Aquí solo se desconecta la superficie: rutas + entradas de navegación.
2. En el componente de navegación (`frontend/src/components/app-nav.tsx` o equivalente — búscalo): quitar las entradas Chat y Settings (y Login si existe en el nav).
3. Revisa que no quede ningún `<Link>`/redirect roto hacia /chat o /settings en las páginas que quedan (grep).

## Qué NO tocar
- Nada de `src/` (backend). Nada de `src/rag/` ni `src/mcp/`.
- No borrar `Chat.tsx`, `Settings.tsx`, `Login.tsx`, `use-auth.tsx` (eso lo hace purga-auth-muerto sobre otra rama).

## Criterio de aceptación (backlog item 1)
- `npm --prefix frontend run build` y `npm --prefix frontend run lint` en verde.
- Ninguna referencia a Chat/Settings/Login en el nav ni rutas activas.
- `git diff` vacío en `src/` (backend).

## Quality gate (obligatorio antes de reportar)
- Build + lint verdes (pega el tail de la salida en tu informe).
- Reuse-first: no introduzcas componentes nuevos; solo eliminas.
- Self code-review del diff antes de reportar (busca imports muertos, rutas colgantes).
- Commit atómico: `refactor(frontend): retirar chat y settings del UI (web pública guest-only) [Track B]`.

## Informe
Escribe tu informe en `.superpowers/fabrica/briefs/retirar-chat-frontend.report.md` (en el repo PRINCIPAL, no en el worktree): estado, hash de commit, salida de oráculos, decisiones tomadas. Tu mensaje final: 2 líneas máximo con estado + commit.

## Memory packet (read_note solo si lo necesitas; proyecto wisdom-paul)
- [[Paul - perfil de trabajo]] — estándares tácitos (no over-engineering, pragmatismo)
- [[doctrina-agentes]] — doctrina de ejecución
- [[desarrollo-agentico]] — principios de desarrollo agéntico
