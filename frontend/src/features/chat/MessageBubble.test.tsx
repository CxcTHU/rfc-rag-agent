import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { MessageBubble, ThinkingPanel } from '@/features/chat/AskPage'
import { buildCitationView } from '@/features/evidence/citations'

describe('chat rendering', () => {
  it('never renders an Agent timer on a user message', () => {
    render(
      <MessageBubble
        activeCitation={null}
        isSelected={false}
        message={{ id: 'user-1', role: 'user', content: '问题[1]', startedAt: 1, completedAt: 3000 }}
        now={5000}
        onCitation={vi.fn()}
        onRetry={vi.fn()}
        onSelect={vi.fn()}
      />,
    )
    expect(screen.queryByText(/思考|已处理/)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '[1]' })).not.toBeInTheDocument()
    expect(screen.queryByText('1 个引用')).not.toBeInTheDocument()
  })

  it('shows only the real pending event supplied to ThinkingPanel', () => {
    render(
      <ThinkingPanel
        activeCitation={null}
        citationView={buildCitationView()}
        elapsedMs={1200}
        isPending
        onCitation={vi.fn()}
        steps={[{ name: 'search_knowledge', step_summary: '后端返回的真实检索事件' }]}
      />,
    )
    expect(screen.getByText('后端返回的真实检索事件')).toBeInTheDocument()
    expect(screen.queryByText(/HyDE|引用修复|规划阶段/)).not.toBeInTheDocument()
  })
})
