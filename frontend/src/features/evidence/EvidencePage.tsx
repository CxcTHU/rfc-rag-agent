import { ExternalLink } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Panel, PanelHeader } from '@/components/ui/panel'
import { EmptyState, LoadingState, RetryState } from '@/components/states'
import { useChatWorkspace } from '@/features/chat/ChatWorkspaceContext'
import { renderAnswerWithCitations } from '@/features/evidence/citations'
import {
  SourceCard,
} from '@/features/evidence/SourcesPanel'
import { imageSourceItemsForResult, sourceItemsForResult, sourceMetaLine, sourceOpenUrl } from '@/features/evidence/sourceModel'
import { safeText } from '@/lib/utils'
import type { AgentQueryResponse } from '@/lib/types'

export function EvidencePage() {
  const workspace = useChatWorkspace()
  const message = workspace.selectedAssistantMessage
  const result = workspace.selectedResult
  const activeCitation = workspace.activeCitation
  const activeIndex = activeCitation && activeCitation.messageId === message?.id ? activeCitation.index : null
  const mediaCount = result ? imageSourceItemsForResult(result).length + tableEvidenceSources(result).length : 0

  if (workspace.messagesError) {
    return <Panel><RetryState title="证据加载失败" error={workspace.messagesError} onRetry={() => void workspace.retryMessages()} /></Panel>
  }
  if (workspace.isWorkspaceLoading && !message) return <Panel><LoadingState label="正在加载所选回答证据..." /></Panel>

  return (
    <Panel>
      <PanelHeader className="compact-header">
        <div>
          <h2>证据溯源</h2>
          <p>{message ? '展示当前所选 Agent 回答的独立证据集。' : '请先在智能问答中选择一条 Agent 回答。'}</p>
        </div>
        <Badge>{mediaCount} 条媒体证据</Badge>
        {activeIndex ? <Button size="sm" variant="secondary" onClick={workspace.clearCitation}>取消高亮</Button> : null}
      </PanelHeader>
      {!message ? <EmptyState title="未选择回答" description="返回智能问答并点击一条 Agent 回答。" /> : null}
      {message && !result ? (
        <EmptyState title={message.pending ? '回答仍在生成' : '该回答没有结果元数据'} description="收到最终 metadata 后再查看证据。" />
      ) : null}
      {result && !result.sources.length ? <EmptyState title="该回答未返回来源" /> : null}
      {result?.sources.length ? (
        <div className="evidence-grid">
          {sourceItemsForResult(result).map((item) => (
            <SourceCard
              active={activeIndex === item.displayIndex}
              citationLinked={item.hasCitation}
              index={item.displayIndex}
              key={`${message?.id}-${item.sourceIndex}-${item.displayIndex}`}
              messageId={message?.id || 'unknown'}
              onSelect={workspace.selectSource}
              source={item.source}
            />
          ))}
          <EvidenceMedia result={result} />
        </div>
      ) : null}
    </Panel>
  )
}

function EvidenceMedia({ result }: { result: AgentQueryResponse }) {
  const figures = imageSourceItemsForResult(result)
  const tables = tableEvidenceSources(result)
  return (
    <>
      {figures.map(({ source, imageUrl }, index) => (
        <article className="evidence-card media-card" key={`figure-${imageUrl}-${index}`}>
          <div className="evidence-card-head"><Badge>Figure {index + 1}</Badge><span>{sourceMetaLine(source)}</span></div>
          <img alt={source.caption || source.title} src={imageUrl} />
          <strong>{source.caption || safeText(source.title, '未命名图片')}</strong>
          <OriginalDocumentLink source={source} />
        </article>
      ))}
      {tables.map((source, index) => (
        <article className="evidence-card table-evidence-card" key={`table-${source.chunk_id || source.source_id || index}`}>
          <div className="evidence-card-head"><Badge>Table {index + 1}</Badge><span>{sourceMetaLine(source)}</span></div>
          <strong>{source.title}</strong>
          <div className="table-evidence-content">
            {renderAnswerWithCitations(source.table_content || source.content || '暂无表格内容', null, () => undefined)}
          </div>
          <OriginalDocumentLink source={source} />
        </article>
      ))}
    </>
  )
}

function OriginalDocumentLink({ source }: { source: AgentQueryResponse['sources'][number] }) {
  const url = sourceOpenUrl(source)
  if (!url) return null
  return <a className="source-open-link" href={url} target="_blank" rel="noreferrer"><ExternalLink size={14} />打开原文</a>
}

function tableEvidenceSources(result: AgentQueryResponse) {
  if (result.refused) return []
  const seen = new Set<string | number>()
  return result.sources.filter((source) => source.chunk_type === 'table' || Boolean(source.table_content)).filter((source) => {
    const key = source.source_id || source.chunk_id || source.title
    if (seen.has(key)) return false
    seen.add(key)
    return true
  }).slice(0, 3)
}
