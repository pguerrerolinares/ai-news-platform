import { useState, useRef, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/hooks/use-auth'

type Step = 'email' | 'code' | 'legacy'

export default function Login() {
  const [step, setStep] = useState<Step>('email')
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { requestOtp, verifyOtp, loginLegacy } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const codeRef = useRef<HTMLInputElement>(null)

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

  useEffect(() => {
    if (step === 'code') codeRef.current?.focus()
  }, [step])

  async function handleRequestOtp(e: React.FormEvent) {
    e.preventDefault()
    if (!email.trim()) return
    setError('')
    setLoading(true)
    try {
      await requestOtp(email)
      setStep('code')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al enviar el codigo')
    } finally {
      setLoading(false)
    }
  }

  async function handleVerifyOtp(e: React.FormEvent) {
    e.preventDefault()
    if (code.length !== 6) return
    setError('')
    setLoading(true)
    try {
      await verifyOtp(email, code)
      navigate(from, { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Codigo invalido o expirado')
    } finally {
      setLoading(false)
    }
  }

  async function handleLegacyLogin(e: React.FormEvent) {
    e.preventDefault()
    if (!password.trim()) return
    setError('')
    setLoading(true)
    try {
      await loginLegacy(password)
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
          <CardDescription>
            {step === 'email' && 'Introduce tu email para recibir un codigo'}
            {step === 'code' && `Codigo enviado a ${email}`}
            {step === 'legacy' && 'Acceso con contrasena compartida'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {error && (
            <p className="mb-4 text-sm text-destructive">{error}</p>
          )}

          {step === 'email' && (
            <form onSubmit={handleRequestOtp} className="space-y-4">
              <Input
                type="email"
                placeholder="tu@email.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                disabled={loading}
                aria-label="Email"
                autoFocus
              />
              <Button type="submit" className="w-full" disabled={loading || !email.trim()}>
                {loading ? 'Enviando...' : 'Enviar codigo'}
              </Button>
              <button
                type="button"
                className="w-full text-xs text-muted-foreground hover:text-foreground transition-colors"
                onClick={() => { setError(''); setStep('legacy') }}
              >
                Acceso con contrasena
              </button>
            </form>
          )}

          {step === 'code' && (
            <form onSubmit={handleVerifyOtp} className="space-y-4">
              <Input
                ref={codeRef}
                type="text"
                inputMode="numeric"
                pattern="\d{6}"
                maxLength={6}
                placeholder="000000"
                value={code}
                onChange={e => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                disabled={loading}
                aria-label="Codigo OTP"
                className="text-center text-2xl tracking-[0.3em] font-mono"
              />
              <Button type="submit" className="w-full" disabled={loading || code.length !== 6}>
                {loading ? 'Verificando...' : 'Verificar'}
              </Button>
              <div className="flex justify-between">
                <button
                  type="button"
                  className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                  onClick={() => { setCode(''); setError(''); setStep('email') }}
                >
                  Cambiar email
                </button>
                <button
                  type="button"
                  className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                  disabled={loading}
                  onClick={async () => {
                    setError('')
                    setLoading(true)
                    try {
                      await requestOtp(email)
                      setError('')
                    } catch (err) {
                      setError(err instanceof Error ? err.message : 'Error al reenviar')
                    } finally {
                      setLoading(false)
                    }
                  }}
                >
                  Reenviar codigo
                </button>
              </div>
            </form>
          )}

          {step === 'legacy' && (
            <form onSubmit={handleLegacyLogin} className="space-y-4">
              <Input
                type="password"
                placeholder="Contrasena"
                value={password}
                onChange={e => setPassword(e.target.value)}
                disabled={loading}
                aria-label="Contrasena"
                autoFocus
              />
              <Button type="submit" className="w-full" disabled={loading || !password.trim()}>
                {loading ? 'Entrando...' : 'Entrar'}
              </Button>
              <button
                type="button"
                className="w-full text-xs text-muted-foreground hover:text-foreground transition-colors"
                onClick={() => { setError(''); setStep('email') }}
              >
                Acceso con email
              </button>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
