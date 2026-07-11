import type { AgentQueryResponse } from '@/lib/types'

export type AgentStreamEvent =
  | { type: 'token'; text: string; payload: Record<string, unknown> }
  | { type: 'metadata'; result: AgentQueryResponse; payload: Record<string, unknown> }
  | { type: 'done'; payload: Record<string, unknown> }
  | { type: 'agent_step' | 'tool_call_start' | 'tool_call_result'; payload: Record<string, unknown> }
  | { type: 'heartbeat'; payload: Record<string, unknown> }
  | { type: 'error'; message: string; payload: Record<string, unknown> }
  | { type: 'message'; payload: Record<string, unknown> }

export function parseSseBlock(rawEvent: string): AgentStreamEvent | null {
  const lines = rawEvent.split(/\r?\n/)
  const type = lines.find((line) => line.startsWith('event:'))?.slice(6).trim() || 'message'
  const dataText = lines
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trimStart())
    .join('\n')
  if (!dataText) return null
  const parsed = JSON.parse(dataText) as unknown
  const payload = parsed && typeof parsed === 'object' ? (parsed as Record<string, unknown>) : { value: parsed }
  if (type === 'token') {
    const text = payload.text ?? payload.token ?? payload.content ?? payload.delta ?? ''
    return { type, text: typeof text === 'string' ? text : '', payload }
  }
  if (type === 'metadata') return { type, result: payload as AgentQueryResponse, payload }
  if (type === 'done') return { type, payload }
  if (type === 'agent_step' || type === 'tool_call_start' || type === 'tool_call_result') {
    return { type, payload }
  }
  if (type === 'heartbeat') return { type, payload }
  if (type === 'error') {
    return { type, message: typeof payload.detail === 'string' ? payload.detail : 'Agent stream failed', payload }
  }
  return { type: 'message', payload }
}

export async function consumeSseResponse(
  response: Response,
  onEvent: (event: AgentStreamEvent) => void,
) {
  if (!response.body) throw new Error('Agent stream response has no body')
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  function consumeBuffer(final = false) {
    while (true) {
      const separator = buffer.match(/\r?\n\r?\n/)
      if (!separator || separator.index === undefined) break
      const rawEvent = buffer.slice(0, separator.index)
      buffer = buffer.slice(separator.index + separator[0].length)
      const event = parseSseBlock(rawEvent)
      if (event) onEvent(event)
    }
    if (final && buffer.trim()) {
      const event = parseSseBlock(buffer)
      buffer = ''
      if (event) onEvent(event)
    }
  }

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    consumeBuffer()
  }
  buffer += decoder.decode()
  consumeBuffer(true)
}
