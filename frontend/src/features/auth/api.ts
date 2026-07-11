import { apiJson } from '@/lib/api/client'
import type { AuthUser, TokenResponse } from '@/lib/types'

const LOCAL_TOKEN_KEY = 'rfc-rag-agent.authToken'
const SESSION_TOKEN_KEY = 'rfc-rag-agent.sessionAuthToken'

export function readStoredToken() {
  return window.localStorage.getItem(LOCAL_TOKEN_KEY) || window.sessionStorage.getItem(SESSION_TOKEN_KEY)
}

export function persistToken(token: string, remember: boolean) {
  const primary = remember ? window.localStorage : window.sessionStorage
  const secondary = remember ? window.sessionStorage : window.localStorage
  primary.setItem(remember ? LOCAL_TOKEN_KEY : SESSION_TOKEN_KEY, token)
  secondary.removeItem(remember ? SESSION_TOKEN_KEY : LOCAL_TOKEN_KEY)
}

export function clearToken() {
  window.localStorage.removeItem(LOCAL_TOKEN_KEY)
  window.sessionStorage.removeItem(SESSION_TOKEN_KEY)
}

export function login(usernameOrEmail: string, password: string) {
  return apiJson<TokenResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username_or_email: usernameOrEmail, password }),
  })
}

export function logoutSession(token?: string | null) {
  return apiJson<{ status: string }>('/auth/logout', { token, method: 'POST' })
}

export function register(username: string, email: string, password: string) {
  return apiJson<AuthUser>('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ username, email, password }),
  })
}

export function currentUser(token: string, signal?: AbortSignal) {
  return apiJson<AuthUser>('/auth/me', { token, signal })
}
