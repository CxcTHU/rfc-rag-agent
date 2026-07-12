import { render } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import { AuthContext, type AuthContextValue } from '@/features/auth/AuthContext'
import { AuthScreen } from '@/features/auth/AuthScreen'

const auth: AuthContextValue = {
  token: null,
  user: null,
  isChecking: false,
  bootError: null,
  isSubmitting: false,
  submitError: null,
  signIn: vi.fn(async () => undefined),
  signUp: vi.fn(async () => undefined),
  signOut: vi.fn(),
  retryCurrentUser: vi.fn(),
  expireSession: vi.fn(),
}

function renderAuthScreen() {
  return render(
    <AuthContext.Provider value={auth}>
      <AuthScreen />
    </AuthContext.Provider>,
  )
}

test('renders the complete animated capability diagrams', () => {
  const { container } = renderAuthScreen()

  expect(container.querySelectorAll('.hybrid .hybrid-path')).toHaveLength(2)
  expect(container.querySelector('.hybrid .hybrid-core')).toBeInTheDocument()
  expect(container.querySelectorAll('.hybrid .hybrid-rank span')).toHaveLength(3)

  expect(container.querySelector('.graph .graph-links')).toBeInTheDocument()
  expect(container.querySelectorAll('.graph .graph-node')).toHaveLength(3)
  expect(container.querySelector('.graph .graph-icon')).toBeInTheDocument()

  expect(container.querySelectorAll('.multimodal .modal-stack')).toHaveLength(3)
  expect(container.querySelector('.multimodal .modal-scan')).toBeInTheDocument()
})
