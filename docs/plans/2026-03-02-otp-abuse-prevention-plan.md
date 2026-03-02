# OTP Abuse Prevention Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Protect the OTP email system from abuse by adding per-email rate limiting, a global daily cap, and a passkey promotion banner.

**Architecture:** Three layers of backend protection in `request_otp()` (per-email 5/hour, global 50/day cap via DB queries) plus a frontend banner to promote passkeys and reduce OTP dependency. All checks happen before `send_otp_email()` to avoid wasting Resend API calls.

**Tech Stack:** Python/FastAPI/SQLAlchemy (backend), React/Shadcn UI (frontend), i18next (translations)

**Design doc:** `docs/plans/2026-03-02-otp-abuse-prevention-design.md`

---

### Task 1: Add `otp_daily_limit` to Settings

**Files:**
- Modify: `src/core/config.py:157-160` (add field after `otp_expire_minutes`)
- Test: `tests/unit/test_config.py`

**Step 1: Write the failing test**

In `tests/unit/test_config.py`, add:

```python
def test_otp_daily_limit_default():
    s = Settings(
        jwt_secret="x",
        shared_password="x",
        database_url="postgresql+asyncpg://x:x@localhost/x",
        database_url_sync="postgresql://x:x@localhost/x",
    )
    assert s.otp_daily_limit == 50


def test_otp_daily_limit_custom():
    s = Settings(
        jwt_secret="x",
        shared_password="x",
        database_url="postgresql+asyncpg://x:x@localhost/x",
        database_url_sync="postgresql://x:x@localhost/x",
        otp_daily_limit=80,
    )
    assert s.otp_daily_limit == 80
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_config.py::test_otp_daily_limit_default -v`
Expected: FAIL — `Settings` has no field `otp_daily_limit`

**Step 3: Write minimal implementation**

In `src/core/config.py`, add after line 160 (`otp_expire_minutes`):

```python
otp_daily_limit: int = 50
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_config.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/core/config.py tests/unit/test_config.py
git commit -m "feat: add otp_daily_limit setting (default 50)"
```

---

### Task 2: Add per-email rate limit (5/hour) to `request_otp`

**Files:**
- Modify: `src/api/routes/otp.py:33-55` (the `request_otp` function)
- Test: `tests/unit/test_otp_routes.py`

**Step 1: Write the failing test**

In `tests/unit/test_otp_routes.py`, add to class `TestOtpRequest`:

```python
async def test_request_otp_email_rate_limit(self, api_client: AsyncClient):
    """Returns 429 when email has 5+ OTPs in the last hour."""
    mock_session = AsyncMock()

    # First execute: email rate limit count returns 5
    # Second execute: daily cap count returns 0 (won't reach this)
    mock_count_result = MagicMock()
    mock_count_result.scalar_one.return_value = 5
    mock_session.execute = AsyncMock(return_value=mock_count_result)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with (
        patch("src.api.routes.otp.get_async_session", mock_get_session),
        patch("src.api.routes.otp.send_otp_email", new_callable=AsyncMock) as mock_send,
    ):
        resp = await api_client.post(
            "/api/auth/otp/request",
            json={"email": "spam@example.com"},
        )

    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "OTP_EMAIL_RATE_LIMITED"
    mock_send.assert_not_called()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_otp_routes.py::TestOtpRequest::test_request_otp_email_rate_limit -v`
Expected: FAIL — no rate limit logic exists, returns 200

**Step 3: Write minimal implementation**

Replace the `request_otp` function in `src/api/routes/otp.py` with:

