import { ApiError, apiJson } from '@/lib/api/client'
import type { AgentQueryResponse, Conversation, ConversationMessagesResponse } from '@/lib/types'

type ConversationListPayload = { conversations?: Conversation[] }

export type UploadedImage = {
  image_id: string
  path: string
  filename: string
  content_type?: string | null
  size_bytes: number
}

export async function listConversations(token: string, signal?: AbortSignal) {
  const payload = await apiJson<Conversation[] | ConversationListPayload>('/conversations', { token, signal })
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

export function getConversationMessages(token: string, conversationId: number, signal?: AbortSignal) {
  return apiJson<ConversationMessagesResponse>(`/conversations/${encodeURIComponent(conversationId)}/messages`, { token, signal })
}

export function runAgentQuery(
  token: string,
  question: string,
  conversationId?: number,
  imagePath?: string | null,
  chatModel?: string,
  signal?: AbortSignal,
) {
  return apiJson<AgentQueryResponse>('/agent/query', {
    token,
    method: 'POST',
    signal,
    body: JSON.stringify({
      question,
      conversation_id: conversationId ?? null,
      top_k: 8,
      max_tool_calls: 5,
      mode: imagePath ? 'react_agent' : 'tool_calling_agent',
      image_path: imagePath || null,
      chat_model: chatModel || null,
    }),
  })
}

export async function uploadAgentImage(token: string, file: File) {
  const formData = new FormData()
  formData.append('file', file)
  const response = await fetch('/agent/upload-image', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  })
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`
    try {
      const payload = await response.json() as { detail?: unknown }
      if (typeof payload.detail === 'string') message = payload.detail
    } catch {
      // Keep the status-only message.
    }
    throw new ApiError(message, response.status)
  }
  return response.json() as Promise<UploadedImage>
}
