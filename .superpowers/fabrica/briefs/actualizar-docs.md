# Brief — actualizar-docs

## Dónde encaja
Último item de la campaña post-auditoría: la documentación debe reflejar el estado del
código tras las 6 ramas de la campaña. Trabajas SOBRE la rama de la purga (base
`fabrica/purga-auth-muerto`), que ya incluye todo el frontend y backend final.

## Worktree y rama
- `/home/paul/Documentos/proyectos/backend/ai-news-platform/.worktrees/actualizar-docs`
  (rama `fabrica/actualizar-docs`, ya creada desde `fabrica/purga-auth-muerto`). `git -C`, nunca `cd &&`.
- PROHIBIDO: push, merge, tocar main.

## Contexto de decisión (cerrado)
Web pública guest-only. Descontinuados: login OTP+Resend, WebAuthn/passkeys, admin user,
usuarios registrados, refresh tokens, páginas Login/Settings/Chat. Sobreviven: guest tokens,
`require_auth_or_guest`, rate limiting, `POST /api/chat` con `require_auth` (inaccesible a
propósito: cero gasto LLM abierto; lo consumiría el MCP si algún día vuelve un emisor de
tokens de usuario). Tablas `users`/`otp_codes`/`webauthn_credentials` dropeadas (migración 018).

## Tarea
1. **AGENTS.md** (léelo entero y contrástalo con el código REAL del worktree, no con memoria):
   - Project Overview y Key facts: quitar "registered users (OTP + WebAuthn passkeys)"; audiencia = pública con guest tokens.
   - Diagrama de tablas y sección Database Schema: fuera users/otp_codes/webauthn_credentials; alembic pasa a 18 versiones.
   - Tabla de API Endpoints: fuera /auth/refresh, /auth/otp/*, /auth/webauthn/*, /auth/me. Chat: anotar "require_auth — sin emisor de tokens de usuario actualmente; consumido solo si se reintroduce" o similar.
   - Sección Auth y Configuración: guest tokens only; fuera ADMIN_EMAIL/RESEND_*/WEBAUTHN_*/OTP_*; fuera "OTP cleanup daily" del scheduler.
   - File Map: fuera otp.py, webauthn.py (ambos), Login/Settings/Chat pages, use-auth, webauthn.ts; contar tests reales (`pytest tests/unit/ -q` en el worktree para el número).
   - Testing: actualizar conteo; NOTA honesta sobre e2e: el harness busca `web/dist` (Angular antiguo) y hace skip de los 19 tests — documentarlo como known issue, no como "35 E2E passing".
   - Last updated: 2026-07-11.
2. **ADR nuevo** en `docs/` (mira el formato/numeración de los ADR existentes en docs/ — sigue exactamente ese patrón): "Web pública guest-only: descontinuación del auth de usuarios (OTP, WebAuthn, admin)". Contexto (auditoría 2026-07-11, decisión de Paul), decisión, consecuencias (chat inaccesible vía web, migración destructiva 018 con downgrade que recrea schema pero no datos, dump manual opcional pre-deploy).
3. **docs/plans/**: si hay milestone activo con items relacionados, marca lo aplicable; si no, no inventes nada.
4. Grep en `docs/runbooks/` de referencias operativas a OTP/WebAuthn/login que queden ROTAS (instrucciones que ya no funcionan): corrígelas solo si son operativas; la historia (ADRs viejos, milestone-history) NO se toca.

## Criterio de aceptación (backlog item 7)
- AGENTS.md refleja el estado real: endpoints eliminados fuera de la tabla, tablas dropeadas fuera del schema, file map sin ficheros muertos.
- ADR nuevo en docs/ siguiendo el patrón existente.
- Cero cambios en código (diff solo en *.md).

## Quality gate
- `git diff --stat` solo con .md.
- Verifica cada afirmación editada contra el código del worktree (endpoints: grep de routers en src/api/app.py; tablas: alembic/versions/018*; tests: pytest -q).
- Self-review del diff. Commit: `docs: actualizar AGENTS.md + ADR web pública guest-only [Track A]`.

## Informe
`.superpowers/fabrica/briefs/actualizar-docs.report.md` en el repo PRINCIPAL. Mensaje final: 2 líneas.

## Memory packet (read_note solo si hace falta; wisdom-paul)
- [[Paul - perfil de trabajo]]
- [[desarrollo-agentico]]
