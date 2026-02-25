import { createContext, useContext, useState, useCallback, useEffect } from 'react'
import { Navigate, useLocation } from 'react-router'
import type { ReactNode } from 'react'
import { apiPost } from '@/lib/api'
import { storeTokens, clearTokens, hasTokens, isTokenExpired } from '@/lib/auth'
import type { AuthTokens } from '@/lib/auth'

interface AuthContextValue {
  isAuthenticated: boolean
  requestOtp: (email: string) => Promise<void>
  verifyOtp: (email: string, code: string) => Promise<void>
  loginLegacy: (password: string) => Promise<void>
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

  const requestOtp = useCallback(async (email: string) => {
    await apiPost('/api/auth/otp/request', { email })
  }, [])

  const verifyOtp = useCallback(async (email: string, code: string) => {
    const tokens = await apiPost<AuthTokens>('/api/auth/otp/verify', { email, code })
    storeTokens(tokens)
    setIsAuthenticated(true)
  }, [])

  const loginLegacy = useCallback(async (password: string) => {
    const tokens = await apiPost<AuthTokens>('/api/auth/token', { password })
    storeTokens(tokens)
    setIsAuthenticated(true)
  }, [])

  const logout = useCallback(() => {
    clearTokens()
    setIsAuthenticated(false)
  }, [])

  return (
    <AuthContext value={{ isAuthenticated, requestOtp, verifyOtp, loginLegacy, logout }}>
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
