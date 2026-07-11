# Spec: purga-auth-muerto

**Backlog**: item 6 (`.superpowers/fabrica/backlog-2026-07-11.md:52-65`). **Lane**: diseño, spec-first.
**Base de análisis**: `origin/main` (f4baa7f en la rama actual no afecta a este scope salvo `src/mcp/client.py`, ya verificado).
**Riesgo**: Track C (migración destructiva de DB) + Track B (borrado grande de superficie API).

## Decisión de contexto (cerrada, no re-litigar)

Web pública guest-only. Muere: login OTP+Resend, WebAuthn/passkeys, admin user, usuarios registrados.
Sobrevive: guest tokens (`POST /api/auth/guest`), `require_auth_or_guest`, rate limiting JWT-aware,
y `POST /api/chat` con `require_auth` TAL CUAL (queda inaccesible; cero gasto LLM abierto; lo
consumiría el MCP si algún día vuelve a haber emisor de tokens de usuario).

La rama `fabrica/retirar-chat-frontend` es la base asumida para el frontend (desconecta rutas
/chat, /settings y nav). **A fecha de esta spec su diff contra origin/main está vacío** (trabajo en
curso de exec-chat) — el implementador debe rebasar sobre su estado final y no duplicar ese trabajo;
esta spec solo borra los ficheros muertos que esa rama deja atrás.

---

## 1. Inventario de borrado — backend

### 1.1 Ficheros que mueren enteros

| Fichero | Qué es | Por qué muere | Quién lo referencia (grep) |
|---|---|---|---|
| `src/api/otp.py` | Generación OTP + envío email vía Resend API (httpx a `api.resend.com`) | Login OTP descontinuado | Solo `src/api/routes/otp.py` (grep `from src.api.otp\|import otp` en src/ → solo routes/otp.py) |
| `src/api/routes/otp.py` | Endpoints `POST /api/auth/otp/request`, `POST /api/auth/otp/verify`, `GET /api/auth/me` | Login OTP descontinuado. `/me` muere con él: solo lo usan `tests/unit/test_otp_routes.py:265-335`; ni frontend ni MCP lo llaman (grep `auth/me` en frontend/src y src/mcp → 0 hits) | `src/api/app.py:25,190` (import + `include_router`) |
| `src/api/webauthn.py` | Challenge store in-memory para WebAuthn (`_challenges`, `store_challenge`, `get_challenge`, `clear_challenge`) | Passkeys descontinuados | Solo `src/api/routes/webauthn.py` y `tests/unit/test_webauthn_challenges.py` |
| `src/api/routes/webauthn.py` | Endpoints `/api/auth/webauthn/{register,login}/{options,verify}`, `GET|DELETE /credentials` | Passkeys descontinuados | `src/api/app.py:30,191` (import + `include_router`) |

### 1.2 `src/api/auth.py` — cirugía, no borrado

**Sobrevive** (con evidencia de consumidor vivo):

- `UserClaims`, `_decode_access_claims` — base de los dos deps siguientes.
- `require_auth` — lo usa chat: `src/api/routes/chat.py:10,32`. Decisión cerrada: queda tal cual.
- `require_auth_or_guest` — lo usan admin, briefings, items, search, sources, stats, topics
  (grep `require_auth_or_guest` en src/api/routes → 25 usos).
- `create_guest_token` — `src/api/routes/auth.py` (endpoint `/guest`).
- `create_access_token` — **sobrevive aunque en src/ solo lo usen otp/webauthn (que mueren)**:
  es la única forma de mintear tokens no-guest, y los tests vivos lo necesitan para ejercitar
  `require_auth` (chat) y endpoints protegidos: `tests/integration/conftest.py:122-124`,
  `tests/security/conftest.py:104-106`, `tests/security/test_rate_limiting.py:30-32`,
  `tests/security/test_sql_injection.py:36-38`, `tests/unit/test_auth.py:13`,
  `tests/integration/test_api_auth.py:9`. Borrarlo dejaría chat sin test posible.

**Muere**:

