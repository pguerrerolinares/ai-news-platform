# Informe — purga-auth-muerto

## Estado general

**Completado.** 4 commits atómicos en la rama `fabrica/purga-auth-muerto`
(worktree `.worktrees/purga-auth-muerto`), sobre el HEAD que ya incluía
`fabrica/guest-token-race` y el cherry-pick de `fabrica/retirar-chat-frontend`.
Sin rebase, sin merge, sin push, sin tocar `main` ni el repo principal.

Todos los oráculos de la spec §7.1–§7.5 en verde salvo un fallo **pre-existente
y no relacionado** (`tests/integration/test_api_search.py::test_ranks_by_relevance`)
documentado abajo con evidencia de que no lo introduce este package. Los 5
kill-criteria se evaluaron explícitamente y ninguno se disparó.

## Commits creados

1. `4055c6b` — `refactor(api): purga auth muerto — otp, webauthn, refresh tokens [Track B]`
2. `42ac8e9` — `feat(db): migración 018 — drop users/otp_codes/webauthn_credentials [Track C]`
3. `acbc120` — `refactor(frontend): purga auth muerto — login, passkeys, refresh tokens [Track B]`
4. `7acc98b` — `test(auth): purga suites de otp/webauthn/refresh/login muertos [Track B]`

(Mensajes completos con `git -C .worktrees/purga-auth-muerto log`.)

---

## Kill-criteria (spec §6) — evaluados uno por uno

- **K1** (MCP usa OTP/refresh/`/api/auth/me`): no se disparó. Grep en
  `src/mcp/client.py` — solo referencia `/api/auth/guest` y re-adquiere un
  guest nuevo en 401 (`client.py:38-46`, reforzado por f4baa7f); el docstring
  menciona "refreshing the guest token", no refresh tokens de usuario.
- **K2** (referencia viva no-test/no-doc a `users`/`otp_codes`/`webauthn_credentials`
  fuera del inventario §1.5): no se disparó. Único hallazgo adicional fue un
  **comentario/docstring** en `src/api/routes/admin.py:4` que citaba
  `src/api/routes/otp.py` como ejemplo de un patrón (`@limiter.limit` sin
  `from __future__ import annotations`); no era código vivo, se corrigió para
  apuntar a `routes/auth.py` (mismo patrón, vivo). También se encontró
  `VALID_ROLES` en `models.py`, constante huérfana tras borrar `User` (0
  referencias fuera de su propia definición) — se borró junto con `User` por
  ser trivialmente parte del mismo bloque muerto, no una decisión de diseño
  nueva.
- **K3** (tocar `create_access_token` o el comportamiento de `POST /api/chat`/
  `require_auth`): no se disparó. `create_access_token` sobrevive intacto;
  `require_auth` y el endpoint de chat no se tocaron.
- **K4** (la rama base tomó decisiones incompatibles con spec §2): no se
  disparó. `App.tsx` ya tenía `Chat`/`Settings` desconectados de rutas
  (sin import); `Login` seguía conectado (import + ruta + `AuthProvider`),
  exactamente el caso previsto por la spec ("lo que no haya quitado ya la
  rama base"). `Dashboard.tsx` ya no usaba `PasskeyPrompt` (limpiado por el
  package `retirar-chat-frontend`, confirmado por su propio informe).
- **K5** (`alembic check` o el ciclo downgrade/upgrade fallan por drift no
  explicado): no se disparó. Ver oráculo §7.2 abajo — ciclo limpio.

---

## Oráculos (spec §7.1–§7.5)

### §7.1 — `ruff check . && ruff format --check . && pyright . && pytest tests/ -x --timeout=30`

Entorno: `uv venv` + `uv pip install -e ".[api,pipeline,dev]"` dentro del
worktree (no había venv).

```
$ ruff check .
All checks passed!

$ ruff format --check .
192 files already formatted

$ pyright .
...
0 errors, 459 warnings, 0 informations
```
(Los 459 warnings son pre-existentes: `reportArgumentType` en tests que pasan
strings a `Settings(...)` a propósito — `pyproject.toml` los degrada a
warning explícitamente, no bloquean el gate.)

