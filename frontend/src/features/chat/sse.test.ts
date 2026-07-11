import { describe, expect, it } from 'vitest'
import { consumeSseResponse, parseSseBlock } from '@/features/chat/sse'

describe('SSE parser', () => {
  it('parses CRLF and multiline data', () => {
    const event = parseSseBlock('event: metadata\r\ndata: {"question":"q",\r\ndata: "answer":"a","sources":[],"citations":[],"refused":false,"mode":"tool_calling_agent","workflow_steps":[]}\r\n')
    expect(event).toMatchObject({ type: 'metadata', result: { question: 'q', answer: 'a' } })
  })

  it('consumes fragmented chunks and all supported event names', async () => {
    const encoded = new TextEncoder().encode([
      'event: token\ndata: {"text":"A"}\n\n',
      'event: agent_step\ndata: {"action":"plan"}\n\n',
      'event: tool_call_start\ndata: {"tool_name":"search_knowledge"}\n\n',
      'event: tool_call_result\ndata: {"tool_name":"search_knowledge","succeeded":true}\n\n',
      'event: heartbeat\ndata: {"at":1}\n\n',
      'event: metadata\ndata: {"question":"q","answer":"A","sources":[],"citations":[],"refused":false,"mode":"tool_calling_agent","workflow_steps":[]}\n\n',
      'event: done\ndata: {}\n\n',
      'event: error\ndata: {"detail":"late"}\n\n',
    ].join(''))
    const chunks = [encoded.slice(0, 17), encoded.slice(17, 91), encoded.slice(91)]
    const response = new Response(new ReadableStream({
      start(controller) {
        chunks.forEach((chunk) => controller.enqueue(chunk))
        controller.close()
      },
    }))
    const events: string[] = []
    await consumeSseResponse(response, (event) => events.push(event.type))
    expect(events).toEqual([
      'token', 'agent_step', 'tool_call_start', 'tool_call_result', 'heartbeat', 'metadata', 'done', 'error',
    ])
  })
})
