# Wire React Frontend to Real API — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace mock data in all 4 React pages with real API calls, add login page with JWT auth, connect chat to real SSE streaming.

**Architecture:** Thin fetch wrapper (`lib/api.ts`) handles JWT headers and auto-refresh. Auth state managed via React context (`hooks/use-auth.tsx`). Pages use `useEffect` + `useState` for data fetching. Chat uses raw `fetch()` + `ReadableStream` for SSE parsing. No new dependencies — React 19 fetch + native APIs only.

**Tech Stack:** React 19, TypeScript, Vite 7, existing Shadcn UI components

---

### Task 1: Environment Config

**Files:**
- Create: `frontend/.env.example`
- Modify: `frontend/src/vite-env.d.ts`

**Step 1: Create .env.example**

Create `frontend/.env.example`:

```
VITE_API_URL=http://localhost:8000
```

**Step 2: Add type declaration for env var**

In `frontend/src/vite-env.d.ts`, add after the existing `/// <reference>` line:

```typescript
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
```

**Step 3: Verify build**

```bash
cd frontend && bun run build
```

Expected: Clean build, no errors.

**Step 4: Commit**

```bash
git add frontend/.env.example frontend/src/vite-env.d.ts
git commit -m "feat: env config for API base URL (VITE_API_URL)"
```

---

### Task 2: Auth Token Storage (`lib/auth.ts`)

**Files:**
- Create: `frontend/src/lib/auth.ts`

**Step 1: Create auth token storage module**

Create `frontend/src/lib/auth.ts`:

```typescript
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
```

**Step 2: Verify build**

```bash
cd frontend && bun run build
```

Expected: Clean build (unused module is fine, will be consumed in Task 3).

**Step 3: Commit**

```bash
git add frontend/src/lib/auth.ts
git commit -m "feat: auth token storage module (localStorage)"
```

---

### Task 3: API Client (`lib/api.ts`)

**Files:**
- Create: `frontend/src/lib/api.ts`

**Step 1: Create the API client**

Create `frontend/src/lib/api.ts`:

```typescript
import { getAccessToken, getRefreshToken, storeTokens, clearTokens, type AuthTokens } from './auth'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
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
    clearTokens()
    window.location.href = '/login'
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
): Promise<{ data: T; totalCount: number | null }> {
  const query = params ? '?' + new URLSearchParams(params).toString() : ''
  const { data, totalCount } = await request<T>(`${path}${query}`)
  return { data, totalCount }
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const { data } = await request<T>(path, {
    method: 'POST',
    body: JSON.stringify(body),
  })
  return data
}

export async function apiStream(path: string, body: unknown): Promise<Response> {
  const url = `${BASE_URL}${path}`
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
    body: JSON.stringify(body),
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
      })
    }
    clearTokens()
    window.location.href = '/login'
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
```

**Step 2: Verify build**

```bash
cd frontend && bun run build
```

Expected: Clean build.

**Step 3: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat: API client with JWT auth, auto-refresh, error handling"
```

---

### Task 4: Auth Context + Login Page

**Files:**
- Create: `frontend/src/hooks/use-auth.tsx`
- Create: `frontend/src/pages/Login.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/app-nav.tsx`

**Step 1: Create AuthProvider context**

Create `frontend/src/hooks/use-auth.tsx`:

```tsx
import { createContext, useContext, useState, useCallback, useEffect } from 'react'
import { Navigate, useLocation } from 'react-router'
import type { ReactNode } from 'react'
import { apiPost } from '@/lib/api'
import { storeTokens, clearTokens, hasTokens, isTokenExpired, type AuthTokens } from '@/lib/auth'