| Símbolo | Por qué | Referencias |
|---|---|---|
| `create_refresh_token` | Refresh tokens eran de usuarios; los guests no refrescan (piden token nuevo: `frontend/src/lib/api.ts:38-49 ensureToken`, `src/mcp/client.py:27-46` re-adquiere guest en 401) | `src/api/routes/{auth,otp,webauthn}.py` (todos mueren o se editan), `tests/unit/test_auth.py:206-275` |
| `validate_refresh_token` | Ídem | Solo `src/api/routes/auth.py` (endpoint refresh, muere) |
| `_refresh_tokens` dict, `_MAX_REFRESH_TOKENS`, `_hash_token`, `_prune_expired` | Store in-memory de refresh tokens, sin consumidor tras lo anterior | Solo internos de auth.py |
| `require_admin` | No queda usuario admin. **Ningún route lo usa ya**: grep `require_admin` en src/ → solo su definición (`src/api/auth.py:183`); admin routes usan `require_auth_or_guest` (`src/api/routes/admin.py:16,85,167,202`) | Solo `tests/unit/test_auth.py:302-373` |

### 1.3 Endpoint `POST /api/auth/refresh` — muere

En `src/api/routes/auth.py`: se borra el handler `refresh` y los imports de
`create_access_token/create_refresh_token/validate_refresh_token`, `RefreshRequest`,
`TokenResponseV2`. El fichero queda solo con `/guest`.

Evidencia de que nadie vivo lo usa:
- Frontend: único consumidor es `frontend/src/lib/api.ts:22` (`refreshAccessToken`), que es
  parte del flujo de tokens de usuario y muere en §2.
- MCP: `src/mcp/client.py` solo llama `POST /api/auth/guest` (`client.py:28`) y en 401
  re-adquiere un guest nuevo, no refresca (`client.py:38-46`, reforzado por f4baa7f).

### 1.4 `src/api/app.py` — ediciones

- Quitar imports y `include_router` de `otp_router` (líneas 25, 190) y `webauthn_router` (30, 191).
- `_validate_production_settings`: quitar el check `admin_email`/`resend_api_key`
  (`app.py:118-119`) y su mención en el docstring. Los checks de `jwt_secret` se quedan.

### 1.5 Modelos ORM (`src/core/models.py`) — mueren

| Modelo | Tabla | Referencias fuera de código muerto |
|---|---|---|
| `User` | `users` | Solo `src/api/routes/otp.py:26`, `src/api/routes/webauthn.py:50` (ambos mueren) y tests §4 |
| `OtpCode` | `otp_codes` | `src/api/routes/otp.py:26`, `src/pipeline/scheduler.py:15,141` (job muere, §1.7) |
| `WebAuthnCredential` | `webauthn_credentials` | Solo `src/api/routes/webauthn.py` |

Grep `from src.core.models` en src/ confirma que ningún módulo vivo importa estos tres
(el resto importa NewsItem/DailyBriefing/ItemEmbedding/PipelineRun/RawExtraction).
Quitar también el import `ForeignKey` de models.py **solo si** deja de usarse — `ItemEmbedding`
lo usa (`models.py:174`), así que se queda.

### 1.6 Schemas (`src/api/schemas.py`)

Mueren (grep de cada nombre en src/ solo da los módulos que mueren en §1.1/1.3):
`OtpRequestBody`, `OtpVerifyBody`, `OtpRequestResponse`, `UserResponse`,
`WebAuthnLoginOptionsRequest`, `WebAuthnRegisterVerifyRequest`, `WebAuthnLoginVerifyRequest`,
`WebAuthnCredentialResponse`, `TokenResponseV2`, `RefreshRequest`.

Sobreviven: `GuestTokenResponse` (endpoint `/guest`), `ErrorWrapper`, `ChatRequest` y el resto.

### 1.7 Scheduler (`src/pipeline/scheduler.py`)

Mueren: el job `otp_cleanup` (`scheduler.py:126-135`), la función `cleanup_expired_otps`
(`scheduler.py:137-144`) y el import de `OtpCode` (`scheduler.py:15`). El resto de jobs
(polls de fuentes, arxiv cron) no se toca.

### 1.8 Dependencias (`pyproject.toml`)

