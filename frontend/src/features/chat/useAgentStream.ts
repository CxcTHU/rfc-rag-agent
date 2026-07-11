import { useCallback, useEffect, useRef, useState } from 'react'
import { runAgentQuery } from '@/features/chat/api'
import { ApiError } from '@/lib/api/client'
import type { AgentQueryResponse } from '@/lib/types'
import { consumeSseResponse, type AgentStreamEvent } from '@/features/chat/sse'

export type AgentStreamRequest = {
  token: string
  conversationId: number
  assistantMessageId: string
  question: string
  imagePath?: string | null
  chatModel?: string
}

export type AgentStreamRunStatus = 'connecting' | 'streaming' | 'completed' | 'stopped' | 'error'

export type AgentStreamRunState = {
  runId: string
  status: AgentStreamRunStatus
  error?: string
  warning?: string
}

type AgentStreamCallbacks = {
  onToken: (request: AgentStreamRequest, text: string) => void
  onMetadata: (request: AgentStreamRequest, result: AgentQueryResponse) => void
  onAgentEvent: (request: AgentStreamRequest, event: AgentStreamEvent) => void
  onHeartbeat?: (request: AgentStreamRequest) => void
  onComplete: (request: AgentStreamRequest, result: AgentQueryResponse) => void
  onStopped: (request: AgentStreamRequest) => void
  onError: (request: AgentStreamRequest, error: Error) => void
  onWarning?: (request: AgentStreamRequest, warning: string) => void
}

class StreamFailure extends Error {
  recoverable: boolean

  constructor(message: string, recoverable: boolean) {
    super(message)
    this.name = 'StreamFailure'
    this.recoverable = recoverable
  }
}

