# Login i18n + Spanish Text Cleanup — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Translate remaining Spanish text in Login.tsx and featured-card.tsx to English using the existing i18n system.

**Architecture:** Add `login` and `featured` keys to existing `en.json`, then replace hardcoded Spanish strings with `t()` calls — same pattern used by Dashboard, Trending, Search, and Chat pages.

**Tech Stack:** React 19, react-i18next (already installed), TypeScript

---

### Task 1: Add login and featured strings to en.json

**Files:**
- Modify: `frontend/src/locales/en.json`

**Step 1: Add the new translation keys**

Add `login` and `featured` sections to the existing JSON:

```json
{
  "nav": { ... },
  "dashboard": { ... },
  "trending": { ... },
  "search": { ... },
  "chat": { ... },
  "login": {
    "description": "Enter your email to receive a code",
    "codeSent": "Code sent to {{email}}",
    "sharedPassword": "Shared password access",
    "sendingCode": "Sending...",
    "sendCode": "Send code",
    "passwordAccess": "Password access",
    "verifying": "Verifying...",
    "verify": "Verify",
    "changeEmail": "Change email",
    "resendCode": "Resend code",
    "password": "Password",
    "otpLabel": "OTP Code",
    "signingIn": "Signing in...",
    "signIn": "Sign in",
    "emailAccess": "Email access",
    "errorSendingCode": "Error sending code",
    "invalidCode": "Invalid or expired code",
    "authError": "Authentication error",
    "errorResending": "Error resending code"
  },
  "featured": {
    "by": "by"
  }
}
```

**Step 2: Verify JSON is valid**

Run: `cd frontend && node -e "require('./src/locales/en.json'); console.log('OK')"`
Expected: `OK`

---

### Task 2: Translate Login.tsx to use i18n

**Files:**
- Modify: `frontend/src/pages/Login.tsx`

**Step 1: Add useTranslation import and hook**

Add to imports:
```tsx
import { useTranslation } from 'react-i18next'
```

Add inside `Login()` component, after existing hooks:
```tsx
const { t } = useTranslation()
```

**Step 2: Replace all Spanish strings**

Replace each hardcoded Spanish string with `t()` call:

| Line | Spanish | Replacement |
|------|---------|-------------|
| 49 | `'Error al enviar el codigo'` | `t('login.errorSendingCode')` |
| 64 | `'Codigo invalido o expirado'` | `t('login.invalidCode')` |
| 79 | `'Error de autenticacion'` | `t('login.authError')` |
| 91 | `'Introduce tu email para recibir un codigo'` | `t('login.description')` |
| 92 | `` `Codigo enviado a ${email}` `` | `t('login.codeSent', { email })` |
| 93 | `'Acceso con contrasena compartida'` | `t('login.sharedPassword')` |
| 113 | `'Enviando...'` / `'Enviar codigo'` | `t('login.sendingCode')` / `t('login.sendCode')` |
| 120 | `'Acceso con contrasena'` | `t('login.passwordAccess')` |
| 137 | `'Codigo OTP'` | `t('login.otpLabel')` |
| 141 | `'Verificando...'` / `'Verificar'` | `t('login.verifying')` / `t('login.verify')` |
| 149 | `'Cambiar email'` | `t('login.changeEmail')` |
| 162 | `'Error al reenviar'` | `t('login.errorResending')` |
| 168 | `'Reenviar codigo'` | `t('login.resendCode')` |
| 178 | `'Contrasena'` (placeholder) | `t('login.password')` |
| 182 | `'Contrasena'` (aria-label) | `t('login.password')` |
| 186 | `'Entrando...'` / `'Entrar'` | `t('login.signingIn')` / `t('login.signIn')` |
| 193 | `'Acceso con email'` | `t('login.emailAccess')` |

**Step 3: Verify build**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

---

### Task 3: Translate featured-card.tsx to use i18n

**Files:**
- Modify: `frontend/src/components/featured-card.tsx`

**Step 1: Add useTranslation import and hook**

Add to imports:
```tsx
import { useTranslation } from 'react-i18next'
```

Add inside `FeaturedCard()` component:
```tsx
const { t } = useTranslation()
```

**Step 2: Replace "por" with t() call**

Line 68: Change `por {item.author}` to `{t('featured.by')} {item.author}`

**Step 3: Verify build**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

---

### Task 4: Update CLAUDE.md language policy

**Files:**
- Modify: `CLAUDE.md` (project root)

**Step 1: Update the Language & Style section**

Change:
```
- **User-facing text** (summaries, Telegram messages, frontend labels): Spanish
```

To:
```
- **User-facing text** (Telegram messages): Spanish
- **Frontend text**: English (all UI labels, buttons, errors)
```

---

### Task 5: Build verification and commit

**Step 1: Full frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors

**Step 2: Grep for remaining Spanish**

Run: `grep -rn "Enviar\|Verificar\|Contrasena\|Codigo\|Acceso\|Entrando\|Reenviar\|Cambiar email" frontend/src/`
Expected: No matches

**Step 3: Commit**

```bash
git add frontend/src/locales/en.json frontend/src/pages/Login.tsx frontend/src/components/featured-card.tsx CLAUDE.md
git commit -m "fix: translate remaining Spanish text in Login and featured-card to English

Add login and featured sections to en.json, replace hardcoded
Spanish strings with t() calls, update CLAUDE.md language policy."
```