| Dep | Estado | Evidencia |
|---|---|---|
| `webauthn~=2.5.0` (extra `api`, línea 42) | Muere | Solo la importa `src/api/routes/webauthn.py` |
| `passlib[bcrypt]~=1.7.0` (core, línea 32) | Muere — **ya estaba muerta** | grep `passlib\|bcrypt` en todo origin/main → solo pyproject.toml y docs/plans (0 imports en src/ ni tests/) |
| `pyjwt[crypto]` | Se queda | Guest tokens + require_auth siguen firmando/verificando JWT |
| `resend` | No existe como dep | El envío usa httpx directo (`src/api/otp.py:14`) — nada que quitar |
| `slowapi`, `mcp` | Se quedan | Rate limiting y MCP server vivos |

CI instala `.[api,pipeline,dev]` y Dockerfile.api `.[api]` — no requieren cambio, solo se
encoge el extra.

---

## 2. Inventario de borrado — frontend (post `fabrica/retirar-chat-frontend`)

Esta sección asume que esa rama ya desconectó rutas `/chat`, `/settings`, `/login`(nav) — si al
rebasar algo de la lista sigue **conectado** (importado desde App.tsx u otro fichero vivo), ver
kill-criteria K4.

### 2.1 Ficheros que mueren enteros

| Fichero | Qué es | Referencias en origin/main (a resolver por la rama base o esta purga) |
|---|---|---|
| `frontend/src/pages/Login.tsx` | Página de login OTP/passkey | `App.tsx:8,24` |
| `frontend/src/pages/Settings.tsx` | Gestión de passkeys | `App.tsx:9,35` |
| `frontend/src/pages/Chat.tsx` | Chat RAG (requiere usuario full) | `App.tsx:7,34` |
| `frontend/src/hooks/use-auth.tsx` | `AuthProvider`/`useAuth`/`RequireAuth` — OTP, passkey login, logout | `App.tsx:2`, `app-nav.tsx:6,22` |
| `frontend/src/lib/webauthn.ts` | Wrapper de `@simplewebauthn/browser` | `use-auth.tsx:7`, `Settings.tsx` |
| `frontend/src/components/passkey-prompt.tsx` | Banner "registra un passkey" | `Dashboard.tsx:10,81` |

### 2.2 Ediciones

- `frontend/src/App.tsx`: quitar `AuthProvider`/`RequireAuth` y las rutas login/chat/settings
  (lo que no haya quitado ya la rama base).
- `frontend/src/components/app-nav.tsx`: quitar `useAuth`, `isFullUser`, `logout`,
  `IconLogin/IconLogout/IconSettings` (`app-nav.tsx:5-6,22,47-48,62`).
- `frontend/src/pages/Dashboard.tsx`: quitar `PasskeyPrompt` (líneas 10, 81).
- `frontend/src/lib/api.ts`: quitar `refreshAccessToken` (líneas 17-34) y la rama de retry-refresh
  en `request()` (401 → pedir guest nuevo directamente, coherente con backend sin `/auth/refresh`);
  quitar el error 401 de chat (`api.ts:164`) y las funciones de chat si la rama base no lo hizo.
- `frontend/src/lib/auth.ts`: recortar a helpers de guest token (access token + expiry en
  localStorage). Mueren `refresh_token` storage, `isGuestToken`, `AuthTokens.refresh_token`
  (`auth.ts:3,9,17,26,37`). Si tras el recorte queda trivial, plegarlo en api.ts es aceptable
  (decisión pre-autorizada clase "detalles de UI/naming").
- `frontend/src/locales/en.json`: quitar bloques `login` (líneas 36-58), claves de passkeys en
  `settings` (63-72), `passkeyPrompt` (79-82) y claves de chat si la rama base no lo hizo.

### 2.3 Dependencias (`frontend/package.json`)

- `@simplewebauthn/browser` muere: único import en `frontend/src/lib/webauthn.ts:1,5`.
- Regenerar `bun.lock`.
- Nada más muere por esta purga: iconos/radix/etc. tienen otros consumidores.

---

## 3. Migración DB — **Track C**

Nueva revisión alembic `018_drop_user_auth_tables.py`, `down_revision = "017"`
(head actual: `017_fix_search_vector_definition.py`).

**Orden de drops en `upgrade()` (por FK)**:
1. `webauthn_credentials` — tiene FK `user_id → users.id ON DELETE CASCADE`
   (`alembic/versions/009_webauthn_credentials.py:31`); debe caer antes que `users`.
