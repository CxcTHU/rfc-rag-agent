import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'
import type { AgentQueryResponse } from '@/lib/types'
import { MarkdownAnswerTable } from '@/features/evidence/MarkdownAnswerTable'

export type CitationSourceItem = {
  displayIndex: number
  originalCitation: number
  hasCitation: boolean
  source: AgentQueryResponse['sources'][number]
  sourceIndex: number
}

export type CitationView = {
  citationCount: number
  invalidCitationCount: number
  displayByOriginal: Map<number, number>
  invalidOriginals: Set<number>
  items: CitationSourceItem[]
}

export function buildCitationView(result?: AgentQueryResponse | null, text?: string): CitationView {
  const answerText = text ?? result?.answer ?? ''
  const orderedOriginals = uniqueNumbers(extractCitationNumbers(answerText))
  const displayByOriginal = new Map<number, number>()
  const invalidOriginals = new Set<number>()
  const declaredInvalid = new Set((result?.invalid_citations || []).map(Number))
  const items: CitationSourceItem[] = []
  orderedOriginals.forEach((originalCitation) => {
    if (declaredInvalid.has(originalCitation)) {
      invalidOriginals.add(originalCitation)
      return
    }
    const sourceIndex = sourceIndexForCitation(result, originalCitation)
    const source = sourceIndex === null ? null : result?.sources[sourceIndex]
    if (sourceIndex !== null && source) {
      const displayIndex = items.length + 1
      displayByOriginal.set(originalCitation, displayIndex)
      items.push({ displayIndex, originalCitation, hasCitation: true, source, sourceIndex })
    } else {
      invalidOriginals.add(originalCitation)
    }
  })
  return {
    citationCount: items.length,
    invalidCitationCount: invalidOriginals.size,
    displayByOriginal,
    invalidOriginals,
    items,
  }
}

function extractCitationNumbers(text: string) {
  const citations: number[] = []
  const pattern = /\[(\d+)\]/g
  let match: RegExpExecArray | null
  while ((match = pattern.exec(text)) !== null) citations.push(Number(match[1]))
  return citations
}

function uniqueNumbers(values: Array<number | string>) {
  const seen = new Set<number>()
  return values
    .map(Number)
    .filter((value) => Number.isFinite(value) && value > 0 && !seen.has(value) && Boolean(seen.add(value)))
}

function sourceIndexForCitation(result: AgentQueryResponse | null | undefined, citation: number) {
  if (!result?.sources.length) return null
  const mapped = result.citation_source_map?.[String(citation)] || result.citation_source_map?.[`[${citation}]`]
  if (typeof mapped === 'number') return normalizeSourceIndex(mapped, result.sources.length)
  if (typeof mapped === 'string') {
    const numeric = Number(mapped)
    if (Number.isFinite(numeric)) return normalizeSourceIndex(numeric, result.sources.length)
    const sourceIndex = result.sources.findIndex(
      (source) => source.source_id === mapped || String(source.chunk_id || '') === mapped || `${source.source_id}:${source.chunk_id}` === mapped,
    )
    if (sourceIndex >= 0) return sourceIndex
  }
  return normalizeSourceIndex(citation, result.sources.length)
}

function normalizeSourceIndex(value: number, count: number) {
  if (value === 0 && count > 0) return 0
  if (value >= 1 && value <= count) return value - 1
  if (value >= 0 && value < count) return value
  return null
}

