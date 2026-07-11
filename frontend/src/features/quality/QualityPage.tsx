import { useMutation } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Panel, PanelHeader } from '@/components/ui/panel'
import { EmptyState, LoadingState, RetryState } from '@/components/states'
import { useAuth } from '@/features/auth/AuthContext'
import { useChatWorkspace } from '@/features/chat/ChatWorkspaceContext'
import { chainWarningFromResult } from '@/features/chat/model'
import { judgeAnswer } from '@/features/quality/api'
import { safetyOrRefusalScore } from '@/features/quality/model'
import { isAuthApiError } from '@/lib/api/client'
import type { AgentQueryResponse, JudgeResponse } from '@/lib/types'
import { formatScore } from '@/lib/utils'

type JudgeInput = {
  conversationId: number
  messageId: string
  result: AgentQueryResponse
}

export function QualityPage() {
  const { token, expireSession } = useAuth()
  const workspace = useChatWorkspace()
  const result = workspace.selectedResult
  const message = workspace.selectedAssistantMessage
  const warning = chainWarningFromResult(result)
  const judgeMutation = useMutation({
    mutationFn: (input: JudgeInput) => judgeAnswer(token as string, input.result),
    onSuccess: (judge: JudgeResponse, input: JudgeInput) => {
      workspace.updateMessageResult(input.conversationId, input.messageId, (current) => ({ ...current, ...judge }))
    },
    onError: (error) => {
      if (isAuthApiError(error)) expireSession()
    },
  })

  function runJudge() {
    if (!result || !message || !workspace.activeConversationId) return
    judgeMutation.mutate({ conversationId: workspace.activeConversationId, messageId: message.id, result })
  }

  const scores = result?.judge_scores || {}
  const errorBelongsToSelection = judgeMutation.variables?.messageId === message?.id
  if (workspace.messagesError) return <Panel><RetryState title="质量审阅加载失败" error={workspace.messagesError} onRetry={() => void workspace.retryMessages()} /></Panel>
  if (workspace.isWorkspaceLoading && !message) return <Panel><LoadingState label="正在加载待评测回答..." /></Panel>
  return (
    <Panel>
      <PanelHeader className="quality-header">
        <div><h2>质量审阅</h2><p>评测当前所选回答，结果仅回写该消息的前端缓存。</p></div>
        <Button onClick={runJudge} disabled={!result?.answer || Boolean(warning) || judgeMutation.isPending}>
          {judgeMutation.isPending ? <Loader2 className="spin" size={16} /> : null}运行 Judge
        </Button>
      </PanelHeader>
      {!message ? <EmptyState title="未选择回答" description="返回智能问答并选择要评测的 Agent 回答。" /> : null}
      {message && !result ? <EmptyState title={message.pending ? '回答仍在生成' : '该回答没有可评测结果'} /> : null}
      {result && !result.answer ? <EmptyState title="当前所选回答没有正文" description="无法运行 Judge。" /> : null}
      {warning ? <EmptyState title="当前回答包含链路告警" description="请先重新生成有效回答，再运行 Judge。" /> : null}
      {result?.answer ? (
        <div className="quality-grid">
          <QualityCard title="Faithfulness" score={scores.faithfulness} reason={result.judge_reasons?.faithfulness} />
          <QualityCard title="Citation Support" score={scores.citation_support} reason={result.judge_reasons?.citation_support} />
          <QualityCard title="Answer Coverage" score={scores.answer_coverage} reason={result.judge_reasons?.answer_coverage} />
          <QualityCard title="Safety / Refusal" score={safetyOrRefusalScore(scores)} reason={result.judge_reasons?.safety_leak_check} />
        </div>
      ) : null}
      {judgeMutation.error && errorBelongsToSelection ? (
        <RetryState title="Judge 运行失败" error={judgeMutation.error} onRetry={runJudge} retryLabel="重新评测当前回答" />
      ) : null}
    </Panel>
  )
}

function QualityCard({ title, score, reason }: { title: string; score: unknown; reason?: string }) {
  return <article className="quality-card"><h3>{title}</h3><Badge>{formatScore(score)}</Badge><p>{reason || '待 Judge 回填。'}</p></article>
}