interface AuthContextValue {
  isAuthenticated: boolean
  login: (password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(() => hasTokens() && !isTokenExpired())

  useEffect(() => {
    const check = () => setIsAuthenticated(hasTokens() && !isTokenExpired())
    window.addEventListener('storage', check)
    return () => window.removeEventListener('storage', check)
  }, [])

  const login = useCallback(async (password: string) => {
    const tokens = await apiPost<AuthTokens>('/api/auth/token', { password })
    storeTokens(tokens)
    setIsAuthenticated(true)
  }, [])

  const logout = useCallback(() => {
    clearTokens()
    setIsAuthenticated(false)
  }, [])

  return (
    <AuthContext value={{ isAuthenticated, login, logout }}>
      {children}
    </AuthContext>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth()
  const location = useLocation()

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <>{children}</>
}
```

**Step 2: Create Login page**

Create `frontend/src/pages/Login.tsx`:

```tsx
import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/hooks/use-auth'

export default function Login() {
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname ?? '/'

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!password.trim()) return

    setError('')
    setLoading(true)
    try {
      await login(password)
      navigate(from, { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error de autenticacion')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-[calc(100vh-5rem)] items-center justify-center px-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl font-bold">AI News</CardTitle>
          <CardDescription>Introduce la contrasena para acceder</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              type="password"
              placeholder="Contrasena"
              value={password}
              onChange={e => setPassword(e.target.value)}
              disabled={loading}
              aria-label="Contrasena"
            />
            {error && (
              <p className="text-sm text-destructive">{error}</p>
            )}
            <Button type="submit" className="w-full" disabled={loading || !password.trim()}>
              {loading ? 'Entrando...' : 'Entrar'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
```

**Step 3: Update App.tsx with auth routes**

Replace `frontend/src/App.tsx`:

```tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router'
import { AuthProvider, RequireAuth } from '@/hooks/use-auth'
import { Layout } from '@/components/layout'
import Dashboard from '@/pages/Dashboard'
import Trending from '@/pages/Trending'
import Buscar from '@/pages/Buscar'
import Chat from '@/pages/Chat'
import Login from '@/pages/Login'

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="login" element={<Login />} />
          <Route element={<RequireAuth><Layout /></RequireAuth>}>
            <Route index element={<Dashboard />} />
            <Route path="trending" element={<Trending />} />
            <Route path="buscar" element={<Buscar />} />
            <Route path="chat" element={<Chat />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
```

**Step 4: Add logout button to nav**

In `frontend/src/components/app-nav.tsx`, add a logout button:

- Import `useAuth` from `@/hooks/use-auth`
- Import `IconLogout` from `@tabler/icons-react`
- After `<ThemeToggle />` in the desktop section, add:

```tsx
const { logout } = useAuth()
// ...
<div className="ml-auto flex items-center gap-1">
  <ThemeToggle />
  <Button variant="ghost" size="icon" onClick={logout} aria-label="Cerrar sesion">
    <IconLogout className="size-4" />
  </Button>
</div>
```

Same for the mobile section.

**Step 5: Verify build**

```bash
cd frontend && bun run build
```

Expected: Clean build.

**Step 6: Commit**

```bash
git add frontend/src/hooks/use-auth.tsx frontend/src/pages/Login.tsx frontend/src/App.tsx frontend/src/components/app-nav.tsx
git commit -m "feat: login page, auth context, protected routes, logout button"
```

---

### Task 5: Wire Dashboard to API

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx`

**Step 1: Replace mock data with real API**

Replace `frontend/src/pages/Dashboard.tsx` — key changes:

- Remove `MOCK_ITEMS`, `MOCK_TOPICS` imports
- Add imports: `useEffect`, `useState`, `apiGet` from `@/lib/api`
- Add `TOPICS` constant (same 7 topics from `TOPIC_LABELS` keys)
- Fetch data with `useEffect` calling `apiGet<NewsItem[]>('/api/items/today', { limit: '50' })`
- Add `loading` and `error` states
- Show `Skeleton` or spinner while loading
- Show error with retry button on failure
- Topic filter remains client-side on fetched data
- Featured card = highest scored item from fetched data

```tsx
import { useState, useMemo, useEffect, useCallback } from 'react'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { TOPIC_LABELS } from '@/lib/constants'
import { NewsCard } from '@/components/news-card'
import { FeaturedCard } from '@/components/featured-card'
import { AnimatedCardGrid, AnimatedCardItem } from '@/components/animated-card-grid'
import { Button } from '@/components/ui/button'
import { apiGet } from '@/lib/api'
import type { NewsItem } from '@/lib/types'
import { motion } from 'motion/react'
import { useReducedMotion } from '@/hooks/use-reduced-motion'
import { IconRefresh } from '@tabler/icons-react'

const TOPICS = Object.keys(TOPIC_LABELS)

export default function Dashboard() {
  const [items, setItems] = useState<NewsItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [activeTopic, setActiveTopic] = useState<string>('all')
  const reduced = useReducedMotion()

  const fetchItems = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const { data } = await apiGet<NewsItem[]>('/api/items/today', { limit: '50' })
      setItems(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al cargar noticias')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchItems() }, [fetchItems])

  const featured = useMemo(
    () => items.length > 0 ? [...items].sort((a, b) => (b.score ?? 0) - (a.score ?? 0))[0] : null,
    [items],
  )

  const filtered = useMemo(() => {
    const rest = featured ? items.filter(i => i.id !== featured.id) : items
    return activeTopic !== 'all' ? rest.filter(i => i.topic === activeTopic) : rest
  }, [items, activeTopic, featured])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <p className="text-muted-foreground">Cargando noticias...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center gap-4 py-24">
        <p className="text-destructive">{error}</p>
        <Button variant="outline" onClick={fetchItems}>
          <IconRefresh className="mr-2 size-4" /> Reintentar
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Latest</h2>
          <p className="text-sm text-muted-foreground">
            {items.length} noticias de {items.filter(i => i.trending).length} trending
          </p>
        </div>
        <Select value={activeTopic} onValueChange={setActiveTopic}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Filtrar por topic" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos los topics</SelectItem>
            {TOPICS.map(topic => (
              <SelectItem key={topic} value={topic}>
                {TOPIC_LABELS[topic] ?? topic}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {activeTopic === 'all' && featured && (
        <motion.div
          initial={reduced ? false : { opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: 'easeOut' }}
        >
          <FeaturedCard item={featured} />
        </motion.div>
      )}

      <AnimatedCardGrid className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" animationKey={activeTopic}>
        {filtered.map(item => (
          <AnimatedCardItem key={item.id}>
            <NewsCard item={item} />
          </AnimatedCardItem>
        ))}
      </AnimatedCardGrid>

      {filtered.length === 0 && (
        <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
          <p>No hay noticias para este topic</p>
        </div>
      )}
    </div>
  )
}
```

**Step 2: Verify build**

```bash
cd frontend && bun run build
```

Expected: Clean build.

**Step 3: Commit**

```bash
git add frontend/src/pages/Dashboard.tsx
git commit -m "feat: wire Dashboard to real API (GET /api/items/today)"
```

---

### Task 6: Wire Trending to API

**Files:**
- Modify: `frontend/src/pages/Trending.tsx`

**Step 1: Replace mock data with real API**

Replace `frontend/src/pages/Trending.tsx`:

```tsx
import { useState, useEffect, useCallback } from 'react'
import { NewsCard } from '@/components/news-card'
import { AnimatedCardGrid, AnimatedCardItem } from '@/components/animated-card-grid'
import { Button } from '@/components/ui/button'
import { apiGet } from '@/lib/api'
import type { NewsItem } from '@/lib/types'
import { IconRefresh } from '@tabler/icons-react'

export default function Trending() {
  const [trendingItems, setTrendingItems] = useState<NewsItem[]>([])
  const [topScored, setTopScored] = useState<NewsItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [trending, top] = await Promise.all([
        apiGet<NewsItem[]>('/api/items/trending', { limit: '20' }),
        apiGet<NewsItem[]>('/api/items/top', { limit: '20' }),
      ])
      setTrendingItems(trending.data)
      setTopScored(top.data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al cargar datos')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchData() }, [fetchData])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <p className="text-muted-foreground">Cargando trending...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center gap-4 py-24">
        <p className="text-destructive">{error}</p>
        <Button variant="outline" onClick={fetchData}>
          <IconRefresh className="mr-2 size-4" /> Reintentar
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <section className="space-y-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">En movimiento</h2>
          <p className="text-sm text-muted-foreground">
            {trendingItems.length} noticias generando traccion ahora
          </p>
        </div>
        <AnimatedCardGrid className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" animationKey="trending">
          {trendingItems.map(item => (
            <AnimatedCardItem key={item.id}>
              <NewsCard item={item} />
            </AnimatedCardItem>
          ))}
        </AnimatedCardGrid>
        {trendingItems.length === 0 && (
          <p className="py-8 text-center text-muted-foreground">No hay noticias trending</p>
        )}
      </section>

      <section className="space-y-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Top puntuados</h2>
          <p className="text-sm text-muted-foreground">Las noticias con mayor puntuacion</p>
        </div>
        <AnimatedCardGrid className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" animationKey="top">
          {topScored.map(item => (
            <AnimatedCardItem key={item.id}>
              <NewsCard item={item} />
            </AnimatedCardItem>
          ))}
        </AnimatedCardGrid>
      </section>
    </div>
  )
}
```

**Step 2: Verify build**

```bash
cd frontend && bun run build
```

**Step 3: Commit**

```bash
git add frontend/src/pages/Trending.tsx
git commit -m "feat: wire Trending to real API (trending + top endpoints)"
```

---

### Task 7: Wire Buscar to API

**Files:**
- Modify: `frontend/src/pages/Buscar.tsx`

**Step 1: Replace mock filter with real API search**

Replace `frontend/src/pages/Buscar.tsx` — key changes:

- Remove `MOCK_ITEMS`, `MOCK_TOPICS` imports
- Import `apiGet` from `@/lib/api`
- Add `TOPICS` constant from `TOPIC_LABELS` keys
- Search is no longer client-side — calls `GET /api/search` on form submit
- Map `sortBy` values: `relevancia` → `relevance`, `fecha` → `date`, `score` → `score`
- Show `totalCount` from `X-Total-Count` header
- Debounce not needed — search triggers on Enter or button click (not on typing)

```tsx
import { useState, useCallback } from 'react'
import { Input } from '@/components/ui/input'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { TOPIC_LABELS } from '@/lib/constants'
import { NewsCard } from '@/components/news-card'
import { AnimatedCardGrid, AnimatedCardItem } from '@/components/animated-card-grid'
import { Button } from '@/components/ui/button'
import { apiGet } from '@/lib/api'
import type { NewsItem } from '@/lib/types'
import { IconSearch, IconRefresh } from '@tabler/icons-react'

const TOPICS = Object.keys(TOPIC_LABELS)
const SORT_MAP: Record<string, string> = {
  relevancia: 'relevance',
  fecha: 'date',
  score: 'score',
}

export default function Buscar() {
  const [query, setQuery] = useState('')
  const [topic, setTopic] = useState('all')
  const [sortBy, setSortBy] = useState('relevancia')
  const [results, setResults] = useState<NewsItem[]>([])
  const [totalCount, setTotalCount] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [searched, setSearched] = useState(false)

  const search = useCallback(async () => {
    if (!query.trim()) return
    setLoading(true)
    setError('')
    setSearched(true)
    try {
      const params: Record<string, string> = {
        q: query.trim(),
        sort_by: SORT_MAP[sortBy] ?? 'relevance',
        limit: '30',
      }
      if (topic !== 'all') params.topic = topic
      const { data, totalCount: count } = await apiGet<NewsItem[]>('/api/search', params)
      setResults(data)
      setTotalCount(count)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error en la busqueda')
      setResults([])
      setTotalCount(null)
    } finally {
      setLoading(false)
    }
  }, [query, topic, sortBy])

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter') search()
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Buscar</h2>
        <p className="text-sm text-muted-foreground">Busca entre las noticias de IA</p>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <IconSearch className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Buscar noticias..."
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            className="pl-9"
            aria-label="Buscar noticias"
          />
        </div>
        <Select value={topic} onValueChange={setTopic}>
          <SelectTrigger className="w-full sm:w-[160px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos</SelectItem>
            {TOPICS.map(t => (
              <SelectItem key={t} value={t}>{TOPIC_LABELS[t] ?? t}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={sortBy} onValueChange={setSortBy}>
          <SelectTrigger className="w-full sm:w-[160px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="relevancia">Relevancia</SelectItem>
            <SelectItem value="fecha">Fecha</SelectItem>
            <SelectItem value="score">Score</SelectItem>
          </SelectContent>
        </Select>
        <Button onClick={search} disabled={loading || !query.trim()}>
          <IconSearch className="mr-2 size-4" />
          Buscar
        </Button>
      </div>

      {error && (
        <div className="flex flex-col items-center gap-4 py-8">
          <p className="text-destructive">{error}</p>
          <Button variant="outline" onClick={search}>
            <IconRefresh className="mr-2 size-4" /> Reintentar
          </Button>
        </div>
      )}

      {searched && !loading && !error && (
        <p className="text-sm text-muted-foreground">
          {totalCount ?? results.length} resultado{(totalCount ?? results.length) !== 1 ? 's' : ''} para &quot;{query}&quot;
        </p>
      )}

      {loading && (
        <div className="flex items-center justify-center py-12">
          <p className="text-muted-foreground">Buscando...</p>
        </div>
      )}

      {!loading && results.length > 0 && (
        <AnimatedCardGrid className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" animationKey={`${query}-${topic}-${sortBy}`}>
          {results.map(item => (
            <AnimatedCardItem key={item.id}>
              <NewsCard item={item} />
            </AnimatedCardItem>
          ))}
        </AnimatedCardGrid>
      )}

      {searched && !loading && !error && results.length === 0 && (
        <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
          <p>No se encontraron resultados para &quot;{query}&quot;</p>
        </div>
      )}

      {!searched && (
        <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
          <IconSearch className="size-8" />
          <p>Escribe y pulsa Enter o Buscar</p>
        </div>
      )}
    </div>
  )
}
```

**Step 2: Verify build**

```bash
cd frontend && bun run build
```

**Step 3: Commit**

```bash
git add frontend/src/pages/Buscar.tsx
git commit -m "feat: wire Buscar to real API (GET /api/search with FTS)"
```

---

### Task 8: Wire Chat to SSE

**Files:**
- Modify: `frontend/src/pages/Chat.tsx`

**Step 1: Replace mock chat with real SSE streaming**

Replace `frontend/src/pages/Chat.tsx` — key changes:

- Remove all `MOCK_RESPONSES` and `getMockResponse()`
- Import `apiStream` from `@/lib/api`
- On send: call `apiStream('/api/chat', { question: text })` which returns a `Response`
- Parse SSE from `response.body` using `ReadableStream` + `TextDecoder`
- Handle events: `message` (type: token → append text, type: sources → store), `error`, `done`
- Keep all animations (message slide-in, typing dots, suggestion chips)

```tsx
import { useState, useRef, useEffect, useCallback } from 'react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { IconSend } from '@tabler/icons-react'
import { motion, AnimatePresence } from 'motion/react'
import { useReducedMotion } from '@/hooks/use-reduced-motion'
import { apiStream } from '@/lib/api'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
}

let nextId = 0
function msgId() {
  return `msg-${++nextId}`
}

const SUGGESTIONS = [
  'Que noticias hay de LLMs?',
  'Resume el trending de hoy',
  'Que herramientas nuevas hay?',
]

const chipContainer = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08 } },
}

const chipItem = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { duration: 0.2, ease: 'easeOut' as const } },
}

async function parseSSE(
  response: Response,
  onToken: (text: string) => void,
  onError: (message: string) => void,
  onDone: () => void,
) {
  const reader = response.body?.getReader()
  if (!reader) { onError('No response body'); return }

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''

    let currentEvent = ''
    for (const line of lines) {
      if (line.startsWith('event: ')) {
        currentEvent = line.slice(7).trim()
      } else if (line.startsWith('data: ')) {
        const data = line.slice(6)
        try {
          const parsed = JSON.parse(data)
          if (currentEvent === 'message') {
            if (parsed.type === 'token' && parsed.content) {
              onToken(parsed.content)
            }
          } else if (currentEvent === 'error') {
            onError(parsed.error?.message ?? 'Error del servidor')
          } else if (currentEvent === 'done') {
            onDone()
          }
        } catch {
          // ignore malformed JSON
        }
        currentEvent = ''
      }
    }
  }
  onDone()
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const reduced = useReducedMotion()

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isStreaming])

  const send = useCallback(async (text: string) => {
    if (!text.trim() || isStreaming) return
    const userMsg: Message = { id: msgId(), role: 'user', content: text.trim() }
    const assistantId = msgId()
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setIsStreaming(true)

    // Add empty assistant message that will be filled by streaming
    setMessages(prev => [...prev, { id: assistantId, role: 'assistant', content: '' }])

    try {
      const response = await apiStream('/api/chat', { question: text.trim() })
      await parseSSE(
        response,
        (token) => {
          setMessages(prev =>
            prev.map(m => m.id === assistantId ? { ...m, content: m.content + token } : m)
          )
        },
        (errorMsg) => {
          setMessages(prev =>
            prev.map(m => m.id === assistantId ? { ...m, content: `Error: ${errorMsg}` } : m)
          )
        },
        () => {
          setIsStreaming(false)
        },
      )
    } catch (err) {
      setMessages(prev =>
        prev.map(m => m.id === assistantId
          ? { ...m, content: `Error: ${err instanceof Error ? err.message : 'No se pudo conectar'}` }
          : m
        )
      )
      setIsStreaming(false)
    }
  }, [isStreaming])

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send(input)
    }
  }

  return (
    <div className="flex h-[calc(100vh-5rem)] flex-col">
      <ScrollArea className="flex-1">
        <div className="mx-auto max-w-3xl space-y-4 p-4">
          <AnimatePresence>
            {messages.length === 0 && !isStreaming && (
              <motion.div
                key="empty"
                initial={reduced ? false : { opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={reduced ? undefined : { opacity: 0 }}
                className="flex flex-col items-center gap-6 pt-24 text-center"
              >
                <div>
                  <h2 className="text-2xl font-bold tracking-tight">Chat IA</h2>
                  <p className="text-sm text-muted-foreground">
                    Pregunta sobre las noticias de IA de hoy
                  </p>
                </div>
                <motion.div
                  className="flex flex-wrap justify-center gap-2"
                  variants={chipContainer}
                  initial="hidden"
                  animate="show"
                >
                  {SUGGESTIONS.map(s => (
                    <motion.div key={s} variants={chipItem}>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => send(s)}
                      >
                        {s}
                      </Button>
                    </motion.div>
                  ))}
                </motion.div>
              </motion.div>
            )}
          </AnimatePresence>

          {messages.map(msg => (
            <motion.div
              key={msg.id}
              initial={reduced ? false : {
                opacity: 0,
                x: msg.role === 'user' ? 20 : -20,
              }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.2, ease: 'easeOut' as const }}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted'
                }`}
              >
                {msg.content || (isStreaming ? '...' : '')}
              </div>
            </motion.div>
          ))}

          <div ref={bottomRef} />
        </div>
      </ScrollArea>

      <div className="border-t bg-background p-4">
        <div className="mx-auto flex max-w-3xl items-end gap-2">
          <Textarea
            placeholder="Escribe tu pregunta..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            className="min-h-10 max-h-32 resize-none"
            aria-label="Escribe tu pregunta"
          />
          <Button
            size="icon"
            onClick={() => send(input)}
            disabled={!input.trim() || isStreaming}
          >
            <IconSend className="size-4" />
            <span className="sr-only">Enviar</span>
          </Button>
        </div>
      </div>
    </div>
  )
}
```

**Step 2: Verify build**

```bash
cd frontend && bun run build
```

**Step 3: Commit**

```bash
git add frontend/src/pages/Chat.tsx
git commit -m "feat: wire Chat to real SSE streaming (POST /api/chat)"
```

---

### Task 9: Cleanup + Final Verification

**Files:**
- Modify: `frontend/src/lib/mock-data.ts` (keep for reference but remove all imports)
- Modify: `frontend/src/App.tsx` (verify no mock imports remain)

**Step 1: Verify no mock imports remain in pages**

Search all page files for `mock-data` imports:

```bash
grep -r "mock-data" frontend/src/pages/
```

Expected: No results. If any remain, remove the import.

**Step 2: Build check**

```bash
cd frontend && bun run build
```

Expected: Clean build. Bundle should be similar size (~167 kB gzip) since mock data was already bundled.

**Step 3: Run dev server and test**

```bash
cd frontend && bun run dev
```

Test checklist:
- [ ] Visit `/` → redirects to `/login` (no token)
- [ ] Login with correct password → redirects to Dashboard
- [ ] Dashboard loads real items from API
- [ ] Topic filter works on Dashboard
- [ ] Navigate to Trending → loads real trending + top items
- [ ] Navigate to Buscar → search returns real results from API
- [ ] Chat → sends question, receives streaming SSE response
- [ ] Logout button → clears tokens, redirects to login
- [ ] All animations still work (page transitions, card stagger, hover, theme toggle)

**Step 4: Commit if any fixes needed**

```bash
git add frontend/
git commit -m "fix: final adjustments to React API wiring"
```

**Step 5: Update AGENTS.md**

In `AGENTS.md`, update the "Frontend Migration" section to note that the React frontend is now wired to the real API (no longer mock data). Update the "Next Tasks" list.

```bash
git add AGENTS.md
git commit -m "docs: update AGENTS.md — React frontend wired to real API"
```
