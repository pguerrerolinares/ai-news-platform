# Login Page i18n + Remaining Spanish Text Cleanup

**Date**: 2026-02-28
**Status**: Approved

## Goal

Complete the frontend language standardization by translating the remaining Spanish text in `Login.tsx` and `featured-card.tsx` to English using the existing i18n infrastructure.

## Context

The language standardization effort (see `2026-02-28-language-standardization-design.md`) converted most of the platform to English. Two files were missed:
- `Login.tsx`: ~16 hardcoded Spanish strings
- `featured-card.tsx`: 1 Spanish string (`"por"`)

## Scope

### 1. Add strings to `en.json`

Add `login` and `featured` sections:

```json
{
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

### 2. Update `Login.tsx`

- Import `useTranslation` from `react-i18next`
- Replace all hardcoded Spanish strings with `t('login.xxx')` calls

### 3. Update `featured-card.tsx`

- Import `useTranslation` from `react-i18next`
- Replace `por` with `t('featured.by')`

### 4. Update `CLAUDE.md`

- Remove "frontend labels" from the Spanish user-facing text list
- Policy becomes: code in English, user-facing Telegram messages and LLM summaries in Spanish (if needed), frontend in English

## What Does NOT Change

- i18n infrastructure (already set up)
- Other pages (already use `useTranslation()`)
- Backend strings
- Any component structure or logic
