import type {
  AgentQueryResponse,
  ChatMessage,
  ConversationMessage,
} from '@/lib/types'

export type ChatModelPreset = 'deepseek-v4-flash' | 'deepseek-v4-pro'
export type PendingImage = { path: string; filename: string }
export type ActiveCitation = { messageId: string; index: number } | null

export const emptyResult: AgentQueryResponse = {
  question: '',
  answer: '',
  sources: [],
  citations: [],
  refused: false,
  mode: 'tool_calling_agent',
  workflow_steps: [],
}

export function hydrateConversationMessages(records: ConversationMessage[]): ChatMessage[] {
  let latestUserQuestion = ''
  return records
    .map((record) => {
      const createdAt = record.created_at ? Date.parse(record.created_at) : undefined
      if (record.role === 'user') {
        latestUserQuestion = record.content
        return { id: `stored-${record.id}`, role: 'user' as const, content: record.content }
      }
      if (record.role === 'summary') {
        return { id: `stored-${record.id}`, role: 'system' as const, content: record.content }
      }
      const result = resultFromStoredAssistant(record, latestUserQuestion)
      const elapsedMs = resultElapsedMs(result)
      return {
        id: `stored-${record.id}`,
        role: 'assistant' as const,
        content: result.answer,
        result,
        startedAt: elapsedMs ? createdAt : undefined,
        completedAt: elapsedMs ? createdAt : undefined,
        elapsedMs,
        chainWarning: chainWarningFromResult(result),
      }
    })
    .filter((message) => message.content || message.result) as ChatMessage[]
}

export function resultFromStoredAssistant(record: ConversationMessage, fallbackQuestion = ''): AgentQueryResponse {
  const metadata = (record.metadata || {}) as Partial<AgentQueryResponse>
  return {
    ...emptyResult,
    ...metadata,
    answer: record.content || metadata.answer || '',
    question: metadata.question || fallbackQuestion,
    mode: record.mode || metadata.mode || emptyResult.mode,
    sources: Array.isArray(metadata.sources) ? metadata.sources : [],
    citations: Array.isArray(metadata.citations) ? metadata.citations : [],
    workflow_steps: Array.isArray(metadata.workflow_steps) ? metadata.workflow_steps : [],
    tool_calls: Array.isArray(metadata.tool_calls) ? metadata.tool_calls : [],
    invalid_citations: Array.isArray(metadata.invalid_citations) ? metadata.invalid_citations : [],
    latency_trace: metadata.latency_trace || {},
  }
}

export function latestAssistantWithResult(messages: ChatMessage[]) {
  return [...messages].reverse().find((message) => message.role === 'assistant' && message.result)
}

export function conversationTitleFromQuestion(question: string) {
  const compact = question.replace(/\s+/g, ' ').trim()
  return compact.length > 28 ? `${compact.slice(0, 28)}...` : compact || '新会话'
}

export function resultElapsedMs(result: AgentQueryResponse | null | undefined) {
  if (!result?.latency_trace) return undefined
  for (const key of ['time_to_final_ms', 'total_latency_ms', 'answer_latency_ms']) {
    const value = result.latency_trace[key]
    const numeric = typeof value === 'number' ? value : typeof value === 'string' ? Number(value) : Number.NaN
    if (Number.isFinite(numeric) && numeric >= 0) return numeric
  }
  return undefined
}

export function formatDuration(ms: number) {
  if (!Number.isFinite(ms) || ms <= 0) return '<1秒'
  if (ms < 1000) return '<1秒'
  return `${Math.max(1, Math.round(ms / 1000))}秒`
}

export function chainWarningFromResult(result: AgentQueryResponse | null | undefined) {
  if (!result) return ''
  const trace = result.latency_trace || {}
  const stopReason = typeof trace.runtime_stop_reason === 'string' ? trace.runtime_stop_reason : ''
  if (stopReason.includes('error') || result.refusal_category === 'service_error') {
    return result.refusal_reason || 'Agent 链路未正常完成，请检查运行诊断后重试。'
  }
  return ''
}