export function renderAnswerWithCitations(
  text: string,
  activeCitation: number | null,
  selectCitation: (index: number) => void,
  citationView = buildCitationView(undefined, text),
) {
  if (!text) return null
  const lines = text.replace(/\r\n/g, '\n').split('\n')
  const blocks: ReactNode[] = []
  let index = 0
  while (index < lines.length) {
    const line = lines[index]
    if (!line.trim()) {
      index += 1
      continue
    }
    if (isMarkdownTableLine(line) && index + 1 < lines.length && isMarkdownTableSeparator(lines[index + 1])) {
      const tableLines = [line]
      index += 2
      while (index < lines.length && isMarkdownTableLine(lines[index])) {
        tableLines.push(lines[index])
        index += 1
      }
      const [header, ...rows] = tableLines.map(splitMarkdownTableRow)
      blocks.push(
        <MarkdownAnswerTable
          header={header}
          key={`table-${blocks.length}`}
          renderCellContent={(cell, keyPrefix) => renderInline(cell, activeCitation, selectCitation, citationView, keyPrefix)}
          rows={rows}
          tableKey={`table-${blocks.length}`}
        />,
      )
      continue
    }
    const orderedItems: string[] = []
    while (index < lines.length) {
      const match = lines[index].match(/^\s*\d+[.)、]\s+(.+)$/)
      if (!match) break
      orderedItems.push(match[1])
      index += 1
    }
    if (orderedItems.length) {
      blocks.push(<ol key={`ol-${blocks.length}`}>{orderedItems.map((item, itemIndex) => <li key={itemIndex}>{renderInline(item, activeCitation, selectCitation, citationView, `ol-${itemIndex}`)}</li>)}</ol>)
      continue
    }
    const bulletItems: string[] = []
    while (index < lines.length) {
      const match = lines[index].match(/^\s*[-*•]\s+(.+)$/)
      if (!match) break
      bulletItems.push(match[1])
      index += 1
    }
    if (bulletItems.length) {
      blocks.push(<ul key={`ul-${blocks.length}`}>{bulletItems.map((item, itemIndex) => <li key={itemIndex}>{renderInline(item, activeCitation, selectCitation, citationView, `ul-${itemIndex}`)}</li>)}</ul>)
      continue
    }
    const heading = line.match(/^#{1,4}\s+(.+)$/)
    if (heading) {
      blocks.push(<h3 key={`heading-${blocks.length}`}>{renderInline(heading[1], activeCitation, selectCitation, citationView, `heading-${blocks.length}`)}</h3>)
      index += 1
      continue
    }
    blocks.push(<p key={`p-${blocks.length}`}>{renderInline(line, activeCitation, selectCitation, citationView, `p-${blocks.length}`)}</p>)
    index += 1
  }
  return blocks
}

function renderInline(
  text: string,
  activeCitation: number | null,
  selectCitation: (index: number) => void,
  citationView: CitationView,
  keyPrefix: string,
) {
  const nodes: ReactNode[] = []
  const pattern = /(\[\d+\]|\*\*.+?\*\*)/g
  let cursor = 0
  let match: RegExpExecArray | null
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > cursor) nodes.push(text.slice(cursor, match.index))
    const token = match[0]
    const citation = token.match(/^\[(\d+)\]$/)
    if (citation) {
      const originalIndex = Number(citation[1])
      const displayIndex = citationView.displayByOriginal.get(originalIndex)
      if (displayIndex === undefined || citationView.invalidOriginals.has(originalIndex)) {
        nodes.push(
          <span
            aria-label={`无效引用 ${originalIndex}`}
            className="citation-link invalid"
            key={`${keyPrefix}-${match.index}`}
            title="该引用未映射到来源"
          >
            [{originalIndex}]
          </span>,
        )
      } else {
        nodes.push(
          <button
            className={cn('citation-link', activeCitation === displayIndex && 'active')}
            data-citation-index={displayIndex}
            key={`${keyPrefix}-${match.index}`}
            onClick={() => selectCitation(displayIndex)}
            type="button"
          >
            [{displayIndex}]
          </button>,
        )
      }
    } else {
      nodes.push(<strong key={`${keyPrefix}-${match.index}`}>{token.slice(2, -2)}</strong>)
    }
    cursor = match.index + token.length
  }
  if (cursor < text.length) nodes.push(text.slice(cursor))
  return nodes
}

function isMarkdownTableLine(line: string) {
  const normalized = normalizeMarkdownTableSyntax(line).trim()
  return normalized.includes('|') && splitMarkdownTableRow(normalized).length >= 2
}

function isMarkdownTableSeparator(line: string) {
  const cells = splitMarkdownTableRow(line)
  return cells.length >= 2 && cells.every((cell) => /^:?-{1,}:?$/.test(cell.replace(/\s+/g, '').trim()))
}

function splitMarkdownTableRow(line: string) {
  return normalizeMarkdownTableSyntax(line).trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((cell) => cell.trim())
}

function normalizeMarkdownTableSyntax(line: string) {
  return line
    .replace(/\uFF5C/g, '|')
    .replace(/[\uFF1A\uFE55]/g, ':')
    .replace(/[\u2010-\u2015\u2212\uFE58\uFE63\uFF0D]/g, '-')
}
