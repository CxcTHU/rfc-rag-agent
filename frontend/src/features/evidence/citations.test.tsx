import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { buildCitationView, renderAnswerWithCitations } from '@/features/evidence/citations'
import { SourceCard } from '@/features/evidence/SourcesPanel'
import { sourceItemsForResult } from '@/features/evidence/sourceModel'
import type { AgentQueryResponse } from '@/lib/types'

const result: AgentQueryResponse = {
  question: 'q', answer: '证据[2]', citations: [2], refused: false, mode: 'tool_calling_agent', workflow_steps: [],
  sources: [
    { title: '检索但未引用', source_type: 'document' },
    { title: '正文引用', source_type: 'document' },
  ],
}

describe('message-level citations', () => {
  it('keeps uncited retrieval sources without manufacturing body citations', () => {
    const items = sourceItemsForResult(result)
    expect(items.map((item) => item.source.title)).toEqual(['正文引用', '检索但未引用'])
    expect(items.map((item) => item.hasCitation)).toEqual([true, false])
    expect(buildCitationView(result).citationCount).toBe(1)
  })

  it('labels an uncited retrieval source without presenting a fake citation jump', async () => {
    const onSelect = vi.fn()
    render(
      <SourceCard
        active={false}
        citationLinked={false}
        index={2}
        messageId="assistant-1"
        onSelect={onSelect}
        source={result.sources[0]}
      />,
    )
    expect(screen.getByText('仅检索')).toBeInTheDocument()
    expect(screen.queryByText('[2]')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /检索但未引用/ }))
    expect(onSelect).toHaveBeenCalledWith(2, false)
  })

  it('keeps invalid citations and retrieval-only source cards in separate index namespaces', () => {
    const invalidCitationResult: AgentQueryResponse = {
      ...result,
      answer: '无效引用[99]',
      citations: [99],
      invalid_citations: [99],
    }
    const items = sourceItemsForResult(invalidCitationResult)
    const citationView = buildCitationView(invalidCitationResult)
    expect(citationView.citationCount).toBe(0)
    expect(citationView.invalidCitationCount).toBe(1)
    expect(items.map((item) => item.displayIndex)).toEqual([1, 2])
    expect(items.every((item) => !item.hasCitation)).toBe(true)
    render(<div>{renderAnswerWithCitations(invalidCitationResult.answer, null, vi.fn(), citationView)}</div>)
    expect(screen.getByLabelText('无效引用 99')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '[99]' })).not.toBeInTheDocument()
  })

  it('never promotes metadata-only citations that are absent from the answer body', () => {
    const mismatched: AgentQueryResponse = {
      ...result,
      answer: '正文只引用[1]',
      citations: [1, 2],
    }
    const view = buildCitationView(mismatched)
    expect(view.citationCount).toBe(1)
    expect(view.items.map((item) => item.source.title)).toEqual(['检索但未引用'])

    const noBodyMarkers = buildCitationView({ ...mismatched, answer: '正文没有引用标记' })
    expect(noBodyMarkers.citationCount).toBe(0)
    expect(sourceItemsForResult({ ...mismatched, answer: '正文没有引用标记' }).every((item) => !item.hasCitation)).toBe(true)
  })

  it('renders and activates only the citation index passed by its owning message', async () => {
    const onSelect = vi.fn()
    const { rerender } = render(<div>{renderAnswerWithCitations(result.answer, null, onSelect, buildCitationView(result))}</div>)
    await userEvent.click(screen.getByRole('button', { name: '[1]' }))
    expect(onSelect).toHaveBeenCalledWith(1)
    rerender(<div>{renderAnswerWithCitations(result.answer, 1, onSelect, buildCitationView(result))}</div>)
    expect(screen.getByRole('button', { name: '[1]' })).toHaveClass('active')
  })

  it('preserves wide-table controls without row/column count labels', async () => {
    const table = [
      '| A | B | C | D | E | F | G | H |',
      '| --- | --- | --- | --- | --- | --- | --- | --- |',
      '| 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |',
    ].join('\n')
    render(<div>{renderAnswerWithCitations(table, null, vi.fn())}</div>)
    expect(screen.queryByText(/表格\s+\d+列\s+x\s+\d+行/)).not.toBeInTheDocument()
    expect(screen.getByText('横向滚动查看')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '展开表格' }))
    expect(screen.getByRole('dialog', { name: '展开表格' })).toBeInTheDocument()
    expect(screen.queryByText(/表格\s+\d+列\s+x\s+\d+行/)).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '关闭展开表格' }))
    expect(screen.queryByRole('dialog', { name: '展开表格' })).not.toBeInTheDocument()
  })

  it('keeps full-width Chinese table separators compatible', () => {
    const table = ['｜ 指标 ｜ 数值 ｜', '｜：－－－｜－－－：｜', '｜ 强度 ｜ 42 ｜'].join('\n')
    render(<div>{renderAnswerWithCitations(table, null, vi.fn())}</div>)
    expect(screen.queryByText(/表格\s+\d+列\s+x\s+\d+行/)).not.toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: '指标' })).toBeInTheDocument()
  })
})
