const STORAGE_KEYS = {
  accessToken: 'auth_access_token',
  expiresAt: 'auth_expires_at',
} as const

export function storeGuestToken(accessToken: string, expiresIn: number): void {
  const expiresAt = Date.now() + expiresIn * 1000
  localStorage.setItem(STORAGE_KEYS.accessToken, accessToken)
  localStorage.setItem(STORAGE_KEYS.expiresAt, String(expiresAt))
}

export function getAccessToken(): string | null {
  return localStorage.getItem(STORAGE_KEYS.accessToken)
}

export function isTokenExpired(): boolean {
  const expiresAt = localStorage.getItem(STORAGE_KEYS.expiresAt)
  if (!expiresAt) return true
  return Date.now() >= Number(expiresAt)
}

export function clearTokens(): void {
  localStorage.removeItem(STORAGE_KEYS.accessToken)
  localStorage.removeItem(STORAGE_KEYS.expiresAt)
}
