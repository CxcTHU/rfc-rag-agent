import { buildCitationView, type CitationSourceItem } from '@/features/evidence/citations'
import type { AgentQueryResponse } from '@/lib/types'

export function sourceItemsForResult(result: AgentQueryResponse) {
  const citationView = buildCitationView(result)
  const citationItems = citationView.items
  const usedSourceIndexes = new Set(citationItems.map((item) => item.sourceIndex))
  let nextDisplayIndex = Math.max(0, ...citationItems.map((item) => item.displayIndex)) + 1
  const retrievalOnly: CitationSourceItem[] = []
  result.sources.forEach((source, sourceIndex) => {
    if (usedSourceIndexes.has(sourceIndex)) return
    retrievalOnly.push({
      displayIndex: nextDisplayIndex,
      originalCitation: nextDisplayIndex,
      hasCitation: false,
      source,
      sourceIndex,
    })
    nextDisplayIndex += 1
  })
  return [...citationItems, ...retrievalOnly]
}

export function imageSourceItemsForResult(result: AgentQueryResponse) {
  if (result.refused) return []
  const seen = new Set<string>()
  return sourceItemsForResult(result).flatMap((item) => {
    const imageUrl = item.source.image_url || ''
    if (!imageUrl || item.source.chunk_type !== 'image_description' || seen.has(imageUrl)) return []
    seen.add(imageUrl)
    return [{ ...item, imageUrl }]
  }).slice(0, 4)
}

export function sourceMetaLine(source: AgentQueryResponse['sources'][number]) {
  const parts = [
    source.page_number ? `第 ${source.page_number} 页` : '',
    source.chunk_index !== undefined && source.chunk_index !== null ? `Chunk ${source.chunk_index}` : '',
    source.chunk_id ? `ID ${source.chunk_id}` : '',
  ].filter(Boolean)
  return parts.length ? parts.join(' / ') : '未提供页码或 chunk 信息'
}

export function sourceOpenUrl(source: AgentQueryResponse['sources'][number]) {
  if (source.document_id === undefined || source.document_id === null) return ''
  return `/documents/${encodeURIComponent(String(source.document_id))}/open`
}
