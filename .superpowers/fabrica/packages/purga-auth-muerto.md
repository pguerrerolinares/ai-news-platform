# Review-package — rama `fabrica/purga-auth-muerto` [Track C]

> Veredicto de Paul AQUÍ: appendear `GATE: MERGED` o `GATE: RECHAZADA — <motivo>`.
> **ORDEN DE GATE**: mergear ANTES `fabrica/retirar-chat-frontend` y
> `fabrica/guest-token-race` (esta rama los incluye como base; el cherry-pick
> de retirar-chat dedupe solo al mergear en orden).

## Qué se hizo
Purga completa del stack de auth de usuarios descontinuado, según spec
`.superpowers/fabrica/specs/purga-auth-muerto.spec.md` (~40 items de inventario con
evidencia grep). 4 commits atómicos, 45 ficheros, **+146/−3.300**:
- `4055c6b` [Track B] backend: mueren otp.py, routes/otp.py, webauthn.py, routes/webauthn.py,
  endpoint `/auth/refresh`, `require_admin`, refresh-token store, modelos User/OtpCode/
  WebAuthnCredential, schemas, job otp_cleanup, deps `webauthn` y `passlib` (esta ya estaba
  muerta). Sobreviven: guest tokens, `require_auth_or_guest`, `require_auth` + `POST /api/chat`
  intactos (decisión cerrada de Paul), `create_access_token` (lo necesitan los tests de chat).
- `42ac8e9` **[Track C]** migración alembic 018: drop `webauthn_credentials` → `otp_codes` →
  `users` (orden FK); downgrade recrea schema acumulado (005+006+009+016). Ciclo
  upgrade/check/downgrade/upgrade verificado limpio contra DB docker local.
- `acbc120` [Track B] frontend: mueren Login/Settings/Chat/use-auth/webauthn.ts/passkey-prompt,
  `refreshAccessToken` y la rama retry-refresh; el single-flight del guest token sobrevive;
  `@simplewebauthn/browser` fuera de package.json y bun.lock.
- `7acc98b` [Track B] tests: 9 ficheros muertos, 7 editados.

## Spec aplicada
`.superpowers/fabrica/specs/purga-auth-muerto.spec.md` (completa). Kill-criteria K1-K5
evaluados uno a uno, ninguno disparado. 4 desviaciones menores documentadas en el informe
(VALID_ROLES huérfana, un test de config no inventariado, docstring colgante, count de jobs)
— todas limpieza de residuos, ninguna toca el diseño cerrado.

## Base de stacking
`fabrica/guest-token-race` + cherry-pick `58c3656` (profundidad 2, guard prohíbe merge intra-fábrica)

## Resultados de oráculo
- `pytest tests/ -m "not e2e"` (menos 1 deselect, ver abajo) → 1132 passed (ejecutor);
  `pytest tests/unit/` → 1050 passed (padre, run independiente)
- `ruff check` / `ruff format --check` / `pyright` → verdes, 0 errors
- alembic: `upgrade head` → 018, `check` limpio, `downgrade -1` recrea las 3 tablas
  (verificado con psql \d), `upgrade head` de nuevo limpio
- greps spec §7.3/§7.4 (otp/webauthn/passkey/resend/require_admin/refresh_token) → 0 hits
  (ejecutor Y padre)
- Frontend `tsc -b && vite build` → verde; `simplewebauthn` 0 menciones en package.json/lock

## Hallazgos colaterales (preexistentes, NO de esta rama — decidir aparte)
1. `tests/integration/test_api_search.py::test_ranks_by_relevance` FALLA en la base ya:
   el bootstrap de tests usa `Base.metadata.create_all`, que no crea el trigger de
   `search_vector` (vive en la migración 017). Gap test-infra vs migraciones.
2. El harness e2e está HUÉRFANO: `tests/e2e/conftest.py::_find_dist_dir()` busca
   `web/dist/...` (build Angular antiguo) y nunca `frontend/dist` → 19 tests skipped
   siempre. Los "35 E2E" de AGENTS.md no corren desde la migración a Vite.
   → Ambos candidatos a items de próxima campaña.

## Nota operativa
- El ciclo de verificación alembic se corrió contra la DB docker de DESARROLLO local:
  ahora está en 018 (tablas de auth ya dropeadas ahí). Si arrancas la API desde main
  sin mergear esto, el código de OTP/WebAuthn de main apuntaría a tablas inexistentes.
- **Scope-question de la spec §8 (confirmar en este gate)**: producción — default adoptado:
  dump manual OPCIONAL antes del deploy destructivo:
  `pg_dump -t users -t otp_codes -t webauthn_credentials ainews > auth_tables_backup.sql`
  y mergear sin más ceremonia (credenciales de un sistema descontinuado, no datos de negocio).

## Verdicts del adjudicador
Ninguno formal: las 4 desviaciones son limpieza mecánica con evidencia; la única decisión
de diseño (qué sobrevive en api.ts/auth.ts) venía pre-resuelta en brief+spec.

## Instrucción de merge (en orden)
```
git -C /home/paul/Documentos/proyectos/backend/ai-news-platform merge --no-ff fabrica/retirar-chat-frontend
git -C /home/paul/Documentos/proyectos/backend/ai-news-platform merge --no-ff fabrica/guest-token-race
git -C /home/paul/Documentos/proyectos/backend/ai-news-platform merge --no-ff fabrica/purga-auth-muerto
```

<!-- GATE: (lo escribe Paul) -->
