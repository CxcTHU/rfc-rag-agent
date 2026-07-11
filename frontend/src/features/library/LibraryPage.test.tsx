import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthContext, type AuthContextValue } from '@/features/auth/AuthContext'
import { LibraryPage } from '@/features/library/LibraryPage'

const auth: AuthContextValue = {
  token: 'fake-unit-token',
  user: { id: 42, username: 'tester', email: 'tester@example.test', is_active: true, created_at: '2026-01-01' },
  isChecking: false,
  bootError: null,
  isSubmitting: false,
  submitError: null,
  signIn: vi.fn(),
  signUp: vi.fn(),
  signOut: vi.fn(),
  retryCurrentUser: vi.fn(),
  expireSession: vi.fn(),
}

function renderLibrary() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthContext.Provider value={auth}><LibraryPage /></AuthContext.Provider>
    </QueryClientProvider>,
  )
}

describe('LibraryPage states', () => {
  beforeEach(() => vi.unstubAllGlobals())

  it('distinguishes loading and a successful empty corpus', async () => {
    let resolveResponse: ((response: Response) => void) | undefined
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise<Response>((resolve) => { resolveResponse = resolve })))
    renderLibrary()
    expect(screen.getByText('正在加载语料库...')).toBeInTheDocument()
    resolveResponse?.(new Response(JSON.stringify([]), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    expect(await screen.findByText('语料库为空')).toBeInTheDocument()
  })

  it('shows normal data and a distinct filter-empty state', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify([{
      id: 1, title: 'RFC 测试文档', source_type: 'local_file', file_name: 'rfc.pdf', status: 'imported', chunk_count: 4,
    }]), { status: 200, headers: { 'Content-Type': 'application/json' } })))
    renderLibrary()
    expect(await screen.findByText('RFC 测试文档')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('筛选语料库'), '不存在')
    expect(screen.getByText('没有匹配的文档')).toBeInTheDocument()
  })

  it('exposes an explicit retry action after an HTTP failure', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'temporary failure' }), { status: 503, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)
    renderLibrary()
    expect(await screen.findByText('语料库加载失败')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '重试' }))
    expect(await screen.findByText('语料库为空')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
