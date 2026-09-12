import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// api.ts delegates token storage to auth.ts (localStorage-backed, not available
// in this test's node environment); mock it with a tiny in-memory equivalent
// so we can exercise api.ts's own ensureToken() single-flight logic.
vi.mock('./auth', () => {
  let token: string | null = null
  let expiresAt = 0
  return {
    getAccessToken: () => token,
    isTokenExpired: () => Date.now() >= expiresAt,
    storeGuestToken: (accessToken: string, expiresIn: number) => {
      token = accessToken
      expiresAt = Date.now() + expiresIn * 1000
    },
    clearTokens: () => {
      token = null
      expiresAt = 0
    },
  }
})

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('ensureToken single-flight (api.ts, guest-token race)', () => {
  beforeEach(() => {
    vi.resetModules()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('N concurrent apiGet calls request a guest token exactly once', async () => {
    const requestedUrls: string[] = []
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      requestedUrls.push(url)
      if (url.includes('/api/auth/guest')) {
        return jsonResponse({ access_token: 'guest-tok', expires_in: 3600 })
      }
      return jsonResponse([])
    })
    vi.stubGlobal('fetch', fetchMock)

    const { apiGet } = await import('./api')

    await Promise.all(
      Array.from({ length: 5 }, () => apiGet('/api/items/latest')),
    )

    const guestTokenCalls = requestedUrls.filter(u => u.includes('/api/auth/guest'))
    expect(guestTokenCalls).toHaveLength(1)
  })
})
