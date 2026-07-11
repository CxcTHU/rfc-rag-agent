import { apiJson } from '@/lib/api/client'
import type { AgentQueryResponse, JudgeResponse } from '@/lib/types'

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