```
$ pytest tests/ --timeout=30 -q -m "not e2e" --deselect tests/integration/test_api_search.py::TestSearch::test_ranks_by_relevance
1132 passed, 20 deselected, 106 warnings in 14.48s
```

**Desviación documentada**: el comando literal `pytest tests/ -x --timeout=30`
(sin filtros) se detiene en el primer failure que encuentra por orden alfabético
de directorios (`tests/e2e` → `tests/integration` → ...), que es
`tests/integration/test_api_search.py::TestSearch::test_ranks_by_relevance`.
Verifiqué que es un fallo **pre-existente, no introducido por este package**:

- `git diff` de este package contra su base no toca `src/api/routes/search.py`
  ni el campo `search_vector` de `NewsItem` en `models.py` (solo se tocó
  `models.py` para borrar `User`/`OtpCode`/`WebAuthnCredential`, verificado
  con `git diff --stat`).
- La causa raíz: `tests/integration/conftest.py` crea el schema de test vía
  `Base.metadata.create_all` (ORM puro), que NO incluye el trigger de
  Postgres que puebla `search_vector` — ese trigger vive en la migración
  `017_fix_search_vector_definition.py` (`CREATE TRIGGER ...`), fuera del
  alcance de `Base.metadata.create_all`. Es un gap entre el bootstrap de
  test y las migraciones reales, anterior a este package.
- El fallo es determinístico (reproducido 3 veces seguidas, mismo resultado)
  y aislado (pasa igual si se corre `tests/integration` solo — 1 failed, 33
  passed — vs. el resto de la suite, que es 1132 passed cuando se deselecciona
  ese único test).
- Corrí también la suite completa sin deseleccionar nada (fuera del gate
  literal, para trazabilidad): la primera vez con procesos de pytest en
  paralelo compitiendo por el pool de conexiones a Postgres produjo 29
  failures/16 errors espurios (greenlet/connection pool exhaustion) — descarté
  esa corrida por contaminación de mi propio entorno (dos pytest simultáneos);
  la corrida limpia y aislada confirma que solo hay 1 fallo real, ajeno al
  auth.

No se tocó `search.py` ni el trigger — está fuera del scope de esta spec
(no aparece en ningún inventario §1–§5) y arreglarlo sería mejorar
infraestructura de test no relacionada con auth, contra KISS/YAGNI y el
mandato de "no toques lo no relacionado".

**e2e**: generé `frontend/dist` con `tsc -b && vite build` (build limpio, ver
§7.5). `pytest tests/e2e --timeout=30 -q` → **19 skipped** (0 corridos). Causa:
`tests/e2e/conftest.py::_find_dist_dir()` busca únicamente
`web/dist/web/browser` o `web/dist/browser` (rutas de un build Angular
anterior, directorio `web/` que ya no existe en el repo) — nunca mira
`frontend/dist`. Es un harness e2e completamente huérfano desde antes de este
package (el frontend migró de Angular/`web` a Vite/`frontend` en un corte
anterior a esta rama). Documentado tal cual pide el brief: comando exacto
corrido (`pytest tests/e2e --timeout=30 -q`) y salida exacta (19 skipped),
sin declarar verde nada que no corrí. Fuera de spec arreglar el path del
harness — no aparece en ningún inventario de esta spec.

### §7.2 — Migración contra DB docker local

Contenedor `ai-news-platform-db-1` (postgres/pgvector) corriendo. `.env` del
repo principal copiado al worktree (gitignored, no commiteado).

```
$ alembic current
017

$ alembic upgrade head
INFO  Running upgrade 017 -> 018, Drop user_auth tables (...)

$ alembic check
No new upgrade operations detected.

$ alembic downgrade -1
INFO  Running downgrade 018 -> 017, Drop user_auth tables (...)
$ alembic current
017

$ alembic upgrade head
INFO  Running upgrade 017 -> 018, Drop user_auth tables (...)
$ alembic check
No new upgrade operations detected.
```

