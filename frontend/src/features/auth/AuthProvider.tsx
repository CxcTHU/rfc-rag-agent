import { useEffect, useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  clearToken,
  currentUser,
  login,
  logoutSession,
  persistToken,
  readStoredToken,
  register,
} from '@/features/auth/api'
import { isAuthApiError } from '@/lib/api/client'
import { AuthContext, type AuthContextValue } from '@/features/auth/AuthContext'
const currentUserKey = ['auth', 'current-user'] as const

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [token, setToken] = useState<string | null>(() => readStoredToken())

  const userQuery = useQuery({
    queryKey: currentUserKey,
    queryFn: ({ signal }) => currentUser(token as string, signal),
    enabled: Boolean(token),
    staleTime: Infinity,
  })

  useEffect(() => {
    if (!userQuery.error || !isAuthApiError(userQuery.error)) return
    clearToken()
    queryClient.clear()
    setToken(null)
  }, [queryClient, userQuery.error])

  const loginMutation = useMutation({
    mutationFn: async (input: { identity: string; password: string; remember: boolean }) => {
      const response = await login(input.identity, input.password)
      return { response, remember: input.remember }
    },
    onSuccess: ({ response, remember }) => {
      queryClient.clear()
      persistToken(response.access_token, remember)
      setToken(response.access_token)
      queryClient.setQueryData(currentUserKey, response.user)
    },
  })

  const registerMutation = useMutation({
    mutationFn: async (input: { username: string; email: string; password: string; remember: boolean }) => {
      await register(input.username, input.email, input.password)
      const response = await login(input.username, input.password)
      return { response, remember: input.remember }
    },
    onSuccess: ({ response, remember }) => {
      queryClient.clear()
      persistToken(response.access_token, remember)
      setToken(response.access_token)
      queryClient.setQueryData(currentUserKey, response.user)
    },
  })

  function expireSession() {
    clearToken()
    queryClient.clear()
    setToken(null)
  }

  function signOut() {
    const currentToken = token
    expireSession()
    void logoutSession(currentToken).catch(() => undefined)
  }

  const value: AuthContextValue = {
    token,
    user: token ? userQuery.data || null : null,
    isChecking: Boolean(token && userQuery.isPending),
    bootError: token && userQuery.error && !isAuthApiError(userQuery.error) ? userQuery.error : null,
    isSubmitting: loginMutation.isPending || registerMutation.isPending,
    submitError: loginMutation.error || registerMutation.error,
    signIn: async (identity, password, remember) => {
      await loginMutation.mutateAsync({ identity, password, remember })
    },
    signUp: async (username, email, password, remember) => {
      await registerMutation.mutateAsync({ username, email, password, remember })
    },
    signOut,
    retryCurrentUser: () => {
      void userQuery.refetch()
    },
    expireSession,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
