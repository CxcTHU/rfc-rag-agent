import type { AgentQueryResponse, AgentWorkflowStep, ChatMessage } from '@/lib/types'
import type { AgentStreamEvent } from '@/features/chat/sse'

export function sseEventToWorkflowStep(event: AgentStreamEvent): AgentWorkflowStep {
  const payload = event.payload
  const name = typeof payload.tool_name === 'string'
    ? payload.tool_name
    : typeof payload.action === 'string'
      ? payload.action
      : event.type
  return {
    name,
    action: event.type,
    tool_name: typeof payload.tool_name === 'string' ? payload.tool_name : undefined,
    input_summary: stringValue(payload.input_summary),
    output_summary: stringValue(payload.output_summary),
    observation_summary: stringValue(payload.observation_summary),
    step_summary: stringValue(payload.step_summary),
    succeeded: typeof payload.succeeded === 'boolean' ? payload.succeeded : undefined,
    skipped: payload.skipped === true,
    error: stringValue(payload.error) || null,
    client_event_at: Date.now(),
  }
}

export function workflowStepsForMessage(message: ChatMessage) {
  if (message.pending) return normalizeActualSteps(message.events || [])
  const authoritative = message.result?.workflow_steps?.length
    ? message.result.workflow_steps
    : message.result?.tool_calls?.length
      ? message.result.tool_calls
      : message.events || []
  return normalizeActualSteps(authoritative)
}

export function normalizeActualSteps(steps: AgentWorkflowStep[]) {
  return dedupeSteps(mergeToolLifecycle(steps)).filter((step) => stepName(step) !== 'retrieval_diagnostics')
}

function mergeToolLifecycle(steps: AgentWorkflowStep[]) {
  const merged: AgentWorkflowStep[] = []
  const starts = new Map<string, number>()
  for (const step of steps) {
    const event = step.action || step.name
    const tool = step.tool_name || (event === 'tool_call_start' || event === 'tool_call_result' ? step.name : '')
    if (!tool || (event !== 'tool_call_start' && event !== 'tool_call_result')) {
      merged.push(step)
      continue
    }
    if (event === 'tool_call_start') {
      starts.set(tool, merged.length)
      merged.push({ ...step, name: tool })
      continue
    }
    const startIndex = starts.get(tool)
    if (startIndex === undefined) {
      merged.push({ ...step, name: tool })
      continue
    }
    const start = merged[startIndex]
    const startedAt = start.client_event_at
    const completedAt = step.client_event_at
    merged[startIndex] = {
      ...start,
      ...step,
      name: tool,
      input_summary: step.input_summary || start.input_summary,
      client_elapsed_ms:
        typeof startedAt === 'number' && typeof completedAt === 'number' && completedAt >= startedAt
          ? completedAt - startedAt
          : step.client_elapsed_ms,
    }
  }
  return merged
}

function dedupeSteps(steps: AgentWorkflowStep[]) {
  const seen = new Set<string>()
  return steps.filter((step) => {
    const key = [stepName(step), step.input_summary, step.output_summary, step.error].join('|')
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

export function stepName(step: Partial<AgentWorkflowStep>) {
  return String(step.tool_name || step.name || step.action || '')
}

export function stepLabel(step: AgentWorkflowStep) {
  return localizeAgentAction(stepName(step))
}

export function stepSummary(step: AgentWorkflowStep) {
  const summary = step.step_summary || step.observation_summary || step.output_summary || step.input_summary || step.error || ''
  return userFacingAgentSummary(summary, step)
}

export function stepStatusLabel(step: AgentWorkflowStep) {
  if (step.skipped) return '已跳过'
  if (step.succeeded === false) return '失败'
  return '已完成'
}

export function stepDurationLabel(step: AgentWorkflowStep) {
  if (typeof step.client_elapsed_ms !== 'number' || step.client_elapsed_ms < 0) return ''
  return step.client_elapsed_ms < 1000 ? `${Math.round(step.client_elapsed_ms)}ms` : `${Math.max(1, Math.round(step.client_elapsed_ms / 1000))}s`
}

export function currentLiveStepTitle(steps: AgentWorkflowStep[]) {
  const latest = steps[steps.length - 1]
  return latest ? stepLabel(latest) : '等待 Agent 返回运行步骤'
}

export function userFacingAgentSummary(summary: string, context: Partial<AgentWorkflowStep> = {}) {
  const text = String(summary || '')
  const normalized = text.toLowerCase()
  if (!text) return ''
  if (normalized.includes('calling model with tool definitions') || normalized.includes('llm_with_tools')) {
    return '正在分析问题并选择检索工具'
  }
  if (normalized.includes('near-duplicate')) return `已跳过：${localizeAgentAction(stepName(context))}；原因：与已执行检索重复`
  if (normalized.includes('existing evidence available')) return `已跳过：${localizeAgentAction(stepName(context))}；原因：已有可用证据`
  if (normalized.includes('model request failed') || normalized.includes('provider')) return '模型服务暂时不可用，已进入错误处理'
  return stripInternalDiagnostics(text)
}

function stripInternalDiagnostics(text: string) {
  return text
    .replace(/selected_chunk_ids=[^;。\n]+[;。]?/gi, '')
    .replace(/candidate_chunk_ids=[^;。\n]+[;。]?/gi, '')
    .trim()
}

export function retrievalTraceFromResult(result: AgentQueryResponse | null | undefined) {
  const trace = result?.latency_trace || {}
  const selected = arrayValue(trace.retrieval_selected_chunk_ids) || arrayValue(trace.selected_chunk_ids)
  const candidates = arrayValue(trace.retrieval_candidate_chunk_ids) || arrayValue(trace.candidate_chunk_ids)
  if (!selected && !candidates) return null
  return {
    selected: selected?.slice(0, 12) || [],
    candidates: candidates?.slice(0, 12) || [],
  }
}

function arrayValue(value: unknown) {
  return Array.isArray(value) ? value.map(String) : null
}

function stringValue(value: unknown) {
  return typeof value === 'string' ? value : undefined
}

function localizeAgentAction(action: string) {
  const labels: Record<string, string> = {
    agent_step: 'Agent 步骤',
    llm_with_tools: '分析并选择工具',
    hybrid_search_knowledge: '混合检索',
    search_knowledge: '检索知识库',
    search_tables: '检索表格证据',
    search_figures: '检索图片证据',
    analyze_user_image: '分析上传图片',
    answer_with_citations: '引用式回答',
    rewrite_query: '改写查询',
    refuse: '安全拒答',
    final_answer: '最终回答',
  }
  return labels[action] || action || 'Agent 步骤'
}
