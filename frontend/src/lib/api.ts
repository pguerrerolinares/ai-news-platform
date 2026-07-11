import { getAccessToken, storeGuestToken, clearTokens, isTokenExpired } from './auth'

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

let inflightGuestToken: Promise<void> | null = null

async function fetchGuestToken(): Promise<void> {
  const res = await fetch(`${BASE_URL}/api/auth/guest`, { method: 'POST' })
  if (!res.ok) {
    throw new ApiError(res.status, 'GUEST_TOKEN_ERROR', 'Failed to obtain guest token')
  }
  const data = await res.json()
  storeGuestToken(data.access_token, data.expires_in)
}

async function ensureToken(): Promise<void> {
  if (getAccessToken() && !isTokenExpired()) return

  if (inflightGuestToken) return inflightGuestToken
  inflightGuestToken = fetchGuestToken()
  try {
    await inflightGuestToken
  } finally {
    inflightGuestToken = null
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
    clearTokens()
    await ensureToken()
    return request<T>(path, options, false)
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

export { ApiError, BASE_URL }
