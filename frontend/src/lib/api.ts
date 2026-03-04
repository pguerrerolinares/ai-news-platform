import { getAccessToken, getRefreshToken, storeTokens, clearTokens, hasTokens, isTokenExpired, isGuestToken, type AuthTokens } from './auth'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

class ApiError extends Error {
  status: number
  code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

async function refreshAccessToken(): Promise<boolean> {
  const refreshToken = getRefreshToken()
  if (!refreshToken) return false

  try {
    const res = await fetch(`${BASE_URL}/api/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
    if (!res.ok) return false
    const tokens: AuthTokens = await res.json()
    storeTokens(tokens)
    return true
  } catch {
    return false
  }
}

async function ensureToken(): Promise<void> {
  if (getAccessToken() && !isTokenExpired()) return
  if (!getRefreshToken()) {
    try {
      const res = await fetch(`${BASE_URL}/api/auth/guest`, { method: 'POST' })
      if (res.ok) {
        const data = await res.json()
        localStorage.setItem('auth_access_token', data.access_token)
        localStorage.setItem('auth_expires_at', String(Date.now() + data.expires_in * 1000))
      }
    } catch {
      // Guest token fetch failed — continue without token
    }
  }
}

function authHeaders(): Record<string, string> {
  const token = getAccessToken()
  if (!token) return {}
  return { Authorization: `Bearer ${token}` }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<{ data: T; totalCount: number | null; response: Response }> {
  await ensureToken()
  const url = `${BASE_URL}${path}`
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
      ...options.headers,
    },
  })

  if (res.status === 401 && retry) {
    const refreshed = await refreshAccessToken()
    if (refreshed) {
      return request<T>(path, options, false)
    }
    if (isGuestToken() || !hasTokens()) {
      clearTokens()
      await ensureToken()
      return request<T>(path, options, false)
    }
    clearTokens()
    window.location.replace('/login')
    throw new ApiError(401, 'UNAUTHORIZED', 'Session expired')
  }

  if (!res.ok) {
    let code = 'UNKNOWN_ERROR'
    let message = `Error ${res.status}`
    try {
      const body = await res.json()
      if (body.error) {
        code = body.error.code ?? code
        message = body.error.message ?? message
      }
    } catch {
      // ignore parse errors
    }
    throw new ApiError(res.status, code, message)
  }

  const totalCountHeader = res.headers.get('X-Total-Count')
  const totalCount = totalCountHeader ? Number(totalCountHeader) : null
  const data: T = await res.json()

  return { data, totalCount, response: res }
}

export async function apiGet<T>(
  path: string,
  params?: Record<string, string>,
  signal?: AbortSignal,
): Promise<{ data: T; totalCount: number | null }> {
  const query = params ? '?' + new URLSearchParams(params).toString() : ''
  const { data, totalCount } = await request<T>(`${path}${query}`, { signal })
  return { data, totalCount }
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const { data } = await request<T>(path, {
    method: 'POST',
    body: JSON.stringify(body),
  })
  return data
}

export async function apiDelete(path: string): Promise<void> {
  await request(path, { method: 'DELETE' })
}

export async function apiStream(
  path: string,
  body: unknown,
  signal?: AbortSignal,
): Promise<Response> {
  await ensureToken()
  const url = `${BASE_URL}${path}`
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
    body: JSON.stringify(body),
    signal,
  })

  if (res.status === 401) {
    const refreshed = await refreshAccessToken()
    if (refreshed) {
      return fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders(),
        },
        body: JSON.stringify(body),
        signal,
      })
    }
    if (isGuestToken()) {
      throw new ApiError(401, 'UNAUTHORIZED', 'Chat requires authentication')
    }
    clearTokens()
    window.location.replace('/login')
    throw new ApiError(401, 'UNAUTHORIZED', 'Session expired')
  }

  if (!res.ok) {
    let message = `Error ${res.status}`
    try {
      const errorBody = await res.json()
      message = errorBody.error?.message ?? message
    } catch {
      // ignore
    }
    throw new ApiError(res.status, 'STREAM_ERROR', message)
  }

  return res
}

export { ApiError, BASE_URL }
