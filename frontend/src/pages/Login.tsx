import { useState, useRef, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router'
import { useTranslation } from 'react-i18next'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/hooks/use-auth'

type Step = 'email' | 'code'

export default function Login() {
  const [step, setStep] = useState<Step>('email')
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { requestOtp, verifyOtp, loginPasskey } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const { t } = useTranslation()
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
      setError(err instanceof Error ? err.message : t('login.errorSendingCode'))
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
      setError(err instanceof Error ? err.message : t('login.invalidCode'))
    } finally {
      setLoading(false)
    }
  }

  async function handlePasskeyLogin() {
    if (!email.trim()) return
    setError('')
    setLoading(true)
    try {
      await loginPasskey(email)
      navigate(from, { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : t('login.passkeyError'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-svh items-start justify-center px-4 pt-[20vh] pb-8">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl font-bold">AI News</CardTitle>
          <CardDescription>
            {step === 'email' && t('login.description')}
            {step === 'code' && t('login.codeSent', { email })}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {error && (
            <p className="mb-4 text-sm text-destructive">{error}</p>
          )}

          {step === 'email' && (
            <form onSubmit={handleRequestOtp} className="space-y-4">
              <Input
                name="email"
                type="email"
                placeholder="you@email.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                disabled={loading}
                aria-label="Email"
                autoComplete="email"
              />
              <Button type="submit" className="w-full" disabled={loading || !email.trim()}>
                {loading ? t('login.sendingCode') : t('login.sendCode')}
              </Button>
              <Button
                type="button"
                variant="outline"
                className="w-full"
                disabled={loading || !email.trim()}
                onClick={handlePasskeyLogin}
              >
                {loading ? t('login.passkeyLoading') : t('login.passkeyLogin')}
              </Button>
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
                aria-label={t('login.otpLabel')}
                className="text-center text-2xl tracking-[0.3em] font-mono"
              />
              <Button type="submit" className="w-full" disabled={loading || code.length !== 6}>
                {loading ? t('login.verifying') : t('login.verify')}
              </Button>
              <div className="flex justify-between">
                <button
                  type="button"
                  className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                  onClick={() => { setCode(''); setError(''); setStep('email') }}
                >
                  {t('login.changeEmail')}
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
                      setError(err instanceof Error ? err.message : t('login.errorResending'))
                    } finally {
                      setLoading(false)
                    }
                  }}
                >
                  {t('login.resendCode')}
                </button>
              </div>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
