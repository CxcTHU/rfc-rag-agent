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

  it('renders deduplicated retrieved image evidence inline below an assistant answer', () => {
    render(
      <MessageBubble
        activeCitation={null}
        isSelected={false}
        message={{
          id: 'assistant-with-figure',
          role: 'assistant',
          content: '检索到了对应图片证据。[1]',
          result: {
            question: '有图片资源吗？',
            answer: '检索到了对应图片证据。[1]',
            citations: [1],
            refused: false,
            mode: 'agent',
            workflow_steps: [],
            sources: [
              {
                title: 'RFC 孔隙结构示意图',
                source_type: 'local_file',
                document_id: 7,
                chunk_id: 101,
                chunk_type: 'image_description',
                image_url: '/assets/rfc-pores.png',
                caption: '孔隙结构示意图',
              },
              {
                title: 'RFC 孔隙结构示意图（重复检索）',
                source_type: 'local_file',
                document_id: 7,
                chunk_id: 102,
                chunk_type: 'image_description',
                image_url: '/assets/rfc-pores.png',
                caption: '孔隙结构示意图',
              },
            ],
          },
        }}
        now={0}
        onCitation={vi.fn()}
        onRetry={vi.fn()}
        onSelect={vi.fn()}
      />,
    )

    expect(screen.getByRole('region', { name: '本回答检索到的图片证据' })).toBeInTheDocument()
    expect(screen.getAllByRole('img', { name: '孔隙结构示意图' })).toHaveLength(1)
    expect(screen.getByRole('button', { name: '[1]' })).toBeInTheDocument()
  })
})
