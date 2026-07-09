import type {
  AgentQueryResponse,
  AuthUser,
  Conversation,
  ConversationMessagesResponse,
  DocumentRecord,
  JudgeResponse,
  SourceRecord,
  TokenResponse,
} from '@/lib/types'

const LOCAL_TOKEN_KEY = 'rfc-rag-agent.authToken'
const SESSION_TOKEN_KEY = 'rfc-rag-agent.sessionAuthToken'

export function readStoredToken() {
  return window.localStorage.getItem(LOCAL_TOKEN_KEY) || window.sessionStorage.getItem(SESSION_TOKEN_KEY)
}

export function persistToken(token: string, remember: boolean) {
  const primary = remember ? window.localStorage : window.sessionStorage
  const secondary = remember ? window.sessionStorage : window.localStorage
  primary.setItem(remember ? LOCAL_TOKEN_KEY : SESSION_TOKEN_KEY, token)
  secondary.removeItem(remember ? SESSION_TOKEN_KEY : LOCAL_TOKEN_KEY)
}

export function clearToken() {
  window.localStorage.removeItem(LOCAL_TOKEN_KEY)
  window.sessionStorage.removeItem(SESSION_TOKEN_KEY)
}

type JsonOptions = RequestInit & { token?: string | null }
type ConversationListPayload = { conversations?: Conversation[] }
type SourceListPayload = { sources?: SourceRecord[] }
type DocumentListPayload = { documents?: DocumentRecord[] }
export type UploadedImage = {
  image_id: string
  path: string
  filename: string
  content_type?: string | null
  size_bytes: number
}

export class AgentStreamError extends Error {
  recoverable: boolean

  constructor(message: string, recoverable: boolean) {
    super(message)
    this.name = 'AgentStreamError'
    this.recoverable = recoverable
  }
}

export function isRecoverableAgentStreamError(error: unknown) {
  return error instanceof AgentStreamError && error.recoverable
}

