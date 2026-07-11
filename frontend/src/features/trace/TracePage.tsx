import { AlertTriangle } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Panel, PanelHeader } from '@/components/ui/panel'
import { EmptyState, LoadingState, RetryState } from '@/components/states'
import { useChatWorkspace } from '@/features/chat/ChatWorkspaceContext'
import { chainWarningFromResult } from '@/features/chat/model'
import { buildCitationView } from '@/features/evidence/citations'
import {
  retrievalTraceFromResult,
  stepLabel,
  stepSummary,
  workflowStepsForMessage,
} from '@/features/trace/workflow'
import { cn } from '@/lib/utils'

export function TracePage() {
  const workspace = useChatWorkspace()
  const message = workspace.selectedAssistantMessage
  const result = workspace.selectedResult

  if (workspace.messagesError) return <Panel><RetryState title="运行诊断加载失败" error={workspace.messagesError} onRetry={() => void workspace.retryMessages()} /></Panel>
  if (workspace.isWorkspaceLoading && !message) return <Panel><LoadingState label="正在加载运行诊断..." /></Panel>
  if (!message) return <Panel><EmptyState title="未选择回答" description="运行诊断只展示当前所选 Agent 回答的真实数据。" /></Panel>
  if (!result && !message.pending) return <Panel><EmptyState title="该回答没有结果元数据" /></Panel>

  const steps = workflowStepsForMessage(message)
  const trace = result?.latency_trace || {}
  const retrieval = retrievalTraceFromResult(result)
  const warning = chainWarningFromResult(result)
  const citationCount = buildCitationView(result).citationCount

  return (
    <Panel>
      <PanelHeader><h2>运行诊断</h2><p>{result?.question || (message.pending ? '当前回答仍在运行' : '暂无问题')}</p></PanelHeader>
      {warning ? <div className="diagnostic-warning"><AlertTriangle size={18} /><span>{warning}</span></div> : null}
      <div className="trace-metrics">
        <Metric label="状态" value={message.pending ? '运行中' : warning ? '链路告警' : result?.refused ? '已拒答' : result?.answer ? '已完成' : '待回答'} />
        <Metric label="真实步骤" value={steps.length} />
        <Metric label="引用" value={citationCount} />
        <Metric label="Sources" value={result?.sources.length || 0} />
      </div>
      <div className="trace-steps">
        {steps.map((step, index) => (
          <article key={`${step.name}-${index}`} className={cn('trace-step', step.succeeded === false && 'failed')}>
            <Badge>{String(index + 1).padStart(2, '0')}</Badge><h3>{stepLabel(step)}</h3><p>{stepSummary(step)}</p>
          </article>
        ))}
        {!steps.length ? (
          <EmptyState
            title={message.pending ? '等待真实运行事件' : '后端未返回 workflow 或 tool steps'}
            description="前端不会根据 latency_trace 推测或补造思考步骤。"
          />
        ) : null}
      </div>
      {retrieval ? (
        <section className="trace-json" aria-label="检索诊断">
          <strong>检索诊断（不属于思考步骤）</strong>
          <pre>{JSON.stringify(retrieval, null, 2)}</pre>
        </section>
      ) : null}
      <pre className="trace-json">{Object.keys(trace).length ? JSON.stringify(trace, null, 2) : '暂无 latency_trace'}</pre>
    </Panel>
  )
}

function Metric({ label, value }: { label: string; value: number | string }) {
  return <article className="metric-card"><span>{label}</span><strong>{value}</strong></article>
}
