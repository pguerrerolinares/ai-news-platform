import { createContext, useContext, useState, useCallback, useEffect } from 'react'
import { Navigate, useLocation } from 'react-router'
import type { ReactNode } from 'react'
import { apiPost } from '@/lib/api'
import { storeTokens, clearTokens, hasTokens, isTokenExpired } from '@/lib/auth'
import type { AuthTokens } from '@/lib/auth'

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