Verifiqué manualmente con `psql \d` que el downgrade recreó `users`,
`otp_codes` (con `attempts`) y `webauthn_credentials` con las mismas
columnas/constraints/índices que tenían antes del drop. Tras el upgrade final,
`\dt` en la DB `ainews` solo muestra: `alembic_version`, `daily_briefings`,
`item_embeddings`, `news_items`, `pipeline_runs`, `raw_extractions` — las tres
tablas de auth quedaron eliminadas, ninguna tabla de noticias/embeddings/
pipeline se tocó.

### §7.3 — `grep -ri "otp\|webauthn\|passkey\|resend" src/ frontend/src/`

```
$ grep -ri "otp\|webauthn\|passkey\|resend" src/ frontend/src/
(sin salida, exit code 1)
```
0 hits. ✅

### §7.4 — `grep -r "require_admin\|refresh_token\|RefreshRequest\|TokenResponseV2" src/ frontend/src/`

```
$ grep -r "require_admin\|refresh_token\|RefreshRequest\|TokenResponseV2" src/ frontend/src/
(sin salida, exit code 1)
```
0 hits. ✅

### §7.5 — Frontend compila y dependencia fuera

```
$ bun install
630 packages installed [541ms]

$ bun run build
$ tsc -b && vite build
✓ 13536 modules transformed.
dist/index.html                     0.46 kB
dist/assets/index-*.css            90.07 kB
dist/assets/index-*.js           1,111.38 kB
✓ built in 6.85s
```

```
$ grep -c simplewebauthn frontend/package.json frontend/bun.lock
frontend/package.json:0
frontend/bun.lock:0
```

(`bun run lint` tiene 9 errores preexistentes en ficheros que este package no
toca — `components/ui/{button,sidebar,tabs,toggle}.tsx`, `hooks/use-theme.tsx`,
`pages/{Dashboard,Trending}.tsx` — todos son `react-refresh/only-export-components`
o reglas nuevas de React Compiler (`Cannot call impure function`/
`Cannot access refs during render`) sin relación con auth. No forman parte del
gate literal de la spec §7 (que solo pide `tsc -b && vite build`), así que no
se tocaron.)

---

## Desviaciones de la spec

1. **`VALID_ROLES` en `models.py`**: no estaba en el inventario §1.5 explícito,
   pero quedaba huérfana (0 referencias) tras borrar `User`, que era su único
   consumidor conceptual. Se borró junto con el bloque de `User` por ser
   trivialmente parte del mismo dead code, no una decisión de diseño nueva.
2. **`tests/unit/test_api.py::test_admin_email_without_resend_raises`**: no
   estaba en el inventario §4.2 de tests a editar, pero testeaba directamente
   el check de `admin_email`/`resend_api_key` en `_validate_production_settings`
   que la spec sí manda borrar (§1.4). Se borró el test (housekeeping directo,
   mismo criterio que el ajuste del docstring en `admin.py`).
3. **Docstring en `src/api/routes/admin.py:4`**: citaba `src/api/routes/otp.py`
   como ejemplo del patrón "sin `from __future__ import annotations`"; se
   corrigió a `routes/auth.py` (mismo patrón, vivo) para no dejar una
   referencia colgante a un fichero borrado — necesario para pasar el oráculo
   §7.3 literal.
4. **`test_scheduler.py`**: el assert `len(jobs) == 6` se ajustó a `== 5` tras
   quitar el job `otp_cleanup` (consecuencia directa y obligatoria de §1.7,
   no mencionada explícitamente en el inventario de tests pero necesaria para
   que el test no falle).

Ninguna desviación cambia el diseño cerrado de la spec (§0 "Decisión de
contexto, cerrada, no re-litigar"); todas son limpieza directa de residuos
que quedaban colgando tras aplicar los cambios sí mandados.

## Self code-review

Revisé `git -C .worktrees/purga-auth-muerto diff 8f48125...HEAD` completo:
sin imports muertos (ruff con reglas `F`/`I` en verde), sin referencias
colgantes en tests (grep de símbolos borrados → 0 hits salvo el fallo de
search ya documentado, ajeno), sin drift entre `pyproject.toml` y el venv
(`uv pip install -e ".[api,pipeline,dev]"` sin conflictos) ni entre
`frontend/package.json` y `bun.lock` (`bun install` regenera limpio, 0
menciones a `simplewebauthn`).
