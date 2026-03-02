import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router'
import { useTranslation } from 'react-i18next'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { apiGet } from '@/lib/api'

const DISMISSED_KEY = 'passkey-prompt-dismissed'

export function PasskeyPrompt() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    if (sessionStorage.getItem(DISMISSED_KEY)) return

    apiGet<{ id: string }[]>('/api/auth/webauthn/credentials')
      .then(({ data }) => {
        if (data.length === 0) setVisible(true)
      })
      .catch(() => {
        // Silently ignore — don't show banner if check fails
      })
  }, [])

  if (!visible) return null

  function handleDismiss() {
    sessionStorage.setItem(DISMISSED_KEY, '1')
    setVisible(false)
  }

  return (
    <Card className="border-primary/20 bg-primary/5">
      <CardContent className="flex items-center justify-between gap-4 py-3">
        <div className="min-w-0">
          <p className="text-sm font-medium">{t('passkeyPrompt.title')}</p>
          <p className="text-xs text-muted-foreground">{t('passkeyPrompt.description')}</p>
        </div>
        <div className="flex shrink-0 gap-2">
          <Button size="sm" variant="ghost" onClick={handleDismiss}>
            {t('passkeyPrompt.dismiss')}
          </Button>
          <Button size="sm" onClick={() => navigate('/settings')}>
            {t('passkeyPrompt.register')}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
