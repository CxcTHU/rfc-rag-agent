import { describe, expect, it } from 'vitest'
import { workflowStepsForMessage } from '@/features/trace/workflow'
import type { ChatMessage } from '@/lib/types'

describe('workflowStepsForMessage', () => {
  it('does not synthesize thought steps from latency_trace', () => {
    const message: ChatMessage = {
      id: 'assistant-1',
      role: 'assistant',
      content: 'answer',
      result: {
        question: 'q', answer: 'answer', sources: [], citations: [], refused: false,
        mode: 'tool_calling_agent', workflow_steps: [], tool_calls: [],
        latency_trace: { planner_latency_ms: 12, rerank_latency_ms: 8, answer_latency_ms: 20 },
      },
    }
    expect(workflowStepsForMessage(message)).toEqual([])
  })

  it('uses captured real SSE events while pending and metadata workflow after completion', () => {
    const message: ChatMessage = {
      id: 'assistant-2', role: 'assistant', content: '', pending: true,
      events: [{ name: 'search_knowledge', action: 'tool_call_start' }],
    }
    expect(workflowStepsForMessage(message).map((step) => step.name)).toEqual(['search_knowledge'])
    message.pending = false
    message.result = {
      question: 'q', answer: 'a', sources: [], citations: [], refused: false,
      mode: 'tool_calling_agent', workflow_steps: [{ name: 'final_answer', step_summary: '真实完成步骤' }],
    }
    expect(workflowStepsForMessage(message).map((step) => step.name)).toEqual(['final_answer'])
  })
})
