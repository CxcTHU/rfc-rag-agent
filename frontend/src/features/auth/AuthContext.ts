import { createContext, useContext } from 'react'
import type { AuthUser } from '@/lib/types'

export type AuthContextValue = {
  token: string | null
  user: AuthUser | null
  isChecking: boolean
  bootError: unknown
  isSubmitting: boolean
  submitError: unknown
  signIn: (identity: string, password: string, remember: boolean) => Promise<void>
  signUp: (username: string, email: string, password: string, remember: boolean) => Promise<void>
  signOut: () => void
  retryCurrentUser: () => void
  expireSession: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used within AuthProvider')
  return value
}
