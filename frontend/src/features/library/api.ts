import { apiJson } from '@/lib/api/client'
import type { DocumentRecord } from '@/lib/types'

type DocumentListPayload = { documents?: DocumentRecord[] }

export async function listDocuments(token: string, signal?: AbortSignal) {
  const payload = await apiJson<DocumentRecord[] | DocumentListPayload>('/documents', { token, signal })
  return Array.isArray(payload) ? payload : payload.documents || []
}