```python
OTP_EMAIL_RATE_LIMIT = 5  # max OTPs per email per hour


@router.post("/otp/request", response_model=OtpRequestResponse)
@limiter.limit("3/minute")
async def request_otp(request: Request, body: OtpRequestBody) -> OtpRequestResponse:
    """Send a 6-digit OTP code to the given email."""
    settings = get_settings()
    email = body.email.lower().strip()

    async with get_async_session() as session:
        # Per-email rate limit: max 5 per hour
        one_hour_ago = datetime.now(tz=UTC) - timedelta(hours=1)
        result = await session.execute(
            select(func.count())
            .select_from(OtpCode)
            .where(OtpCode.email == email, OtpCode.created_at > one_hour_ago)
        )
        email_count = result.scalar_one()
        if email_count >= OTP_EMAIL_RATE_LIMIT:
            logger.warning("otp_email_rate_limited", email=email, count=email_count)
            raise APIError(429, "OTP_EMAIL_RATE_LIMITED", "Too many attempts. Try again later.")

        # Invalidate old unused codes for this email
        await session.execute(
            update(OtpCode)
            .where(OtpCode.email == email, OtpCode.used == False)  # noqa: E712
            .values(used=True)
        )

        code = generate_otp_code()
        expires_at = datetime.now(tz=UTC) + timedelta(minutes=settings.otp_expire_minutes)

        # Store new code
        session.add(OtpCode(email=email, code=code, expires_at=expires_at))
        await session.commit()

    await send_otp_email(email, code)
    return OtpRequestResponse(message="Code sent")
```

Add necessary imports at the top of `src/api/routes/otp.py`:

```python
from sqlalchemy import func, select, update
```

