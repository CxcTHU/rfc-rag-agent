import type { ReactNode } from 'react'
import { Loader2 } from 'lucide-react'
import { RetryState } from '@/components/states'
import { AuthScreen } from '@/features/auth/AuthScreen'
import { useAuth } from '@/features/auth/AuthContext'

export function AuthGate({ children }: { children: ReactNode }) {
  const auth = useAuth()
  if (auth.isChecking) {
    return (
      <main className="auth-boot-screen" aria-live="polite" aria-busy="true">
        <div className="brand-lockup"><span className="brand-mark">R</span><div><strong>RFC-RAG-Agent</strong><small>正在恢复工作台</small></div></div>
        <Loader2 className="spin" size={22} aria-hidden="true" />
      </main>
    )
  }
  if (auth.bootError) {
    return <main className="auth-boot-screen"><RetryState title="会话恢复失败" error={auth.bootError} onRetry={auth.retryCurrentUser} /></main>
  }
  if (!auth.user || !auth.token) return <AuthScreen />
  return children
}
