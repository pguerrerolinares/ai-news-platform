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

  function getRedirectPath(): string {
    const state: unknown = location.state
    if (state && typeof state === 'object' && 'from' in state) {
      const { from } = state
      if (from && typeof from === 'object' && 'pathname' in from) {
        const { pathname } = from
        if (typeof pathname === 'string') return pathname
      }
    }
    return '/'
  }

  const from = getRedirectPath()

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
