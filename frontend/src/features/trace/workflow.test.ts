import { describe, expect, it } from 'vitest'
import { hydrateConversationMessages } from '@/features/chat/model'
import { stepLabel, stepSummary, workflowStepsForMessage } from '@/features/trace/workflow'
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

  it('reconciles completed metadata into captured SSE steps without replacing live state', () => {
    const message: ChatMessage = {
      id: 'assistant-2', role: 'assistant', content: '', pending: true,
      events: [{
        name: 'hybrid_search_knowledge', action: 'tool_call_result', step_id: 'call-1',
        output_summary: 'returned 6 hybrid results',
      }],
    }
    expect(workflowStepsForMessage(message).map((step) => step.name)).toEqual(['hybrid_search_knowledge'])
    message.pending = false
    message.result = {
      question: 'q', answer: 'a', sources: [], citations: [], refused: false,
      mode: 'tool_calling_agent', workflow_steps: [
        {
          name: 'hybrid_search_knowledge', step_id: 'call-1',
          output_summary: 'returned 11 hybrid results',
        },
        { name: 'final_answer', step_id: 'final', step_summary: '真实完成步骤' },
      ],
    }
    const steps = workflowStepsForMessage(message)
    expect(steps.map((step) => step.name)).toEqual(['hybrid_search_knowledge', 'final_answer'])
    expect(steps[0].output_summary).toBe('returned 6 hybrid results')
  })

  it('shows a user-facing final-model wait state after evidence is sufficient', () => {
    const step = {
      name: 'final_answer_generating',
      action: 'agent_step',
      step_summary: 'waiting_final_model',
    }

    expect(stepLabel(step)).toBe('正在生成最终回答')
    expect(stepSummary(step)).toBe('正在等待最终模型返回')
  })

  it('restores the complete persisted runtime after a conversation reload', () => {
    const message = hydrateConversationMessages([
      { id: 1, conversation_id: 1, role: 'user', content: 'q' },
      {
        id: 2,
        conversation_id: 1,
        role: 'assistant',
        content: 'answer',
        mode: 'tool_calling_agent',
        metadata: {
          sources: [], citations: [], refused: false,
          mode: 'tool_calling_agent',
          workflow_steps: [
            { name: 'hybrid_search_knowledge', step_id: 'call-1' },
            { name: 'final_answer', step_id: 'final' },
          ],
          runtime_workflow_steps: [
            { name: 'llm_with_tools', action: 'agent_step', step_summary: 'planning' },
            {
              name: 'hybrid_search_knowledge', action: 'tool_call_start',
              tool_name: 'hybrid_search_knowledge', step_id: 'call-1', input_summary: 'query=q',
            },
            {
              name: 'hybrid_search_knowledge', action: 'tool_call_result',
              tool_name: 'hybrid_search_knowledge', step_id: 'call-1',
              observation_summary: 'returned 6 results', succeeded: true,
            },
            { name: 'final_answer', action: 'agent_step', step_summary: 'completed' },
          ],
        },
      },
    ])[1]

    expect(workflowStepsForMessage(message).map((step) => step.name)).toEqual([
      'llm_with_tools',
      'hybrid_search_knowledge',
      'final_answer',
    ])
  })
})