2. `otp_codes` — sin FKs, orden libre.
3. `users`.

**`downgrade()`**: recrea las tres tablas con el schema final acumulado — 005 (users, otp_codes)
+ 006 (server defaults de `created_at`/`used`) + 009 (webauthn_credentials) + 016 (columna
`attempts` en otp_codes) — e índices (`idx_otp_codes_lookup`, unique de email, etc.).
**Reversibilidad explícita**: el downgrade restaura el schema, NO los datos. Es asumible: son
credenciales/códigos de un sistema descontinuado, no datos de negocio. El package debe marcar
Track C en el commit.

**Verificación** (config.md líneas 24-25): `docker compose up db -d` local, luego
`alembic upgrade head && alembic check`. También `alembic downgrade -1 && alembic upgrade head`
como smoke de reversibilidad.

---

## 4. Tests

### 4.1 Mueren enteros

| Fichero | Cubre |
|---|---|
| `tests/unit/test_otp.py` | Generación/envío OTP |
| `tests/unit/test_otp_routes.py` | Endpoints otp/request, otp/verify, /me |
| `tests/unit/test_webauthn_challenges.py` | Challenge store |
| `tests/unit/test_webauthn_config.py` | Settings webauthn_* |
| `tests/unit/test_webauthn_model.py` | Modelo WebAuthnCredential |
| `tests/unit/test_webauthn_routes.py` | Endpoints webauthn |
| `tests/unit/test_webauthn_schemas.py` | Schemas webauthn |
| `tests/e2e/test_login.py` | Página de login (58 líneas) |
| `tests/e2e/test_chat.py` | Página de chat (muere con Chat.tsx) |

### 4.2 Se editan

| Fichero | Qué se quita |
|---|---|
| `tests/unit/test_auth.py` | Clases/tests de refresh tokens (líneas 206-275), `require_admin` (302-373), fixture key `jwt_refresh_expire_days` (línea 29). Se quedan: require_auth, guest tokens, require_auth_or_guest, guest-rechazado-por-require_auth (433-440) |
| `tests/unit/test_config.py` | Tests de `admin_email`, `resend_api_key`, `otp_from_email`, `otp_expire_minutes`, `otp_daily_limit` (líneas 197-245) |
| `tests/unit/test_models.py` | Secciones User y OtpCode (~líneas 216-257 y las de User) |
| `tests/unit/test_scheduler.py` | Asserts de `otp_cleanup` (líneas 31, 49-61) y `test_cleanup_expired_otps_executes` (64-81) |
| `tests/unit/test_sources_api.py` | Import/override residual de `require_auth` (líneas 11, 33) — solo limpieza |
| `tests/e2e/conftest.py` | `handle_auth`/`login_status` (líneas 164-186) y `handle_chat`; dejar mock de guest si el frontend lo pide |
| `tests/e2e/test_navigation.py` | Tests de redirect a /login (líneas 46-58) |

### 4.3 No se tocan (verificado)

`tests/security/test_auth_boundary.py` (enumera solo endpoints vivos, incl. `/api/chat` que sigue
protegido), `test_jwt_manipulation.py` (0 refs a refresh/otp), `tests/integration/test_api_auth.py`
(guest + JWT genérico), `tests/unit/test_chat_route.py` (require_auth sigue), `test_ratelimit.py`,
`test_admin_routes.py` (usan require_auth_or_guest).

---

## 5. Config / env

### 5.1 `src/core/config.py` — Settings que mueren

- Bloque "Auth (multi-user)" (líneas 163-167): `admin_email`, `resend_api_key`, `otp_from_email`,
  `otp_expire_minutes`, `otp_daily_limit`.
- Bloque "WebAuthn" (líneas 169-172): `webauthn_rp_id`, `webauthn_rp_name`, `webauthn_origin`.
- `jwt_refresh_expire_days` (línea 39): único uso en src/ es `create_refresh_token`
  (`src/api/auth.py:70`), que muere; resto de hits son docs/plans y fixtures de tests que se editan.
- Se quedan: `jwt_secret`, `jwt_algorithm`, `jwt_access_expire_minutes` (guest tokens y
  require_auth los usan).

