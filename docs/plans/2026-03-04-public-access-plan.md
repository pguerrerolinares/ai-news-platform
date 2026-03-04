# Public Access + Guest Tokens Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Open the platform to public visitors with guest tokens, remove legacy shared-password auth, and add differentiated rate limiting.

**Architecture:** New `POST /api/auth/guest` endpoint issues short-lived JWTs with `role: "guest"`. A new `require_auth_or_guest` dependency replaces `require_auth` on read-only endpoints. Frontend acquires guest tokens automatically and only requires login for chat/settings.

**Tech Stack:** FastAPI, python-jose (JWT), slowapi (rate limiting), React 19, react-router

---

### Task 1: Backend — Add `create_guest_token` and `require_auth_or_guest`

**Files:**
- Modify: `src/api/auth.py:1-160`
- Test: `tests/unit/test_auth.py`

**Step 1: Write failing tests for guest token creation and auth-or-guest dependency**

Add to `tests/unit/test_auth.py`:

```python
# ---------------------------------------------------------------------------
# Guest tokens
# ---------------------------------------------------------------------------
class TestGuestTokens:
    """Tests for guest token creation and require_auth_or_guest."""

    def test_create_guest_token_has_guest_role(self):
        test_settings = _make_test_settings()
        with patch("src.api.auth.get_settings", return_value=test_settings):
            from src.api.auth import create_guest_token
            token = create_guest_token()
        payload = jwt.decode(token, TEST_SECRET, algorithms=[TEST_ALGORITHM])
        assert payload["role"] == "guest"
        assert payload["sub"].startswith("guest:")
        assert payload["type"] == "access"

    def test_create_guest_token_has_exp(self):
        test_settings = _make_test_settings()
        with patch("src.api.auth.get_settings", return_value=test_settings):
            from src.api.auth import create_guest_token
            token = create_guest_token()
        payload = jwt.decode(token, TEST_SECRET, algorithms=[TEST_ALGORITHM])
        assert "exp" in payload
        assert "jti" in payload

    async def test_require_auth_or_guest_accepts_guest_token(self):
        test_settings = _make_test_settings()
        from fastapi.security import HTTPAuthorizationCredentials
        from src.api.auth import require_auth_or_guest, create_guest_token

        with patch("src.api.auth.get_settings", return_value=test_settings):
            token = create_guest_token()
            creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
            user = await require_auth_or_guest(creds)
        assert user.role == "guest"
        assert user.sub.startswith("guest:")

    async def test_require_auth_or_guest_accepts_regular_token(self):
        test_settings = _make_test_settings()
        from fastapi.security import HTTPAuthorizationCredentials
        from src.api.auth import require_auth_or_guest

        with patch("src.api.auth.get_settings", return_value=test_settings):
            token = create_access_token(subject="user-uuid", role="reader", email="u@test.com")
            creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
            user = await require_auth_or_guest(creds)
        assert user.role == "reader"

    async def test_require_auth_rejects_guest_token(self):
        """require_auth (strict) should reject guest tokens."""
        test_settings = _make_test_settings()
        from fastapi.security import HTTPAuthorizationCredentials
        from src.api.auth import require_auth, create_guest_token
        from src.api.errors import APIError

        with patch("src.api.auth.get_settings", return_value=test_settings):
            token = create_guest_token()
            creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
            with pytest.raises(APIError) as exc_info:
                await require_auth(creds)
            assert exc_info.value.status_code == 401
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_auth.py::TestGuestTokens -v`
Expected: FAIL (ImportError — `create_guest_token` and `require_auth_or_guest` don't exist yet)

**Step 3: Implement `create_guest_token` and `require_auth_or_guest`**

In `src/api/auth.py`, add after `create_refresh_token`:

```python
def create_guest_token() -> str:
    """Create a short-lived guest JWT for unauthenticated visitors."""
    settings = get_settings()
    expire = datetime.now(tz=UTC) + timedelta(hours=24)
    payload: dict[str, object] = {
        "sub": f"guest:{uuid.uuid4().hex[:12]}",
        "exp": expire,
        "type": "access",
        "role": "guest",
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
```

Modify `require_auth` to reject guest tokens — add after the `if payload.get("type")` check:

```python
        if payload.get("role") == "guest":
            raise APIError(401, "GUEST_NOT_ALLOWED", "Authentication required")
```

Add new dependency after `require_admin`:

```python
async def require_auth_or_guest(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UserClaims:
    """Accept both authenticated users and guest tokens."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("type") not in ("access", None):
            raise APIError(401, "INVALID_TOKEN", "Token is not an access token")
        sub: str | None = payload.get("sub")
        if sub is None:
            raise APIError(401, "INVALID_TOKEN", "Invalid or expired token")
        return UserClaims(
            sub=sub,
            role=payload.get("role", "reader"),
            email=payload.get("email", ""),
        )
    except JWTError:
        raise APIError(401, "INVALID_TOKEN", "Invalid or expired token") from None
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_auth.py -v`
Expected: ALL PASS

**Step 5: Commit**

```
feat: add guest token creation and require_auth_or_guest dependency
```

---

### Task 2: Backend — Add `POST /api/auth/guest` endpoint

**Files:**
- Modify: `src/api/routes/auth.py:1-59`
- Modify: `src/api/schemas.py` (add `GuestTokenResponse`)
- Test: `tests/unit/test_auth.py`

**Step 1: Write failing test**

Add to `tests/unit/test_auth.py`:

```python
class TestGuestEndpoint:
    """Tests for POST /api/auth/guest."""

    async def test_guest_endpoint_returns_200(self, api_client: AsyncClient):
        resp = await api_client.post("/api/auth/guest")
        assert resp.status_code == 200

    async def test_guest_endpoint_returns_access_token(self, api_client: AsyncClient):
        resp = await api_client.post("/api/auth/guest")
        data = resp.json()
        assert "access_token" in data
        assert "expires_in" in data
        assert data["token_type"] == "bearer"
        # Guest tokens should NOT have refresh tokens
        assert "refresh_token" not in data

    async def test_guest_token_is_valid_jwt(self, api_client: AsyncClient):
        resp = await api_client.post("/api/auth/guest")
        token = resp.json()["access_token"]
        payload = jwt.decode(token, TEST_SECRET, algorithms=[TEST_ALGORITHM])
        assert payload["role"] == "guest"
        assert payload["sub"].startswith("guest:")
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_auth.py::TestGuestEndpoint -v`
Expected: FAIL (404 — endpoint doesn't exist)

**Step 3: Add schema and endpoint**

In `src/api/schemas.py`, add after `TokenResponseV2`:

```python
class GuestTokenResponse(BaseModel):
    access_token: str
    expires_in: int
    token_type: str = "bearer"
```

In `src/api/routes/auth.py`, add import of `create_guest_token` and add endpoint:

```python
from src.api.auth import (
    create_access_token,
    create_guest_token,
    create_refresh_token,
    validate_refresh_token,
)
from src.api.schemas import (
    ErrorWrapper,
    GuestTokenResponse,
    RefreshRequest,
    TokenRequest,
    TokenResponseV2,
)
```

Add endpoint before the `/token` endpoint:

```python
@router.post("/guest", response_model=GuestTokenResponse)
@limiter.limit("10/minute")
async def guest_token(request: Request) -> GuestTokenResponse:
    """Issue a guest token for unauthenticated visitors."""
    token = create_guest_token()
    return GuestTokenResponse(
        access_token=token,
        expires_in=24 * 3600,
    )
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_auth.py -v`
Expected: ALL PASS

**Step 5: Commit**

```
feat: add POST /api/auth/guest endpoint for public access
```

---

### Task 3: Backend — Remove legacy shared-password auth

**Files:**
- Modify: `src/api/routes/auth.py` (delete `/token` endpoint)
- Modify: `src/api/schemas.py` (delete `TokenRequest`)
- Modify: `src/core/config.py:40-43` (delete `shared_password`)
- Modify: `tests/unit/test_auth.py` (delete legacy test classes, update fixtures)
- Test: `tests/unit/test_auth.py`

**Step 1: Delete the `/token` endpoint from `src/api/routes/auth.py`**

Remove lines 18-33 (the entire `login` function and its decorators). Also remove `import hmac` and `TokenRequest` from imports.

The file should only have: `guest_token` and `refresh` endpoints.

**Step 2: Delete `TokenRequest` from `src/api/schemas.py`**

Remove lines 52-53:
```python
class TokenRequest(BaseModel):
    password: str
```

**Step 3: Remove `shared_password` from `src/core/config.py`**

Remove lines 40-43:
```python
    shared_password: str = Field(
        default="change-me-in-production",
        description="Shared password for login (semi-public app)",
    )
```

**Step 4: Update tests**

In `tests/unit/test_auth.py`:
- Delete `TEST_PASSWORD` constant
- Remove `shared_password` from `_make_test_settings` defaults
- Delete entire `TestTokenEndpointSuccess` class
- Delete entire `TestTokenEndpointFailure` class
- Update `TestRequireAuth.test_valid_token_passes` — use `create_access_token` directly instead of logging in via `/api/auth/token`
- Update `TestRefreshTokens` — use `create_refresh_token` directly instead of logging in via `/api/auth/token`
- Delete `TestRefreshTokens.test_login_returns_refresh_token` (no more login endpoint)
- Update `test_refresh_returns_new_tokens` to create refresh token directly
- Update `test_old_refresh_token_rejected_after_rotation` similarly
- Update `test_access_token_with_refresh_type_rejected` similarly
- Search all test files for `shared_password` references and remove them

**Step 5: Run full test suite**

Run: `pytest tests/unit/test_auth.py -v`
Expected: ALL PASS (no references to removed code)

Run: `ruff check src/api/routes/auth.py src/api/schemas.py src/core/config.py`
Expected: Clean

**Step 6: Commit**

```
refactor: remove legacy shared-password auth endpoint

BREAKING: POST /api/auth/token removed. Use OTP or passkey login.
The shared_password config setting is no longer used.
```

---

### Task 4: Backend — Switch public endpoints to `require_auth_or_guest`

**Files:**
- Modify: `src/api/routes/items.py` (8 endpoints)
- Modify: `src/api/routes/search.py` (1 endpoint)
- Modify: `src/api/routes/briefings.py` (2 endpoints)
- Modify: `src/api/routes/stats.py` (8 endpoints)
- Test: `tests/unit/test_auth.py`

**Step 1: Write a test that guest tokens work on public endpoints**

Add to `tests/unit/test_auth.py`:

```python
class TestGuestAccessPublicEndpoints:
    """Guest tokens should access public read-only endpoints."""

    async def test_guest_can_access_items(self, api_client: AsyncClient):
        from src.api.auth import create_guest_token
        from src.core.database import get_session
        from unittest.mock import AsyncMock, MagicMock

        test_settings = _make_test_settings()
        with patch("src.api.auth.get_settings", return_value=test_settings):
            token = create_guest_token()

        async def _mock_session():
            mock_result = MagicMock()
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = []
            mock_result.scalars.return_value = mock_scalars
            mock_result.scalar_one.return_value = 0
            session = AsyncMock()
            session.execute = AsyncMock(return_value=mock_result)
            yield session

        app.dependency_overrides[get_session] = _mock_session
        try:
            resp = await api_client.get(
                "/api/items", headers={"Authorization": f"Bearer {token}"}
            )
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.pop(get_session, None)

    async def test_guest_cannot_access_chat(self, api_client: AsyncClient):
        from src.api.auth import create_guest_token

        test_settings = _make_test_settings()
        with patch("src.api.auth.get_settings", return_value=test_settings):
            token = create_guest_token()

        resp = await api_client.post(
            "/api/chat",
            json={"question": "test"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_auth.py::TestGuestAccessPublicEndpoints::test_guest_can_access_items -v`
Expected: FAIL (401 — `require_auth` rejects guest tokens)

**Step 3: Replace `require_auth` with `require_auth_or_guest` in public route files**

In each of these files, change the import and all `Depends(require_auth)` to `Depends(require_auth_or_guest)`:

**`src/api/routes/items.py`:**
```python
# Change import
from src.api.auth import UserClaims, require_auth_or_guest
# Change all 8 occurrences of:
#   _user: UserClaims = Depends(require_auth)
# to:
#   _user: UserClaims = Depends(require_auth_or_guest)
```

**`src/api/routes/search.py`:**
```python
from src.api.auth import UserClaims, require_auth_or_guest
# 1 occurrence
```

**`src/api/routes/briefings.py`:**
```python
from src.api.auth import UserClaims, require_auth_or_guest
# 2 occurrences
```

**`src/api/routes/stats.py`:**
```python
from src.api.auth import UserClaims, require_auth_or_guest
# 8 occurrences
```

**Do NOT change:** `routes/chat.py`, `routes/otp.py`, `routes/webauthn.py` — these stay with `require_auth`.

**Step 4: Run tests**

Run: `pytest tests/unit/test_auth.py -v`
Expected: ALL PASS

Run: `ruff check src/api/routes/`
Expected: Clean

**Step 5: Commit**

```
feat: switch read-only endpoints to require_auth_or_guest

Items, search, briefings, and stats endpoints now accept guest tokens.
Chat and auth endpoints still require full authentication.
```

---

### Task 5: Backend — Differentiated rate limiting by token type

**Files:**
- Modify: `src/api/ratelimit.py`
- Test: `tests/unit/test_ratelimit.py` (new test if needed, or add to existing)

**Step 1: Write failing test**

Create or add to rate limit tests:

```python
# tests/unit/test_ratelimit.py
from unittest.mock import MagicMock, patch
from src.api.ratelimit import get_rate_limit_key
from src.core.config import Settings

def _make_test_settings(**overrides) -> Settings:
    defaults = {
        "jwt_secret": "test-secret",
        "shared_password": "x",
        "database_url": "postgresql+asyncpg://x:x@localhost/x",
        "database_url_sync": "postgresql://x:x@localhost/x",
    }
    defaults.update(overrides)
    return Settings(**defaults)

def test_rate_limit_key_returns_jti_for_guest():
    """Guest tokens should be rate-limited by their jti claim."""
    from jose import jwt
    token = jwt.encode(
        {"sub": "guest:abc", "role": "guest", "jti": "unique-jti-123", "type": "access"},
        "test-secret",
        algorithm="HS256",
    )
    request = MagicMock()
    request.headers = {"Authorization": f"Bearer {token}"}
    request.client.host = "10.0.1.5"

    with patch("src.api.ratelimit.get_settings", return_value=_make_test_settings()):
        key = get_rate_limit_key(request)
    assert key == "guest:unique-jti-123"

def test_rate_limit_key_returns_sub_for_authenticated():
    """Authenticated tokens should be rate-limited by their sub claim."""
    from jose import jwt
    token = jwt.encode(
        {"sub": "user-uuid-456", "role": "reader", "type": "access"},
        "test-secret",
        algorithm="HS256",
    )
    request = MagicMock()
    request.headers = {"Authorization": f"Bearer {token}"}
    request.client.host = "10.0.1.5"

    with patch("src.api.ratelimit.get_settings", return_value=_make_test_settings()):
        key = get_rate_limit_key(request)
    assert key == "user:user-uuid-456"

def test_rate_limit_key_falls_back_to_ip():
    """No token should fall back to IP-based limiting."""
    request = MagicMock()
    request.headers = {}
    request.client.host = "1.2.3.4"

    key = get_rate_limit_key(request)
    assert key == "ip:1.2.3.4"
```

**Step 2: Run to verify failure**

Run: `pytest tests/unit/test_ratelimit.py -v`
Expected: FAIL (ImportError — `get_rate_limit_key` doesn't exist)

**Step 3: Implement `get_rate_limit_key`**

In `src/api/ratelimit.py`, add:

```python
from src.core.config import get_settings

def get_rate_limit_key(request: Request) -> str:
    """Extract rate-limit key from JWT (if present) or fall back to IP.

    - Guest tokens: keyed by "guest:{jti}"
    - Authenticated tokens: keyed by "user:{sub}"
    - No token: keyed by "ip:{client_ip}"
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            from jose import jwt as jose_jwt

            settings = get_settings()
            payload = jose_jwt.decode(
                token,
                settings.jwt_secret,
                algorithms=[settings.jwt_algorithm],
                options={"verify_exp": False},
            )
            role = payload.get("role", "")
            if role == "guest":
                jti = payload.get("jti", "unknown")
                return f"guest:{jti}"
            sub = payload.get("sub", "unknown")
            return f"user:{sub}"
        except Exception:
            pass
    return f"ip:{get_client_ip(request)}"
```

**Step 4: Run tests**

Run: `pytest tests/unit/test_ratelimit.py -v`
Expected: ALL PASS

**Step 5: Commit**

```
feat: add JWT-aware rate limit key function

Rate limits are now per-token (guest by jti, user by sub) instead of
per-IP. Falls back to IP when no token is present.
```

---

### Task 6: Frontend — Guest token auto-acquisition in auth hook

**Files:**
- Modify: `frontend/src/lib/auth.ts` (add guest token storage helpers)
- Modify: `frontend/src/lib/api.ts` (acquire guest token on 401/403)
- Modify: `frontend/src/hooks/use-auth.tsx` (remove `loginLegacy`, add guest state)

**Step 1: Update `frontend/src/lib/auth.ts`**

Add a `isGuestToken()` helper:

```typescript
export function isGuestToken(): boolean {
  const token = getAccessToken()
  if (!token) return false
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return payload.role === 'guest'
  } catch {
    return false
  }
}
```

**Step 2: Update `frontend/src/lib/api.ts`**

Add guest token acquisition. When a request gets a 401/403 and there's no token at all, fetch a guest token first:

```typescript
async function ensureToken(): Promise<void> {
  if (getAccessToken() && !isTokenExpired()) return
  // No valid token — get a guest token
  if (!getRefreshToken()) {
    const res = await fetch(`${BASE_URL}/api/auth/guest`, { method: 'POST' })
    if (res.ok) {
      const data = await res.json()
      // Store guest token — no refresh token
      localStorage.setItem('auth_access_token', data.access_token)
      localStorage.setItem('auth_expires_at', String(Date.now() + data.expires_in * 1000))
    }
  }
}
```

Call `await ensureToken()` at the top of the `request()` function, before making the fetch.

Also update the 401 handler: only redirect to `/login` if the user had a real (non-guest) session. For guest tokens, just re-acquire a fresh guest token:

```typescript
if (res.status === 401 && retry) {
  const refreshed = await refreshAccessToken()
  if (refreshed) {
    return request<T>(path, options, false)
  }
  // If was a guest token, just get a new one
  if (isGuestToken() || !hasTokens()) {
    clearTokens()
    await ensureToken()
    return request<T>(path, options, false)
  }
  clearTokens()
  window.location.replace('/login')
  throw new ApiError(401, 'UNAUTHORIZED', 'Session expired')
}
```

Import `isGuestToken` from `./auth`.

**Step 3: Update `frontend/src/hooks/use-auth.tsx`**

- Remove `loginLegacy` from the context value and interface
- Add `isGuest` boolean to context
- `isAuthenticated` should be true for both real users AND guests (they can browse)
- Add `isFullUser` computed: `hasTokens() && !isTokenExpired() && !isGuestToken()`

```typescript
interface AuthContextValue {
  isAuthenticated: boolean  // true if has any valid token (guest or real)
  isFullUser: boolean       // true only if has a real (non-guest) token
  requestOtp: (email: string) => Promise<void>
  verifyOtp: (email: string, code: string) => Promise<void>
  loginPasskey: (email: string) => Promise<void>
  logout: () => void
}
```

**Step 4: Commit**

```
feat(frontend): add guest token auto-acquisition

Frontend now automatically acquires guest tokens for unauthenticated
visitors. Removed loginLegacy. Added isFullUser flag to distinguish
guest from authenticated sessions.
```

---

### Task 7: Frontend — Update routing (public vs private)

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/hooks/use-auth.tsx` (`RequireAuth` uses `isFullUser`)

**Step 1: Update `RequireAuth` to check `isFullUser`**

In `frontend/src/hooks/use-auth.tsx`:

```typescript
export function RequireAuth({ children }: { children: ReactNode }) {
  const { isFullUser } = useAuth()
  const location = useLocation()

  if (!isFullUser) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <>{children}</>
}
```

**Step 2: Update `App.tsx` — move Layout outside RequireAuth**

```typescript
function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="login" element={<Login />} />
          <Route element={<Layout />}>
            <Route index element={<Latest />} />
            <Route path="top" element={<Top />} />
            <Route path="search" element={<Search />} />
            <Route path="timeline" element={<Timeline />} />
            <Route element={<RequireAuth><Outlet /></RequireAuth>}>
              <Route path="chat" element={<Chat />} />
              <Route path="settings" element={<Settings />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
```

Add `import { Outlet } from 'react-router'` to imports.

**Step 3: Commit**

```
feat(frontend): make main routes public, protect only chat and settings
```

---

### Task 8: Frontend — Update nav bar (Sign in / Sign out)

**Files:**
- Modify: `frontend/src/components/app-nav.tsx`

**Step 1: Update nav to show Sign in or user controls**

```typescript
import { NavLink, useNavigate } from 'react-router'
import { Button } from '@/components/ui/button'
import { ThemeToggle } from '@/components/theme-toggle'
import { useScrollDirection } from '@/hooks/use-scroll-direction'
import { IconLogin, IconLogout, IconSettings } from '@tabler/icons-react'
import { motion } from 'motion/react'
import { useAuth } from '@/hooks/use-auth'

const links = [
  { to: '/', label: 'Latest' },
  { to: '/top', label: 'Top' },
  { to: '/timeline', label: 'Timeline' },
  { to: '/search', label: 'Search' },
]

export function AppNav() {
  const { isFullUser, logout } = useAuth()
  const scrollDir = useScrollDirection()
  const navigate = useNavigate()

  return (
    <header
      className={`sticky z-50 bg-background/80 backdrop-blur-sm transition-[top] duration-300 ${
        scrollDir === 'down' ? '-top-24' : 'top-0'
      }`}
    >
      <div className="mx-auto flex h-12 max-w-2xl items-center px-4">
        <NavLink to="/" className="text-lg font-bold tracking-tight">
          AI News
        </NavLink>
        <div className="ml-auto flex items-center gap-1">
          <ThemeToggle />
          {isFullUser ? (
            <>
              <NavLink to="/settings">
                <Button variant="ghost" size="icon" className="size-8" aria-label="Settings">
                  <IconSettings className="size-4" />
                </Button>
              </NavLink>
              <Button variant="ghost" size="icon" className="size-8" onClick={logout} aria-label="Log out">
                <IconLogout className="size-4" />
              </Button>
            </>
          ) : (
            <Button
              variant="ghost"
              size="sm"
              className="gap-1.5 text-sm"
              onClick={() => navigate('/login')}
            >
              <IconLogin className="size-4" />
              Sign in
            </Button>
          )}
        </div>
      </div>
      <nav className="mx-auto flex max-w-2xl gap-1 px-4 pb-2">
        {links.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `relative rounded-full px-3 py-1 text-sm font-medium transition-colors ${
                isActive
                  ? 'text-primary-foreground'
                  : 'text-muted-foreground hover:text-foreground hover:bg-accent'
              }`
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <motion.span
                    layoutId="nav-active"
                    className="absolute inset-0 rounded-full bg-primary"
                    transition={{ type: 'spring', bounce: 0.15, duration: 0.4 }}
                  />
                )}
                <span className="relative z-10">{label}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>
    </header>
  )
}
```

**Step 2: Commit**

```
feat(frontend): show Sign in button for guests, logout for users
```

---

### Task 9: Frontend — Remove legacy login step from Login page

**Files:**
- Modify: `frontend/src/pages/Login.tsx`

**Step 1: Clean up Login.tsx**

- Remove `Step` type's `'legacy'` option: `type Step = 'email' | 'code'`
- Remove `password`, `showPassword` state
- Remove `handleLegacyLogin` function
- Remove `IconEye`, `IconEyeOff` imports
- Remove the entire `{step === 'legacy' && ...}` JSX block
- Remove the "password access" button from the email step
- Remove `loginLegacy` from `useAuth()` destructuring

**Step 2: Remove i18n keys for legacy login**

Search for `login.passwordAccess`, `login.sharedPassword`, `login.password`, `login.signingIn`, `login.signIn`, `login.emailAccess`, `login.authError` in i18n files and remove them.

**Step 3: Build to verify**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors

**Step 4: Commit**

```
refactor(frontend): remove legacy password login from Login page

Only OTP and passkey login methods remain.
```

---

### Task 10: Nginx — Commit the scanner-blocking config

**Files:**
- Already modified: `frontend/nginx.conf`

**Step 1: Verify the nginx config is valid**

Review that the regex block is before the SPA fallback in `frontend/nginx.conf`.

**Step 2: Build frontend Docker image to test**

Run: `cd frontend && docker build -t ainews-frontend-test -f Dockerfile .`
Expected: Build succeeds

**Step 3: Commit**

```
fix(nginx): block WordPress/phpMyAdmin scanner bots with 444

Returns connection-drop for common vulnerability scanner paths
(wp-admin, wp-login, xmlrpc.php, phpmyadmin, .env, .git, etc.)
```

---

### Task 11: Integration test — Full guest flow

**Files:**
- Test: `tests/unit/test_auth.py` (verify end-to-end guest flow)

**Step 1: Write integration-style test**

```python
class TestGuestFlow:
    """End-to-end: get guest token, use it on public endpoint, fail on chat."""

    async def test_full_guest_flow(self, api_client: AsyncClient):
        from unittest.mock import AsyncMock, MagicMock
        from src.core.database import get_session

        # 1. Get guest token
        resp = await api_client.post("/api/auth/guest")
        assert resp.status_code == 200
        token = resp.json()["access_token"]

        # 2. Access public endpoint
        async def _mock_session():
            mock_result = MagicMock()
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = []
            mock_result.scalars.return_value = mock_scalars
            mock_result.scalar_one.return_value = 0
            session = AsyncMock()
            session.execute = AsyncMock(return_value=mock_result)
            yield session

        app.dependency_overrides[get_session] = _mock_session
        try:
            resp = await api_client.get(
                "/api/items", headers={"Authorization": f"Bearer {token}"}
            )
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.pop(get_session, None)

        # 3. Chat should be blocked
        resp = await api_client.post(
            "/api/chat",
            json={"question": "test question"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401
```

**Step 2: Run full test suite**

Run: `pytest tests/unit/test_auth.py -v`
Expected: ALL PASS

**Step 3: Run linting**

Run: `ruff check . && ruff format --check .`
Expected: Clean

**Step 4: Commit**

```
test: add guest flow integration test
```

---

### Task 12: Update backlog and docs

**Files:**
- Modify: `docs/plans/ideas-backlog.md`
- Modify: `AGENTS.md` (if auth section needs updating)

**Step 1: Update backlog**

Mark as done:
- Remove legacy auth
- Add public access with guest tokens

Move to Done section.

**Step 2: Final commit**

```
docs: update backlog — public access and legacy auth removal complete
```
