# Review-package — rama `fabrica/retirar-chat-frontend`

> Veredicto de Paul AQUÍ: appendear `GATE: MERGED` o `GATE: RECHAZADA — <motivo>`.

## Qué se hizo
Retirada la superficie de chat/settings del UI (web pública guest-only, login
descontinuado): rutas `/chat` y `/settings` + bloque `RequireAuth` fuera de App.tsx;
entrada "Settings" y botón "Sign in" fuera del nav; `PasskeyPrompt` desconectado de
Dashboard (apuntaba a `/settings`, ya inexistente — cazado en el grep de links rotos).
Solo se DESCONECTA; los ficheros muertos (Chat.tsx, Login.tsx, use-auth…) los borra
purga-auth-muerto. Backend intacto (diff vacío en src/). 3 ficheros, +6/-31.
Commit: `58c3656` — `refactor(frontend): retirar chat y settings del UI (web pública guest-only) [Track B]`

## Spec aplicada
`.superpowers/fabrica/briefs/retirar-chat-frontend.md` (item 1 del backlog 2026-07-11)

## Base de stacking
origin/main (60d6ba9)

## Resultados de oráculo
- `npm --prefix frontend run build` → verde (ejecutor y padre, independientes)
- `npm --prefix frontend run lint` → 20 errores preexistentes (Timeline/Trending, React
  Compiler), baseline idéntico verificado con git stash por el ejecutor; 0 nuevos
- grep de rutas colgantes: sin `<Link>`/navigate a /chat o /settings en páginas conectadas

## Reviews
- Self-review del ejecutor: sin findings.
- Review de rama (orquestador fable): diff solo elimina; `AuthProvider` se mantiene con
  razón citada (useAuth aún tiene consumidores: Login.tsx, app-nav); decisión de
  desconectar PasskeyPrompt correcta y dentro del criterio de aceptación.

## Verdicts del adjudicador
Ninguno — las tres decisiones del informe citan el brief o el código; ninguna es de
diseño abierto.

## Instrucción de merge
`git -C /home/paul/Documentos/proyectos/backend/ai-news-platform merge --no-ff fabrica/retirar-chat-frontend`

<!-- GATE: (lo escribe Paul) -->