### 5.2 `.env.example`

Mueren: bloque "Auth (multi-user OTP)" completo (`ADMIN_EMAIL`, `RESEND_API_KEY`,
`OTP_FROM_EMAIL`, `OTP_EXPIRE_MINUTES`) y `SHARED_PASSWORD` (legacy ya muerto: grep
`SHARED_PASSWORD\|shared_password` en src/ → 0 hits). No hay vars `WEBAUTHN_*` en .env.example.
Se queda `JWT_SECRET`.

### 5.3 Docker / CI

grep `RESEND\|WEBAUTHN\|ADMIN_EMAIL\|OTP_` en `docker-compose.yml`, `docker-compose.coolify.yml`,
`.github/workflows/ci.yml`, `Dockerfile.api`, `docker-entrypoint.sh` → 0 hits. Nada que cambiar.
(Si el deploy de Coolify tiene esas env vars seteadas fuera del repo, `extra="ignore"` en Settings
las hace inocuas — limpiarlas allí es housekeeping opcional, fuera de este package.)

---

## 6. Kill-criteria pre-registrados (parar e ir al gate)

- **K1**: cualquier evidencia de que el MCP (src/mcp/) usa OTP, refresh o `/api/auth/me`
  (a fecha de spec: solo usa `/api/auth/guest`, verificado en `src/mcp/client.py`).
- **K2**: descubrir en la implementación una referencia viva (no-test, no-doc) a `users`,
  `otp_codes` o `webauthn_credentials` fuera del inventario §1.5 (p.ej. una query cruda en
  `src/core/queries.py` o un job no inventariado).
- **K3**: que quitar `create_access_token` parezca necesario o que algún cambio toque el
  comportamiento de `POST /api/chat` / `require_auth` — decisión cerrada, no adjudicar.
- **K4**: al rebasar sobre `fabrica/retirar-chat-frontend`, encontrar que esa rama tomó decisiones
  incompatibles con §2 (p.ej. conservó use-auth para otra cosa) — coordinar, no pisar.
- **K5**: `alembic check` o el ciclo downgrade/upgrade fallan por drift de schema no explicado
  por esta migración.

---

## 7. Criterio de aceptación (backlog item 6, literal)

> suite completa + e2e en verde tras la purga; `alembic upgrade head` y `alembic check` pasan;
> grep sin referencias muertas a otp/webauthn en src/ y frontend/src. Track C (migración DB):
> el package lo marca explícitamente.

Operativizado:
1. `ruff check . && ruff format --check . && pyright . && pytest tests/ -x --timeout=30` verde
   (gate pre-push del proyecto), incluyendo e2e.
2. Contra DB docker local: `alembic upgrade head && alembic check` y smoke
   `alembic downgrade -1 && alembic upgrade head`.
3. `grep -ri "otp\|webauthn\|passkey\|resend" src/ frontend/src/` → 0 hits
   (docs/ y docs/plans/ quedan como historia, no se tocan aquí; AGENTS.md lo actualiza el
   item 7 `actualizar-docs`).
4. `grep -r "require_admin\|refresh_token\|RefreshRequest\|TokenResponseV2" src/ frontend/src/` → 0 hits.
5. Frontend compila (`tsc -b && vite build`) y `@simplewebauthn/browser` fuera de package.json y lock.
6. Commits con `[Track C]` en la migración; `[Track B]` en el borrado de superficie API.

---

## 8. Preguntas de scope abiertas

1. **Timing de la migración destructiva en producción**: el drop de tablas en Coolify borra los
   usuarios/credenciales reales existentes. El código no puede responder si Paul quiere conservar
   un dump previo (`pg_dump -t users -t otp_codes -t webauthn_credentials`) antes del deploy.
   Propuesta por defecto: el runbook del package incluye el comando de dump como paso manual
   opcional pre-deploy, y la migración se mergea sin más ceremonia (datos de un sistema
   descontinuado). Confirmar en el gate.

(Las demás dudas planteables — ¿muere `/auth/refresh`?, ¿muere `require_admin`?, ¿usa el MCP algo
más que guest?, ¿passlib vivo? — las responde el código; citas en §1.2, §1.3, §1.8.)
