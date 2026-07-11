import { ExternalLink } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Panel, PanelHeader } from '@/components/ui/panel'
import { EmptyState, LoadingState, RetryState } from '@/components/states'
import { useChatWorkspace } from '@/features/chat/ChatWorkspaceContext'
import { buildCitationView } from '@/features/evidence/citations'
import { sourceItemsForResult, sourceMetaLine, sourceOpenUrl } from '@/features/evidence/sourceModel'
import { cn, safeText } from '@/lib/utils'
import type { AgentQueryResponse } from '@/lib/types'

export function SourcesPanel() {
  const workspace = useChatWorkspace()
  const message = workspace.selectedAssistantMessage
  const result = workspace.selectedResult
  const activeCitation = workspace.activeCitation
  const activeIndex = activeCitation && activeCitation.messageId === message?.id ? activeCitation.index : null

  return (
    <Panel className="sources-panel" aria-label="回答来源">
      <PanelHeader className="compact-header">
        <div>
          <strong>Sources</strong>
          <p>{sourceSummary(message?.pending, result)}</p>
        </div>
        {activeIndex ? (
          <Button size="sm" variant="secondary" onClick={workspace.clearCitation}>取消高亮</Button>
        ) : null}
      </PanelHeader>
      <div className="source-card-list">
        {workspace.messagesError ? (
          <RetryState compact title="回答来源加载失败" error={workspace.messagesError} onRetry={() => void workspace.retryMessages()} />
        ) : (
          <>
            {!message && workspace.isWorkspaceLoading ? <LoadingState compact label="正在恢复回答来源..." /> : null}
            {!message && !workspace.isWorkspaceLoading ? (
              <EmptyState compact title="未选择回答" description="点击一条 Agent 回答后查看它的来源。" />
            ) : null}
            {message && !result ? (
              <EmptyState
                compact
                title={message.pending ? '回答仍在生成' : '该回答没有结果元数据'}
                description={message.pending ? '收到最终 metadata 后会显示来源。' : '无法从其他回答回退来源。'}
              />
            ) : null}
            {result && !result.sources.length ? (
              <EmptyState compact title="该回答未返回来源" description="不会显示同一会话中其他回答的来源。" />
            ) : null}
            {result ? sourceItemsForResult(result).map((item) => (
              <SourceCard
                active={activeIndex === item.displayIndex}
                citationLinked={item.hasCitation}
                index={item.displayIndex}
                key={`${message?.id}-${item.sourceIndex}-${item.displayIndex}`}
                messageId={message?.id || 'unknown'}
                onSelect={workspace.selectSource}
                source={item.source}
              />
            )) : null}
          </>
        )}
      </div>
    </Panel>
  )
}

function sourceSummary(pending: boolean | undefined, result: AgentQueryResponse | null) {
  if (pending && !result) return '正在等待最终 Agent 结果'
  if (!result) return '选择一条 Agent 回答查看对应来源'
  if (!result.sources.length) return '该回答未返回来源'
  const citationView = buildCitationView(result)
  const invalidSummary = citationView.invalidCitationCount ? ` / ${citationView.invalidCitationCount} 个无效引用` : ''
  return citationView.citationCount
    ? `${citationView.citationCount} 个正文引用 / ${result.sources.length} 个检索来源${invalidSummary}`
    : `${result.sources.length} 个检索来源${invalidSummary}`
}

export function SourceCard({
  active,
  citationLinked,
  index,
  messageId,
  onSelect,
  source,
}: {
  active: boolean
  citationLinked: boolean
  index: number
  messageId: string
  onSelect: (index: number, hasCitation: boolean) => void
  source: AgentQueryResponse['sources'][number]
}) {
  const openUrl = sourceOpenUrl(source)
  return (
    <article className={cn('source-card', active && 'active')} id={`source-card-${messageId}-${index}`}>
      <button className="source-card-title" type="button" onClick={() => onSelect(index, citationLinked)}>
        <Badge className="source-index-badge">{citationLinked ? `[${index}]` : '仅检索'}</Badge>
        <span>{safeText(source.title, '未命名来源')}</span>
      </button>
      <div className="source-meta-row">
        <Badge className="source-type-badge">{source.source_type || '未知来源'}</Badge>
        {source.chunk_type ? <Badge className="source-type-badge">{source.chunk_type}</Badge> : null}
      </div>
      <p>{sourceMetaLine(source)}</p>
      {openUrl ? (
        <a className="source-open-link" href={openUrl} target="_blank" rel="noreferrer">
          <ExternalLink size={14} />
          <span>打开原文</span>
        </a>
      ) : null}
      {source.image_url ? <img alt={source.caption || source.title} src={source.image_url} /> : null}
    </article>
  )
}