Note: `select` and `update` are already imported. Add `func` to the existing import.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_otp_routes.py::TestOtpRequest -v`
Expected: ALL PASS (including existing tests — they mock execute to return MagicMock which will need adjustment)

Note: Existing tests mock `session.execute` as a single call. With the new rate-limit query, `execute` is now called multiple times. The existing tests' mock returns a MagicMock whose `.scalar_one()` returns another MagicMock (truthy but < 5 won't work with `>=`). **You may need to adjust the existing test mocks** to handle multiple execute calls using `side_effect`:

```python
# In existing tests, replace:
mock_session.execute = AsyncMock(return_value=MagicMock())
# With:
mock_count_result = MagicMock()
mock_count_result.scalar_one.return_value = 0  # email rate limit: 0 recent
mock_daily_result = MagicMock()
mock_daily_result.scalar_one.return_value = 0  # daily cap: 0 today
mock_update_result = MagicMock()
mock_session.execute = AsyncMock(
    side_effect=[mock_count_result, mock_daily_result, mock_update_result]
)
```

(The daily cap query will be added in Task 3, but prepare the mock now to avoid touching it again.)

**Step 5: Commit**

```bash
git add src/api/routes/otp.py tests/unit/test_otp_routes.py
git commit -m "feat: add per-email OTP rate limit (5/hour)"
```

---

### Task 3: Add global daily cap to `request_otp`

**Files:**
- Modify: `src/api/routes/otp.py` (add daily cap check after email rate limit)
- Test: `tests/unit/test_otp_routes.py`

**Step 1: Write the failing test**

In `tests/unit/test_otp_routes.py`, add to class `TestOtpRequest`:

```python
async def test_request_otp_daily_cap(self, api_client: AsyncClient):
    """Returns 503 when global daily OTP cap is reached."""
    mock_session = AsyncMock()

    # First execute: email rate limit count returns 0 (OK)
    mock_email_count = MagicMock()
    mock_email_count.scalar_one.return_value = 0
    # Second execute: daily cap count returns 50 (at limit)
    mock_daily_count = MagicMock()
    mock_daily_count.scalar_one.return_value = 50
    mock_session.execute = AsyncMock(
        side_effect=[mock_email_count, mock_daily_count]
    )
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with (
        patch("src.api.routes.otp.get_async_session", mock_get_session),
        patch("src.api.routes.otp.send_otp_email", new_callable=AsyncMock) as mock_send,
    ):
        resp = await api_client.post(
            "/api/auth/otp/request",
            json={"email": "legit@example.com"},
        )

    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "OTP_DAILY_CAP_REACHED"
    mock_send.assert_not_called()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_otp_routes.py::TestOtpRequest::test_request_otp_daily_cap -v`
Expected: FAIL — no daily cap logic, returns 200

**Step 3: Write minimal implementation**

In the `request_otp` function in `src/api/routes/otp.py`, add after the per-email rate limit check and before the invalidation of old codes:

```python
        # Global daily cap
        today_start = datetime.now(tz=UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        daily_result = await session.execute(
            select(func.count())
            .select_from(OtpCode)
            .where(OtpCode.created_at >= today_start)
        )
        daily_count = daily_result.scalar_one()
        if daily_count >= settings.otp_daily_limit:
            logger.warning("otp_daily_cap_reached", daily_count=daily_count,
                           limit=settings.otp_daily_limit)
            raise APIError(503, "OTP_DAILY_CAP_REACHED",
                           "Service temporarily unavailable. Try again later.")
```

Also add 503 to the error handler in `src/api/errors.py` `code_map` if not present (check first — it might already fall through to `INTERNAL_ERROR`). Actually, since we use `APIError` directly with the code, this is handled already by `api_error_handler`.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_otp_routes.py::TestOtpRequest -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/api/routes/otp.py tests/unit/test_otp_routes.py
git commit -m "feat: add global daily OTP cap (configurable, default 50)"
```

---

### Task 4: Add i18n keys for passkey prompt banner

**Files:**
- Modify: `frontend/src/locales/en.json`

**Step 1: Add translation keys**

Add a new `"passkeyPrompt"` section to `frontend/src/locales/en.json`:

```json
"passkeyPrompt": {
  "title": "Faster sign-in available",
  "description": "Register a passkey to sign in with fingerprint or Face ID — no more email codes.",
  "register": "Set up passkey",
  "dismiss": "Not now"
}
```

**Step 2: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds (no TS errors from new keys)

**Step 3: Commit**

```bash
git add frontend/src/locales/en.json
git commit -m "feat: add i18n keys for passkey promotion banner"
```

---

### Task 5: Create PasskeyPrompt component

**Files:**
- Create: `frontend/src/components/passkey-prompt.tsx`
- Test: Manual verification

**Step 1: Create the component**

Create `frontend/src/components/passkey-prompt.tsx`:

```tsx
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router'
import { useTranslation } from 'react-i18next'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { apiGet } from '@/lib/api'

const DISMISSED_KEY = 'passkey-prompt-dismissed'

export function PasskeyPrompt() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    if (sessionStorage.getItem(DISMISSED_KEY)) return

    apiGet<{ id: string }[]>('/api/auth/webauthn/credentials')
      .then(({ data }) => {
        if (data.length === 0) setVisible(true)
      })
      .catch(() => {
        // Silently ignore — don't show banner if check fails
      })
  }, [])

  if (!visible) return null

  function handleDismiss() {
    sessionStorage.setItem(DISMISSED_KEY, '1')
    setVisible(false)
  }

  return (
    <Card className="border-primary/20 bg-primary/5">
      <CardContent className="flex items-center justify-between gap-4 py-3">
        <div className="min-w-0">
          <p className="text-sm font-medium">{t('passkeyPrompt.title')}</p>
          <p className="text-xs text-muted-foreground">{t('passkeyPrompt.description')}</p>
        </div>
        <div className="flex shrink-0 gap-2">
          <Button size="sm" variant="ghost" onClick={handleDismiss}>
            {t('passkeyPrompt.dismiss')}
          </Button>
          <Button size="sm" onClick={() => navigate('/settings')}>
            {t('passkeyPrompt.register')}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
```

**Step 2: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add frontend/src/components/passkey-prompt.tsx
git commit -m "feat: add PasskeyPrompt banner component"
```

---

### Task 6: Add PasskeyPrompt to Dashboard page

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx`

**Step 1: Add the banner to Dashboard**

At the top of `frontend/src/pages/Dashboard.tsx`, add import:

```tsx
import { PasskeyPrompt } from '@/components/passkey-prompt'
```

Inside the JSX, add `<PasskeyPrompt />` right after the opening `<div>` and before the header:

```tsx
return (
    <div className="mx-auto max-w-2xl space-y-6 px-4">
      <PasskeyPrompt />
      <div className="flex items-center justify-between">
      ...
```

**Step 2: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add frontend/src/pages/Dashboard.tsx
git commit -m "feat: show passkey promotion banner on Dashboard"
```

---

### Task 7: Final verification and quality gate

**Step 1: Run backend lint + type check + tests**

Run: `ruff check . && ruff format --check . && pyright . && pytest tests/ -x --timeout=30`
Expected: ALL PASS

**Step 2: Run frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 3: Final commit (if any fixes needed)**

Fix any lint/type issues, then commit fixes.

**Step 4: Update AGENTS.md if needed**

If the file map or architecture section needs updating to reflect the new rate limiting logic, update it.
