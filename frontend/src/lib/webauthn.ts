import { startRegistration, startAuthentication } from '@simplewebauthn/browser'
import type {
  PublicKeyCredentialCreationOptionsJSON,
  PublicKeyCredentialRequestOptionsJSON,
} from '@simplewebauthn/browser'
import { apiPost, apiGet, apiDelete } from './api'
import type { AuthTokens } from './auth'

export interface WebAuthnCredential {
  id: string
  device_name: string
  backed_up: boolean
  created_at: string
  last_used_at: string | null
}

export async function registerPasskey(deviceName: string): Promise<void> {
  // 1. Get registration options from server (POST, authenticated)
  const options = await apiPost<PublicKeyCredentialCreationOptionsJSON>(
    '/api/auth/webauthn/register/options',
    {},
  )

  // 2. Create credential via browser API (triggers biometric prompt)
  const credential = await startRegistration({ optionsJSON: options })

  // 3. Send to server for verification
  await apiPost('/api/auth/webauthn/register/verify', {
    device_name: deviceName,
    credential,
  })
}

export async function loginWithPasskey(email: string): Promise<AuthTokens> {
  // 1. Get authentication options from server
  const options = await apiPost<PublicKeyCredentialRequestOptionsJSON>(
    '/api/auth/webauthn/login/options',
    { email },
  )

  // 2. Get assertion via browser API (triggers biometric prompt)
  const credential = await startAuthentication({ optionsJSON: options })

  // 3. Verify with server, get tokens
  return apiPost<AuthTokens>('/api/auth/webauthn/login/verify', {
    email,
    credential,
  })
}

export async function listPasskeys(): Promise<WebAuthnCredential[]> {
  const { data } = await apiGet<WebAuthnCredential[]>('/api/auth/webauthn/credentials')
  return data
}

export async function deletePasskey(id: string): Promise<void> {
  await apiDelete(`/api/auth/webauthn/credentials/${id}`)
}
