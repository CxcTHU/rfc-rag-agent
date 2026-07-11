import { Component, type ErrorInfo, type ReactNode } from 'react'
import { AlertTriangle, Loader2, RefreshCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function LoadingState({ label = '正在加载...', compact = false }: { label?: string; compact?: boolean }) {
  return (
    <div className={cn('empty-state', compact && 'compact')} aria-busy="true" aria-live="polite">
      <Loader2 className="spin" size={18} aria-hidden="true" />
      <span>{label}</span>
    </div>
  )
}

export function EmptyState({
  title,
  description,
  compact = false,
  action,
}: {
  title: string
  description?: string
  compact?: boolean
  action?: ReactNode
}) {
  return (
    <div className={cn('empty-state', compact && 'compact')}>
      <strong>{title}</strong>
      {description ? <p>{description}</p> : null}
      {action}
    </div>
  )
}

export function RetryState({
  title = '加载失败',
  error,
  onRetry,
  retryLabel = '重试',
  compact = false,
}: {
  title?: string
  error?: unknown
  onRetry: () => void
  retryLabel?: string
  compact?: boolean
}) {
  const message = error instanceof Error ? error.message : error ? String(error) : '请稍后重试。'
  return (
    <div className={cn('empty-state', compact && 'compact')} role="alert">
      <AlertTriangle size={18} aria-hidden="true" />
      <strong>{title}</strong>
      <p>{message}</p>
      <Button size="sm" variant="secondary" onClick={onRetry}>
        <RefreshCcw size={14} />
        {retryLabel}
      </Button>
    </div>
  )
}

type ErrorBoundaryProps = {
  children: ReactNode
  resetKey?: string
}

type ErrorBoundaryState = {
  error: Error | null
  resetKey?: string
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null, resetKey: this.props.resetKey }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { error }
  }

  static getDerivedStateFromProps(props: ErrorBoundaryProps, state: ErrorBoundaryState): Partial<ErrorBoundaryState> | null {
    if (state.error && props.resetKey !== state.resetKey) {
      return { error: null, resetKey: props.resetKey }
    }
    return props.resetKey !== state.resetKey ? { resetKey: props.resetKey } : null
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('React workspace render failed', error.name, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <main className="auth-boot-screen">
          <RetryState
            title="页面渲染失败"
            error={this.state.error}
            onRetry={() => this.setState({ error: null })}
          />
        </main>
      )
    }
    return this.props.children
  }
}
