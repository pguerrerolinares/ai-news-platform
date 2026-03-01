import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { listPasskeys, registerPasskey, deletePasskey } from '@/lib/webauthn'
import type { WebAuthnCredential } from '@/lib/webauthn'

export default function Settings() {
  const { t } = useTranslation()
  const [passkeys, setPasskeys] = useState<WebAuthnCredential[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showRegister, setShowRegister] = useState(false)
  const [deviceName, setDeviceName] = useState('')
  const [registering, setRegistering] = useState(false)

  async function loadPasskeys() {
    try {
      const keys = await listPasskeys()
      setPasskeys(keys)
    } catch {
      setError('Failed to load passkeys')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadPasskeys() }, [])

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault()
    if (!deviceName.trim()) return
    setRegistering(true)
    setError('')
    try {
      await registerPasskey(deviceName.trim())
      setDeviceName('')
      setShowRegister(false)
      await loadPasskeys()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed')
    } finally {
      setRegistering(false)
    }
  }

  async function handleDelete(id: string) {
    if (!confirm(t('settings.deleteConfirm'))) return
    try {
      await deletePasskey(id)
      setPasskeys(prev => prev.filter(p => p.id !== id))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed')
    }
  }

  function formatDate(dateStr: string | null) {
    if (!dateStr) return t('settings.never')
    return new Date(dateStr).toLocaleDateString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric',
    })
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{t('settings.title')}</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t('settings.passkeys')}</CardTitle>
          <CardDescription>{t('settings.passkeysDescription')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          {loading ? (
            <p className="text-sm text-muted-foreground">Loading...</p>
          ) : passkeys.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t('settings.noPasskeys')}</p>
          ) : (
            <div className="space-y-3">
              {passkeys.map(pk => (
                <div
                  key={pk.id}
                  className="flex items-center justify-between rounded-lg border p-3"
                >
                  <div className="space-y-1">
                    <p className="text-sm font-medium">{pk.device_name}</p>
                    <p className="text-xs text-muted-foreground">
                      {t('settings.registered')}: {formatDate(pk.created_at)}
                      {' · '}
                      {t('settings.lastUsed')}: {formatDate(pk.last_used_at)}
                      {pk.backed_up && (
                        <span className="ml-2 text-green-600">
                          {t('settings.backedUp')}
                        </span>
                      )}
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-destructive hover:text-destructive"
                    onClick={() => handleDelete(pk.id)}
                  >
                    {t('settings.delete')}
                  </Button>
                </div>
              ))}
            </div>
          )}

          {showRegister ? (
            <form onSubmit={handleRegister} className="flex gap-2">
              <Input
                value={deviceName}
                onChange={e => setDeviceName(e.target.value)}
                placeholder={t('settings.deviceNamePlaceholder')}
                disabled={registering}
                autoFocus
              />
              <Button type="submit" disabled={registering || !deviceName.trim()}>
                {registering ? t('settings.registering') : t('settings.register')}
              </Button>
              <Button
                type="button"
                variant="ghost"
                onClick={() => { setShowRegister(false); setDeviceName('') }}
              >
                {t('settings.cancel')}
              </Button>
            </form>
          ) : (
            <Button
              variant="outline"
              onClick={() => setShowRegister(true)}
            >
              {t('settings.registerPasskey')}
            </Button>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
