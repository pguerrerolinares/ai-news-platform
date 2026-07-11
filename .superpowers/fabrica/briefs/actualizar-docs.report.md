# Informe — actualizar-docs

## Qué se hizo
- **AGENTS.md**: reescrito para reflejar el estado real del worktree tras las 6 ramas de
  purga (base `fabrica/purga-auth-muerto`):
  - Project Overview / Key facts: audiencia pública guest-only, sin usuarios registrados.
  - Diagrama de tablas y sección Database Schema: fuera `users`/`otp_codes`/`webauthn_credentials`
    (dropeadas en migración 018, verificado contra `alembic/versions/018_drop_user_auth_tables.py`).
  - Alembic: 17 → 18 versiones.
  - Tabla de API Endpoints: fuera `/auth/refresh`, `/auth/otp/*`, `/auth/webauthn/*`, `/auth/me`
    (verificado con grep de `@router.post/get` en `src/api/routes/auth.py`, que ahora solo
    expone `POST /api/auth/guest`). Chat anotado como inaccesible (`require_auth`, sin
    emisor de tokens de usuario).
  - Auth/Configuración: solo guest tokens; fuera `ADMIN_EMAIL`/`RESEND_*`/`WEBAUTHN_*`/`OTP_*`
    (verificado: ningún hit en `src/core/config.py`); fuera "OTP cleanup daily" del scheduler
    (verificado: ningún hit en `src/pipeline/scheduler.py`).
  - File Map: fuera `otp.py`, `webauthn.py`, páginas Login/Settings/Chat, `use-auth`,
    `webauthn.ts` (verificado: no existen en el worktree).
  - Testing: conteo real `pytest tests/unit/ -q` → 1050 passed (ejecutado en el worktree).
    Nota honesta sobre E2E: `tests/e2e/conftest.py::_find_dist_dir` busca `web/dist/...`
    (Angular viejo) y hace skip de los 19 tests siempre — documentado como known issue,
    no como "35 E2E passing".
  - Last updated: 2026-07-11.
- **ADR nuevo**: `docs/adr/002-web-publica-guest-only.md`, siguiendo el formato exacto de
  `001-remote-mcp-server.md` (Date/Status/Track, Context/Decision/Consequences/Alternatives).
  Contexto: auditoría 2026-07-11, decisión de Paul. Consecuencias: chat inaccesible vía web
  (intencional, gate de gasto LLM), migración 018 destructiva con downgrade que recrea schema
  sin datos, dump manual opcional pre-deploy.
- **docs/plans/**: revisado; no hay milestone activo con items relacionados a esta purga
  (todos los planes fechados son históricos, el último es 2026-03-16) — no se inventó nada.
- **docs/runbooks/**: grep de OTP/WebAuthn/login — cero referencias operativas; nada que corregir.

## Verificación (quality gate)
- `git diff --stat --cached`: solo `AGENTS.md` (modificado) y
  `docs/adr/002-web-publica-guest-only.md` (nuevo) — cero cambios en código.
- Cada afirmación contrastada contra el código real (no memoria): routers en `src/api/app.py`
  y `src/api/routes/*.py`, migración 018, `pytest tests/unit/ -q` (1050 passed), modelos ORM
  en `src/core/models.py`, contenido de `frontend/src/{pages,hooks,lib}`.
- Nota fuera de alcance: `pytest tests/integration/test_api_search.py::test_ranks_by_relevance`
  falla en el worktree (pre-existente, no relacionado con la purga de auth ni tocado aquí).

## Commit
Pendiente de ejecutar `git commit` (ver mensaje final de la sesión).
