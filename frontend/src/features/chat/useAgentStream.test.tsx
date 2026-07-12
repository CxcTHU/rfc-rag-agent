import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAgentStream, type AgentStreamRequest } from '@/features/chat/useAgentStream'

const request: AgentStreamRequest = {
  token: 'fake-test-token',
  conversationId: 7,
  assistantMessageId: 'assistant-7',
  question: '测试问题',
}

function callbacks() {
  return {
    onToken: vi.fn(),
    onMetadata: vi.fn(),
    onAgentEvent: vi.fn(),
    onHeartbeat: vi.fn(),
    onComplete: vi.fn(),
    onStopped: vi.fn(),
    onError: vi.fn(),
    onWarning: vi.fn(),
  }
}

function sseResponse(blocks: string[]) {
  const encoder = new TextEncoder()
  return new Response(new ReadableStream({
    start(controller) {
      blocks.forEach((block) => controller.enqueue(encoder.encode(block)))
      controller.close()
    },
  }), { status: 200 })
}

const metadata = {
  question: '测试问题', answer: '最终回答', sources: [], citations: [], refused: false,
  mode: 'tool_calling_agent', workflow_steps: [],
}

describe('useAgentStream', () => {
  beforeEach(() => vi.unstubAllGlobals())

  it('sends one unified request contract for text and uploaded images', async () => {
    const handlers = callbacks()
    const fetchMock = vi.fn().mockResolvedValue(sseResponse([
      `event: metadata\ndata: ${JSON.stringify(metadata)}\n\n`,
      'event: done\ndata: {}\n\n',
    ]))
    vi.stubGlobal('fetch', fetchMock)
    const { result } = renderHook(() => useAgentStream(handlers))

    await act(async () => {
      await result.current.start({ ...request, imagePath: 'data/user_uploads/2026-07-12/crack.png' })
    })

    const payload = JSON.parse(String(fetchMock.mock.calls[0][1].body))
    expect(payload).toMatchObject({
      question: request.question,
      conversation_id: request.conversationId,
      image_path: 'data/user_uploads/2026-07-12/crack.png',
    })
    expect(payload).not.toHaveProperty('mode')
    expect(payload).not.toHaveProperty('top_k')
    expect(payload).not.toHaveProperty('source_id')
  })

  it('treats metadata as the final result and done only as transport completion', async () => {
    const handlers = callbacks()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(sseResponse([
      'event: token\ndata: {"text":"部分"}\n\n',
      `event: metadata\ndata: ${JSON.stringify(metadata)}\n\n`,
      'event: done\ndata: {}\n\n',
    ])))
    const { result } = renderHook(() => useAgentStream(handlers))
    await act(async () => { await result.current.start(request) })
    expect(handlers.onMetadata).toHaveBeenCalledWith(request, metadata)
    expect(handlers.onComplete).toHaveBeenCalledWith(request, metadata)
    expect(handlers.onError).not.toHaveBeenCalled()
    expect(result.current.runStates[7].status).toBe('completed')
  })

  it('fails when done arrives without metadata', async () => {
    const handlers = callbacks()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(sseResponse(['event: done\ndata: {}\n\n'])))
    const { result } = renderHook(() => useAgentStream(handlers))
    await act(async () => { await result.current.start(request) })
    expect(handlers.onComplete).not.toHaveBeenCalled()
    expect(handlers.onError).toHaveBeenCalledWith(request, expect.objectContaining({ message: 'Stream ended without metadata' }))
    expect(result.current.runStates[7].status).toBe('error')
  })

  it('uses the synchronous fallback only before any SSE event on a recoverable setup failure', async () => {
    const handlers = callbacks()
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response('', { status: 503, statusText: 'Unavailable' }))
      .mockResolvedValueOnce(new Response(JSON.stringify(metadata), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)
    const { result } = renderHook(() => useAgentStream(handlers))
    await act(async () => { await result.current.start(request) })
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(handlers.onComplete).toHaveBeenCalledWith(request, metadata)
  })

  it('stops an in-flight synchronous fallback with the same AbortSignal', async () => {
    const handlers = callbacks()
    let fallbackStarted: (() => void) | undefined
    const started = new Promise<void>((resolve) => { fallbackStarted = resolve })
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response('', { status: 503, statusText: 'Unavailable' }))
      .mockImplementationOnce((_path: string, options: RequestInit) => {
        fallbackStarted?.()
        return new Promise((_resolve, reject) => {
          options.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
        })
      })
    vi.stubGlobal('fetch', fetchMock)
    const { result } = renderHook(() => useAgentStream(handlers))
    await act(async () => {
      const running = result.current.start(request)
      await started
      result.current.stop(request.conversationId)
      await running
    })
    expect(handlers.onStopped).toHaveBeenCalledWith(request)
    expect(handlers.onComplete).not.toHaveBeenCalled()
  })

  it('does not fallback for a non-retryable HTTP response', async () => {
    const handlers = callbacks()
    const fetchMock = vi.fn().mockResolvedValue(new Response('', { status: 422, statusText: 'Invalid' }))
    vi.stubGlobal('fetch', fetchMock)
    const { result } = renderHook(() => useAgentStream(handlers))
    await act(async () => { await result.current.start(request) })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(handlers.onError).toHaveBeenCalled()
  })

  it('preserves 401 as an auth ApiError and never falls back', async () => {
    const handlers = callbacks()
    const fetchMock = vi.fn().mockResolvedValue(new Response('', { status: 401, statusText: 'Unauthorized' }))
    vi.stubGlobal('fetch', fetchMock)
    const { result } = renderHook(() => useAgentStream(handlers))
    await act(async () => { await result.current.start(request) })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(handlers.onError).toHaveBeenCalledWith(request, expect.objectContaining({ status: 401 }))
  })

  it('keeps final metadata and reports a warning when transport fails afterward', async () => {
    const handlers = callbacks()
    const encoder = new TextEncoder()
    let pulled = false
    const response = new Response(new ReadableStream({
      pull(controller) {
        if (!pulled) {
          pulled = true
          controller.enqueue(encoder.encode(`event: metadata\ndata: ${JSON.stringify(metadata)}\n\n`))
          return
        }
        controller.error(new Error('socket reset'))
      },
    }))
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response))
    const { result } = renderHook(() => useAgentStream(handlers))
    await act(async () => { await result.current.start(request) })
    expect(handlers.onWarning).toHaveBeenCalledWith(request, expect.stringContaining('流结束异常'))
    expect(handlers.onComplete).toHaveBeenCalledWith(request, metadata)
    expect(handlers.onError).not.toHaveBeenCalled()
  })

  it('keeps authoritative metadata when the user stops before done or EOF', async () => {
    let metadataSeen: (() => void) | undefined
    const seen = new Promise<void>((resolve) => { metadataSeen = resolve })
    const handlers = { ...callbacks(), onMetadata: vi.fn(() => metadataSeen?.()) }
    const encoder = new TextEncoder()
    vi.stubGlobal('fetch', vi.fn().mockImplementation((_path: string, options: RequestInit) => Promise.resolve(new Response(new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(`event: metadata\ndata: ${JSON.stringify(metadata)}\n\n`))
        options.signal?.addEventListener('abort', () => controller.error(new DOMException('Aborted', 'AbortError')))
      },
    })))))
    const { result } = renderHook(() => useAgentStream(handlers))
    await act(async () => {
      const running = result.current.start(request)
      await seen
      result.current.stop(request.conversationId)
      await running
    })
    expect(handlers.onComplete).toHaveBeenCalledWith(request, metadata)
    expect(handlers.onStopped).not.toHaveBeenCalled()
    expect(result.current.runStates[7].status).toBe('completed')
  })

  it('aborts a connecting run without invoking fallback', async () => {
    const handlers = callbacks()
    const fetchMock = vi.fn().mockImplementation((_path: string, options: RequestInit) => new Promise((_resolve, reject) => {
      options.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
    }))
    vi.stubGlobal('fetch', fetchMock)
    const { result } = renderHook(() => useAgentStream(handlers))
    await act(async () => {
      const running = result.current.start(request)
      await Promise.resolve()
      result.current.stop(request.conversationId)
      await running
    })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(handlers.onStopped).toHaveBeenCalledWith(request)
    expect(handlers.onComplete).not.toHaveBeenCalled()
  })

  it('updates independent conversations concurrently', async () => {
    const handlers = callbacks()
    vi.stubGlobal('fetch', vi.fn().mockImplementation((_path: string, options: RequestInit) => {
      const payload = JSON.parse(String(options.body)) as { question: string }
      const perConversationMetadata = { ...metadata, question: payload.question, answer: `回答：${payload.question}` }
      return Promise.resolve(sseResponse([
        `event: metadata\ndata: ${JSON.stringify(perConversationMetadata)}\n\n`,
        'event: done\ndata: {}\n\n',
      ]))
    }))
    const { result } = renderHook(() => useAgentStream(handlers))
    const secondRequest = { ...request, conversationId: 8, assistantMessageId: 'assistant-8', question: '另一个会话' }
    await act(async () => { await Promise.all([result.current.start(request), result.current.start(secondRequest)]) })
    expect(handlers.onComplete).toHaveBeenCalledWith(request, expect.objectContaining({ question: request.question }))
    expect(handlers.onComplete).toHaveBeenCalledWith(secondRequest, expect.objectContaining({ question: secondRequest.question }))
  })
})