export function useAgentStream(callbacks: AgentStreamCallbacks) {
  const callbacksRef = useRef(callbacks)
  callbacksRef.current = callbacks
  const controllersRef = useRef(new Map<number, { controller: AbortController; runId: string; request: AgentStreamRequest }>())
  const [runStates, setRunStates] = useState<Record<number, AgentStreamRunState>>({})

  const patchRunState = useCallback((conversationId: number, runId: string, patch: Partial<AgentStreamRunState>) => {
    setRunStates((previous) => {
      if (previous[conversationId]?.runId && previous[conversationId].runId !== runId) return previous
      const previousState = previous[conversationId]
      return {
        ...previous,
        [conversationId]: {
          ...previousState,
          runId,
          status: previousState?.status || 'connecting',
          ...patch,
        },
      }
    })
  }, [])

  const start = useCallback(async (request: AgentStreamRequest) => {
    if (controllersRef.current.has(request.conversationId)) return
    const runId = crypto.randomUUID()
    const controller = new AbortController()
    controllersRef.current.set(request.conversationId, { controller, runId, request })
    patchRunState(request.conversationId, runId, { status: 'connecting', error: undefined, warning: undefined })
    let receivedAnyEvent = false
    let metadata: AgentQueryResponse | null = null
    let finishedByDone = false
    let tokenBuffer = ''
    let frameId: number | null = null

    const flushTokens = () => {
      if (frameId !== null) {
        window.cancelAnimationFrame(frameId)
        frameId = null
      }
      if (!tokenBuffer) return
      const text = tokenBuffer
      tokenBuffer = ''
      callbacksRef.current.onToken(request, text)
    }
    const scheduleTokenFlush = () => {
      if (frameId !== null) return
      frameId = window.requestAnimationFrame(flushTokens)
    }

    try {
      const response = await fetch('/agent/query/stream', {
        method: 'POST',
        signal: controller.signal,
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${request.token}`,
        },
        body: JSON.stringify({
          question: request.question,
          conversation_id: request.conversationId,
          top_k: 8,
          max_tool_calls: 5,
          mode: request.imagePath ? 'react_agent' : 'tool_calling_agent',
          image_path: request.imagePath || null,
          chat_model: request.chatModel || null,
        }),
      })
      if (!response.ok) {
        if (response.status < 500) throw new ApiError(`${response.status} ${response.statusText}`, response.status)
        throw new StreamFailure(`${response.status} ${response.statusText}`, response.status >= 500)
      }
      if (!response.body) throw new StreamFailure('Agent stream response has no body', true)
      patchRunState(request.conversationId, runId, { status: 'streaming' })
      await consumeSseResponse(response, (event) => {
        if (controllersRef.current.get(request.conversationId)?.runId !== runId) return
        receivedAnyEvent = true
        if (event.type === 'token') {
          tokenBuffer += event.text
          scheduleTokenFlush()
          return
        }
        flushTokens()
        if (event.type === 'metadata') {
          metadata = event.result
          callbacksRef.current.onMetadata(request, event.result)
          return
        }
        if (event.type === 'done') {
          finishedByDone = true
          return
        }
        if (event.type === 'heartbeat') {
          callbacksRef.current.onHeartbeat?.(request)
          return
        }
        if (event.type === 'error') throw new StreamFailure(event.message, false)
        if (event.type !== 'message') callbacksRef.current.onAgentEvent(request, event)
      })
      flushTokens()
      if (!metadata) throw new StreamFailure(finishedByDone ? 'Stream ended without metadata' : 'Stream closed without metadata', false)
      callbacksRef.current.onComplete(request, metadata)
      patchRunState(request.conversationId, runId, { status: 'completed' })
    } catch (error) {
      flushTokens()
      if (metadata) {
        if (controller.signal.aborted) {
          callbacksRef.current.onComplete(request, metadata)
          patchRunState(request.conversationId, runId, { status: 'completed' })
        } else {
          const failure = error instanceof StreamFailure
            ? error
            : new StreamFailure(error instanceof Error ? error.message : 'Agent stream failed', false)
          const warning = `流结束异常：${failure.message}`
          callbacksRef.current.onWarning?.(request, warning)
          callbacksRef.current.onComplete(request, metadata)
          patchRunState(request.conversationId, runId, { status: 'completed', warning })
        }
      } else if (controller.signal.aborted) {
        callbacksRef.current.onStopped(request)
        patchRunState(request.conversationId, runId, { status: 'stopped' })
      } else if (error instanceof ApiError) {
        callbacksRef.current.onError(request, error)
        patchRunState(request.conversationId, runId, { status: 'error', error: error.message })
      } else {
        const failure = error instanceof StreamFailure
          ? error
          : new StreamFailure(error instanceof Error ? error.message : 'Agent stream failed', !receivedAnyEvent)
        if (failure.recoverable && !receivedAnyEvent) {
          try {
            const fallback = await runAgentQuery(
              request.token,
              request.question,
              request.conversationId,
              request.imagePath,
              request.chatModel,
              controller.signal,
            )
            if (controller.signal.aborted) throw new DOMException('Aborted', 'AbortError')
            callbacksRef.current.onMetadata(request, fallback)
            callbacksRef.current.onComplete(request, fallback)
            patchRunState(request.conversationId, runId, { status: 'completed' })
          } catch (fallbackError) {
            if (controller.signal.aborted) {
              callbacksRef.current.onStopped(request)
              patchRunState(request.conversationId, runId, { status: 'stopped' })
            } else {
              const normalized = fallbackError instanceof Error ? fallbackError : new Error('Agent 运行失败')
              callbacksRef.current.onError(request, normalized)
              patchRunState(request.conversationId, runId, { status: 'error', error: normalized.message })
            }
          }
        } else {
          callbacksRef.current.onError(request, failure)
          patchRunState(request.conversationId, runId, { status: 'error', error: failure.message })
        }
      }
    } finally {
      if (frameId !== null) window.cancelAnimationFrame(frameId)
      if (controllersRef.current.get(request.conversationId)?.runId === runId) {
        controllersRef.current.delete(request.conversationId)
      }
    }
  }, [patchRunState])

  const stop = useCallback((conversationId: number) => {
    controllersRef.current.get(conversationId)?.controller.abort()
  }, [])

  const stopAll = useCallback(() => {
    controllersRef.current.forEach(({ controller }) => controller.abort())
  }, [])

  useEffect(() => stopAll, [stopAll])

  return {
    start,
    stop,
    stopAll,
    runStates,
    isRunning: (conversationId: number | undefined) => Boolean(conversationId && controllersRef.current.has(conversationId)),
  }
}