export async function apiJson<T>(path: string, options: JsonOptions = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (!headers.has('Content-Type') && options.body) {
    headers.set('Content-Type', 'application/json')
  }
  if (options.token) {
    headers.set('Authorization', `Bearer ${options.token}`)
  }
  const response = await fetch(path, { ...options, headers })
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`
    try {
      const payload = await response.json()
      message = apiErrorMessage(payload.detail) || message
    } catch {
      // Keep the HTTP status message.
    }
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

function apiErrorMessage(detail: unknown): string {
  if (!detail) return ''
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === 'string') return item
        if (item && typeof item === 'object') {
          const record = item as Record<string, unknown>
          const location = Array.isArray(record.loc) ? record.loc.join('.') : ''
          const msg = typeof record.msg === 'string' ? record.msg : ''
          return [location, msg].filter(Boolean).join(': ')
        }
        return ''
      })
      .filter(Boolean)
      .join('; ')
  }
  if (typeof detail === 'object') {
    const record = detail as Record<string, unknown>
    return typeof record.message === 'string' ? record.message : JSON.stringify(record)
  }
  return String(detail)
}

export function login(username_or_email: string, password: string) {
  return apiJson<TokenResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username_or_email, password }),
  })
}

export function register(username: string, email: string, password: string) {
  return apiJson<AuthUser>('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ username, email, password }),
  })
}

export function currentUser(token: string) {
  return apiJson<AuthUser>('/auth/me', { token })
}

export async function listConversations(token: string) {
  const payload = await apiJson<Conversation[] | ConversationListPayload>('/conversations', { token })
  return Array.isArray(payload) ? payload : payload.conversations || []
}

export function createConversation(token: string, title = '新对话') {
  return apiJson<Conversation>('/conversations', {
    token,
    method: 'POST',
    body: JSON.stringify({ title }),
  })
}

export function renameConversation(token: string, conversationId: number, title: string) {
  return apiJson<Conversation>(`/conversations/${encodeURIComponent(conversationId)}`, {
    token,
    method: 'PATCH',
    body: JSON.stringify({ title }),
  })
}

export function deleteConversation(token: string, conversationId: number) {
  return apiJson<{ conversation_id: number; deleted: boolean }>(`/conversations/${encodeURIComponent(conversationId)}`, {
    token,
    method: 'DELETE',
  })
}

export function getConversationMessages(token: string, conversationId: number) {
  return apiJson<ConversationMessagesResponse>(`/conversations/${encodeURIComponent(conversationId)}/messages`, { token })
}

export function runAgentQuery(token: string, question: string, conversationId?: number, imagePath?: string | null) {
  return apiJson<AgentQueryResponse>('/agent/query', {
    token,
    method: 'POST',
    body: JSON.stringify({
      question,
      conversation_id: conversationId ?? null,
      top_k: 8,
      max_tool_calls: 5,
      mode: imagePath ? 'react_agent' : 'tool_calling_agent',
      image_path: imagePath || null,
    }),
  })
}

export async function streamAgentQuery(
  token: string,
  question: string,
  conversationId: number | undefined,
  imagePath: string | null | undefined,
  handlers: {
    onToken: (token: string) => void
    onMetadata: (metadata: Partial<AgentQueryResponse>) => void
    onDone: (result: AgentQueryResponse) => void
    onAgentEvent?: (event: string, payload: Record<string, unknown>) => void
    onHeartbeat?: (payload: Record<string, unknown>) => void
  },
  signal?: AbortSignal,
) {
  const response = await fetch('/agent/query/stream', {
    method: 'POST',
    signal,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      question,
      conversation_id: conversationId ?? null,
      top_k: 8,
      max_tool_calls: 5,
      mode: imagePath ? 'react_agent' : 'tool_calling_agent',
      image_path: imagePath || null,
    }),
  })
  if (!response.ok || !response.body) {
    throw new AgentStreamError(`${response.status} ${response.statusText}`, true)
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let metadata: AgentQueryResponse | null = null
  let completed = false
  let receivedStreamEvent = false
  const consumeEvent = (rawEvent: string) => {
    const lines = rawEvent.split(/\r?\n/)
    const event = lines.find((line) => line.startsWith('event:'))?.slice(6).trim() || 'message'
    const dataText = lines
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).trim())
      .join('\n')
    if (!dataText) return
    receivedStreamEvent = true
    const payload = JSON.parse(dataText)
    if (event === 'token') {
      const chunk = payload.text ?? payload.token ?? payload.content ?? payload.delta ?? ''
      if (typeof chunk === 'string' && chunk) {
        handlers.onToken(chunk)
      }
    } else if (event === 'metadata') {
      metadata = payload as AgentQueryResponse
      handlers.onMetadata(metadata)
    } else if (event === 'done') {
      completed = true
      if (metadata) {
        handlers.onDone(metadata)
      }
    } else if (event === 'agent_step' || event === 'tool_call_start' || event === 'tool_call_result') {
      handlers.onAgentEvent?.(event, payload)
    } else if (event === 'heartbeat') {
      handlers.onHeartbeat?.(payload)
    } else if (event === 'error') {
      throw new AgentStreamError(payload.detail || 'Agent stream failed', !receivedStreamEvent)
    }
  }
  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const events = buffer.split('\n\n')
      buffer = events.pop() || ''
      for (const rawEvent of events) {
        consumeEvent(rawEvent)
      }
    }
  } catch (error) {
    if (error instanceof AgentStreamError) {
      throw error
    }
    const message = error instanceof Error ? error.message : 'Agent stream failed'
    throw new AgentStreamError(message, !receivedStreamEvent)
  }
  buffer += decoder.decode()
  if (buffer.trim()) {
    const events = `${buffer}\n\n`.split('\n\n')
    for (const rawEvent of events) {
      if (rawEvent.trim()) {
        consumeEvent(rawEvent)
      }
    }
  }
  if (!completed && metadata) {
    handlers.onDone(metadata)
  }
  if (!metadata) {
    throw new AgentStreamError('Stream ended without metadata', !receivedStreamEvent)
  }
}

export function judgeAnswer(token: string, result: AgentQueryResponse) {
  return apiJson<JudgeResponse>('/agent/judge', {
    token,
    method: 'POST',
    body: JSON.stringify({
      question: result.question,
      answer: result.answer,
      sources: result.sources.slice(0, 12).map((source) => ({
        title: source.title,
        content: source.content,
        source_type: source.source_type,
        chunk_id: source.chunk_id,
      })),
      citations: result.citations,
      refused: result.refused,
      refusal_reason: result.refusal_reason,
    }),
  })
}

export async function listSources(token: string) {
  const payload = await apiJson<SourceRecord[] | SourceListPayload>('/sources', { token })
  return Array.isArray(payload) ? payload : payload.sources || []
}

export async function listDocuments(token: string) {
  const payload = await apiJson<DocumentRecord[] | DocumentListPayload>('/documents', { token })
  return Array.isArray(payload) ? payload : payload.documents || []
}

export function syncSources(token: string) {
  return apiJson<{ imported?: number; updated?: number }>('/sources/sync', {
    token,
    method: 'POST',
  })
}

export async function uploadAgentImage(token: string, file: File) {
  const formData = new FormData()
  formData.append('file', file)
  const response = await fetch('/agent/upload-image', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  })
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`
    try {
      const payload = await response.json()
      message = payload.detail || message
    } catch {
      // Keep the HTTP status message.
    }
    throw new Error(message)
  }
  return response.json() as Promise<UploadedImage>
}
