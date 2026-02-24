const STORAGE_KEYS = {
  accessToken: 'auth_access_token',
  refreshToken: 'auth_refresh_token',
  expiresAt: 'auth_expires_at',
} as const

export interface AuthTokens {
  access_token: string
  refresh_token: string
  expires_in: number
  token_type: string
}

export function storeTokens(tokens: AuthTokens): void {
  const expiresAt = Date.now() + tokens.expires_in * 1000
  localStorage.setItem(STORAGE_KEYS.accessToken, tokens.access_token)
  localStorage.setItem(STORAGE_KEYS.refreshToken, tokens.refresh_token)
  localStorage.setItem(STORAGE_KEYS.expiresAt, String(expiresAt))
}

export function getAccessToken(): string | null {
  return localStorage.getItem(STORAGE_KEYS.accessToken)
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(STORAGE_KEYS.refreshToken)
}

export function isTokenExpired(): boolean {
  const expiresAt = localStorage.getItem(STORAGE_KEYS.expiresAt)
  if (!expiresAt) return true
  return Date.now() >= Number(expiresAt)
}

export function clearTokens(): void {
  localStorage.removeItem(STORAGE_KEYS.accessToken)
  localStorage.removeItem(STORAGE_KEYS.refreshToken)
  localStorage.removeItem(STORAGE_KEYS.expiresAt)
}

export function hasTokens(): boolean {
  return getAccessToken() !== null && getRefreshToken() !== null
}
