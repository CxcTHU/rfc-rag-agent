import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type FormEvent,
  type ReactNode,
} from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createConversation,
  deleteConversation,
  getConversationMessages,
  listConversations,
  renameConversation,
  uploadAgentImage,
} from '@/features/chat/api'
import { isAuthApiError } from '@/lib/api/client'
import type { AgentQueryResponse, ChatMessage, Conversation } from '@/lib/types'
import { useAuth } from '@/features/auth/AuthContext'
import { ChatWorkspaceContext, type ChatWorkspaceValue } from '@/features/chat/ChatWorkspaceContext'
import { conversationKeys } from '@/features/chat/queryKeys'
import {
  chainWarningFromResult,
  conversationTitleFromQuestion,
  hydrateConversationMessages,
  latestAssistantWithResult,
  resultElapsedMs,
  type ActiveCitation,
  type ChatModelPreset,
  type PendingImage,
} from '@/features/chat/model'
import { sseEventToWorkflowStep } from '@/features/trace/workflow'
import { useAgentStream, type AgentStreamRequest } from '@/features/chat/useAgentStream'

const ACTIVE_CONVERSATION_STORAGE_KEY = 'rfc-rag-agent.activeConversationId'
const PINNED_CONVERSATIONS_STORAGE_KEY = 'rfc-rag-agent.pinnedConversationIds'
const CHAT_MODEL_STORAGE_KEY = 'rfc-rag-agent.chatModel'
const DRAFT_KEY = 'draft'

type ConversationThread = {
  conversation: Conversation
  messages: ChatMessage[]
}

function readPinnedConversationIds() {
  try {
    const value = JSON.parse(window.localStorage.getItem(PINNED_CONVERSATIONS_STORAGE_KEY) || '[]')
    return Array.isArray(value) ? value.filter((item): item is number => Number.isInteger(item)) : []
  } catch {
    return []
  }
}

function readChatModel(): ChatModelPreset {
  return window.localStorage.getItem(CHAT_MODEL_STORAGE_KEY) === 'deepseek-v4-pro'
    ? 'deepseek-v4-pro'
    : 'deepseek-v4-flash'
}

export function ChatWorkspaceProvider({ children }: { children: ReactNode }) {
  const { token, user, expireSession } = useAuth()
  const queryClient = useQueryClient()
  const composerRef = useRef<HTMLTextAreaElement | null>(null)
  const imageInputRef = useRef<HTMLInputElement | null>(null)
  const initializedRef = useRef(false)
  const sessionEpochRef = useRef(0)
  const submittingRef = useRef(false)
  const conversationMutationRef = useRef(false)
  const uploadsRef = useRef(new Set<string>())
  const operationRetryRef = useRef<(() => void) | null>(null)
  const [activeConversationId, setActiveConversationId] = useState<number | undefined>()
  const [isDraft, setIsDraft] = useState(false)
  const [selectedAssistantMessageId, setSelectedAssistantMessageId] = useState<string | null>(null)
  const [activeCitation, setActiveCitation] = useState<ActiveCitation>(null)
  const [question, setQuestion] = useState('')
  const [selectedChatModel, setSelectedChatModelState] = useState<ChatModelPreset>(readChatModel)
  const [pendingImages, setPendingImages] = useState<Record<string, PendingImage | undefined>>({})
  const [uploadingKeys, setUploadingKeys] = useState<Record<string, boolean>>({})
  const [pinnedConversationIds, setPinnedConversationIds] = useState<number[]>(readPinnedConversationIds)
  const [statusByConversation, setStatusByConversation] = useState<Record<number, string>>({})
  const [draftStatus, setDraftStatus] = useState('新对话：发送首个问题后才会创建会话')
  const [submitError, setSubmitError] = useState<unknown>(null)
  const [operationError, setOperationError] = useState<{ title: string; error: unknown; retryLabel: string } | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isConversationMutating, setIsConversationMutating] = useState(false)
  const [now, setNow] = useState(() => Date.now())

  const userId = user?.id
  useEffect(() => () => {
    sessionEpochRef.current += 1
  }, [token, userId])

  const conversationsQuery = useQuery({
    queryKey: conversationKeys.list(userId || 0),
    queryFn: ({ signal }) => listConversations(token as string, signal),
    enabled: Boolean(token && userId),
    staleTime: 15_000,
  })

  const conversations = useMemo(() => {
    const pinOrder = new Map(pinnedConversationIds.map((id, index) => [id, index]))
    return [...(conversationsQuery.data || [])].sort((left, right) => {
      const leftPinned = pinOrder.has(left.id)
      const rightPinned = pinOrder.has(right.id)
      if (leftPinned !== rightPinned) return leftPinned ? -1 : 1
      if (leftPinned && rightPinned) return (pinOrder.get(left.id) || 0) - (pinOrder.get(right.id) || 0)
      return right.id - left.id
    })
  }, [conversationsQuery.data, pinnedConversationIds])

  useEffect(() => {
    if (initializedRef.current || !conversationsQuery.isSuccess) return
    initializedRef.current = true
    const storedId = Number(window.localStorage.getItem(ACTIVE_CONVERSATION_STORAGE_KEY))
    const restored = conversations.find((item) => item.id === storedId) || conversations[0]
    if (restored) {
      setActiveConversationId(restored.id)
      setIsDraft(false)
    } else {
      setIsDraft(true)
    }
  }, [conversations, conversationsQuery.isSuccess])

  const messagesQuery = useQuery({
    queryKey: conversationKeys.messages(userId || 0, activeConversationId || 0),
    queryFn: async ({ signal }) => {
      const response = await getConversationMessages(token as string, activeConversationId as number, signal)
      return {
        conversation: response.conversation,
        messages: hydrateConversationMessages(response.messages),
      } satisfies ConversationThread
    },
    enabled: Boolean(token && userId && activeConversationId),
    staleTime: (query) => {
      const thread = query.state.data as ConversationThread | undefined
      return thread?.messages.some((message) => message.pending) ? Infinity : 30_000
    },
  })

  const messages = activeConversationId ? messagesQuery.data?.messages || [] : []
  const selectedAssistantMessage =
    messages.find((message) => message.id === selectedAssistantMessageId && message.role === 'assistant') || null
  const selectedResult = selectedAssistantMessage?.result || null

  useEffect(() => {
    if (!activeConversationId || !messagesQuery.data) return
    setSelectedAssistantMessageId((current) => {
      if (current && messagesQuery.data.messages.some((message) => message.id === current && message.role === 'assistant')) {
        return current
      }
      setActiveCitation(null)
      return latestAssistantWithResult(messagesQuery.data.messages)?.id || null
    })
  }, [activeConversationId, messagesQuery.data])

  useEffect(() => {
    const error = conversationsQuery.error || messagesQuery.error
    if (error && isAuthApiError(error)) expireSession()
  }, [conversationsQuery.error, expireSession, messagesQuery.error])

  const setThreadMessages = (conversationId: number, updater: (messages: ChatMessage[]) => ChatMessage[]) => {
    if (!userId) return
    queryClient.setQueryData<ConversationThread>(
      conversationKeys.messages(userId, conversationId),
      (current) => current ? { ...current, messages: updater(current.messages) } : current,
    )
  }

  const patchMessage = (request: AgentStreamRequest, updater: (message: ChatMessage) => ChatMessage) => {
    setThreadMessages(request.conversationId, (current) =>
      current.map((message) => message.id === request.assistantMessageId ? updater(message) : message),
    )
  }

  const stream = useAgentStream({
    onToken: (request, text) => {
      patchMessage(request, (message) => ({ ...message, content: `${message.content}${text}` }))
      setStatusByConversation((current) => ({ ...current, [request.conversationId]: 'Agent 正在生成回答...' }))
    },
    onMetadata: (request, result) => {
      patchMessage(request, (message) => ({
        ...message,
        result,
        chainWarning: chainWarningFromResult(result),
      }))
    },
    onAgentEvent: (request, event) => {
      const step = sseEventToWorkflowStep(event)
      if (!step) return
      patchMessage(request, (message) => ({
        ...message,
        events: [...(message.events || []), step].slice(-64),
      }))
      setStatusByConversation((current) => ({ ...current, [request.conversationId]: 'Agent 正在执行真实工作流...' }))
    },
    onHeartbeat: (request) => {
      setStatusByConversation((current) => ({ ...current, [request.conversationId]: 'Agent 连接正常，正在处理...' }))
    },
    onComplete: (request, result) => {
      const completedAt = Date.now()
      patchMessage(request, (message) => ({
        ...message,
        content: result.answer || message.content,
        result,
        pending: false,
        completedAt,
        elapsedMs: resultElapsedMs(result) ?? (message.startedAt ? completedAt - message.startedAt : undefined),
        chainWarning: chainWarningFromResult(result),
      }))
      setStatusByConversation((current) => ({ ...current, [request.conversationId]: '回答已完成' }))
      if (userId) void queryClient.invalidateQueries({ queryKey: conversationKeys.list(userId) })
    },
    onStopped: (request) => {
      const completedAt = Date.now()
      patchMessage(request, (message) => ({
        ...message,
        pending: false,
        completedAt,
        elapsedMs: message.startedAt ? completedAt - message.startedAt : undefined,
        error: message.content ? undefined : '已停止生成',
        chainWarning: '已停止生成，保留当前已接收的内容。',
      }))
      setStatusByConversation((current) => ({ ...current, [request.conversationId]: '已停止生成' }))
    },
    onError: (request, error) => {
      if (isAuthApiError(error)) expireSession()
      patchMessage(request, (message) => ({
        ...message,
        pending: false,
        completedAt: Date.now(),
        error: `生成失败：${error.message}`,
      }))
      setStatusByConversation((current) => ({ ...current, [request.conversationId]: 'Agent 运行失败' }))
    },
    onWarning: (request, warning) => {
      patchMessage(request, (message) => ({ ...message, chainWarning: warning }))
    },
  })
  const stopStream = stream.stop

  useEffect(() => {
    if (!initializedRef.current || !conversationsQuery.isSuccess || isDraft || isSubmitting || isConversationMutating || !activeConversationId) return
    if ((conversationsQuery.data || []).some((conversation) => conversation.id === activeConversationId)) return
    stopStream(activeConversationId)
    const next = conversations[0]
    setSelectedAssistantMessageId(null)
    setActiveCitation(null)
    if (next) {
      setActiveConversationId(next.id)
      persistActiveConversation(next.id)
      setIsDraft(false)
    } else {
      setActiveConversationId(undefined)
      persistActiveConversation()
      setIsDraft(true)
      setDraftStatus('当前会话已不存在，已进入新对话')
    }
  }, [activeConversationId, conversations, conversationsQuery.data, conversationsQuery.isSuccess, isConversationMutating, isDraft, isSubmitting, stopStream])

  useEffect(() => {
    if (!Object.values(stream.runStates).some((state) => state.status === 'connecting' || state.status === 'streaming')) return
    const timer = window.setInterval(() => setNow(Date.now()), 1_000)
    return () => window.clearInterval(timer)
  }, [stream.runStates])

  const createMutation = useMutation({
    mutationFn: (title: string) => createConversation(token as string, title),
  })
  const renameMutation = useMutation({
    mutationFn: (input: { conversationId: number; title: string }) =>
      renameConversation(token as string, input.conversationId, input.title),
  })
  const deleteMutation = useMutation({
    mutationFn: (conversationId: number) => deleteConversation(token as string, conversationId),
  })
  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadAgentImage(token as string, file),
  })

  function activeKey() {
    return activeConversationId ? String(activeConversationId) : DRAFT_KEY
  }

  function persistActiveConversation(conversationId?: number) {
    if (conversationId) window.localStorage.setItem(ACTIVE_CONVERSATION_STORAGE_KEY, String(conversationId))
    else window.localStorage.removeItem(ACTIVE_CONVERSATION_STORAGE_KEY)
  }

  function newDraft() {
    if (submittingRef.current || conversationMutationRef.current || uploadsRef.current.has(activeKey())) return
    initializedRef.current = true
    setActiveConversationId(undefined)
    persistActiveConversation()
    setIsDraft(true)
    setSelectedAssistantMessageId(null)
    setActiveCitation(null)
    setQuestion('')
    setSubmitError(null)
    clearOperationError()
    setDraftStatus('新对话：发送首个问题后才会创建会话')
    setPendingImages((current) => ({ ...current, [DRAFT_KEY]: undefined }))
    window.requestAnimationFrame(() => composerRef.current?.focus())
  }

  function openConversation(conversationId: number) {
    if (submittingRef.current || conversationMutationRef.current || uploadsRef.current.has(activeKey())) return
    initializedRef.current = true
    setActiveConversationId(conversationId)
    persistActiveConversation(conversationId)
    setIsDraft(false)
    setSelectedAssistantMessageId(null)
    setActiveCitation(null)
    setSubmitError(null)
    clearOperationError()
  }

  async function submitQuestion(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault()
    const trimmedQuestion = question.trim()
    if (!trimmedQuestion || !token || !userId) return
    if (submittingRef.current || conversationMutationRef.current || uploadsRef.current.has(activeKey())) return
    if (activeConversationId && stream.isRunning(activeConversationId)) return
    initializedRef.current = true
    submittingRef.current = true
    const submissionEpoch = sessionEpochRef.current
    setIsSubmitting(true)
    setSubmitError(null)
    clearOperationError()
    try {
      let conversationId = activeConversationId
      let threadConversation = conversations.find((item) => item.id === conversationId)
      const sourceAttachmentKey = conversationId ? String(conversationId) : DRAFT_KEY
      const attachment = pendingImages[sourceAttachmentKey]

      if (!conversationId) {
        setDraftStatus('正在创建会话...')
        try {
          await queryClient.cancelQueries({ queryKey: conversationKeys.list(userId) })
          if (sessionEpochRef.current !== submissionEpoch) return
          const created = await createMutation.mutateAsync(conversationTitleFromQuestion(trimmedQuestion))
          if (sessionEpochRef.current !== submissionEpoch) return
          await queryClient.cancelQueries({ queryKey: conversationKeys.list(userId) })
          if (sessionEpochRef.current !== submissionEpoch) return
          conversationId = created.id
          threadConversation = created
          queryClient.setQueryData<Conversation[]>(conversationKeys.list(userId), (current = []) => [
            created,
            ...current.filter((item) => item.id !== created.id),
          ])
          queryClient.setQueryData<ConversationThread>(conversationKeys.messages(userId, created.id), {
            conversation: created,
            messages: [],
          })
          setPendingImages((current) => {
            const next: Record<string, PendingImage | undefined> = { ...current, [DRAFT_KEY]: undefined }
            if (attachment) next[String(created.id)] = attachment
            return next
          })
          setActiveConversationId(created.id)
          persistActiveConversation(created.id)
          setIsDraft(false)
        } catch (error) {
          if (sessionEpochRef.current !== submissionEpoch) return
          if (isAuthApiError(error)) {
            expireSession()
            return
          }
          setSubmitError(error)
          setDraftStatus('会话创建失败，问题与附件已保留')
          void conversationsQuery.refetch()
          return
        }
      }

      if (!conversationId || !threadConversation) return
      await queryClient.cancelQueries({ queryKey: conversationKeys.messages(userId, conversationId) })
      if (sessionEpochRef.current !== submissionEpoch) return
      const userMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'user',
        content: trimmedQuestion,
      }
      const assistantMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: '',
        pending: true,
        startedAt: Date.now(),
        events: [],
      }
      queryClient.setQueryData<ConversationThread>(conversationKeys.messages(userId, conversationId), (current) => ({
        conversation: current?.conversation || threadConversation as Conversation,
        messages: [...(current?.messages || []), userMessage, assistantMessage],
      }))
      setSelectedAssistantMessageId(assistantMessage.id)
      setActiveCitation(null)
      setQuestion('')
      setPendingImages((current) => ({ ...current, [String(conversationId)]: undefined }))
      setStatusByConversation((current) => ({ ...current, [conversationId as number]: '正在连接 Agent...' }))
      void stream.start({
        token,
        conversationId,
        assistantMessageId: assistantMessage.id,
        question: trimmedQuestion,
        imagePath: attachment?.path,
        chatModel: selectedChatModel,
      })
    } finally {
      submittingRef.current = false
      if (sessionEpochRef.current === submissionEpoch) setIsSubmitting(false)
    }
  }

  function reportOperationError(
    title: string,
    error: unknown,
    retry: () => void,
    retryLabel = '重试',
  ) {
    operationRetryRef.current = retry
    setOperationError({ title, error, retryLabel })
  }

  function clearOperationError() {
    operationRetryRef.current = null
    setOperationError(null)
  }

  async function uploadFile(file: File, key: string) {
    if (!token || uploadsRef.current.has(key)) return
    const operationEpoch = sessionEpochRef.current
    uploadsRef.current.add(key)
    setUploadingKeys((current) => ({ ...current, [key]: true }))
    clearOperationError()
    try {
      const uploaded = await uploadMutation.mutateAsync(file)
      if (sessionEpochRef.current !== operationEpoch) return
      setPendingImages((current) => ({ ...current, [key]: { path: uploaded.path, filename: uploaded.filename } }))
    } catch (error) {
      if (sessionEpochRef.current !== operationEpoch) return
      if (isAuthApiError(error)) {
        expireSession()
        return
      }
      reportOperationError('图片上传失败', error, () => { void uploadFile(file, key) }, '重新上传')
    } finally {
      uploadsRef.current.delete(key)
      if (sessionEpochRef.current === operationEpoch) {
        setUploadingKeys((current) => ({ ...current, [key]: false }))
      }
    }
  }

  async function uploadImage(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    await uploadFile(file, activeKey())
  }

  function setSelectedChatModel(value: ChatModelPreset) {
    window.localStorage.setItem(CHAT_MODEL_STORAGE_KEY, value)
    setSelectedChatModelState(value)
  }

  function setPendingImage(image: PendingImage | null) {
    const key = activeKey()
    setPendingImages((current) => ({ ...current, [key]: image || undefined }))
  }

  function selectAssistantMessage(messageId: string) {
    setSelectedAssistantMessageId(messageId)
    setActiveCitation(null)
  }

  function selectCitation(messageId: string, index: number) {
    setSelectedAssistantMessageId(messageId)
    setActiveCitation({ messageId, index })
    window.requestAnimationFrame(() => {
      document.getElementById(`source-card-${messageId}-${index}`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    })
  }

  function selectSource(index: number, hasCitation: boolean) {
    if (!selectedAssistantMessageId) return
    const messageId = selectedAssistantMessageId
    setActiveCitation({ messageId, index })
    if (!hasCitation) return
    window.requestAnimationFrame(() => {
      const selector = `[data-message-id="${CSS.escape(messageId)}"] [data-citation-index="${index}"]`
      document.querySelector<HTMLElement>(selector)?.scrollIntoView({ block: 'center', behavior: 'smooth' })
    })
  }

  function toggleConversationPin(conversationId: number) {
    setPinnedConversationIds((current) => {
      const next = current.includes(conversationId)
        ? current.filter((id) => id !== conversationId)
        : [conversationId, ...current]
      window.localStorage.setItem(PINNED_CONVERSATIONS_STORAGE_KEY, JSON.stringify(next))
      return next
    })
  }

  async function renameConversationById(conversationId: number) {
    if (!token || !userId || conversationMutationRef.current || submittingRef.current) return
    const current = conversations.find((item) => item.id === conversationId)
    const title = window.prompt('请输入新的会话标题', current?.title || '')?.trim()
    if (!title) return
    const operationEpoch = sessionEpochRef.current
    conversationMutationRef.current = true
    setIsConversationMutating(true)
    clearOperationError()
    try {
      await queryClient.cancelQueries({ queryKey: conversationKeys.list(userId) })
      if (sessionEpochRef.current !== operationEpoch) return
      const updated = await renameMutation.mutateAsync({ conversationId, title })
      if (sessionEpochRef.current !== operationEpoch) return
      await queryClient.cancelQueries({ queryKey: conversationKeys.list(userId) })
      if (sessionEpochRef.current !== operationEpoch) return
      queryClient.setQueryData<Conversation[]>(conversationKeys.list(userId), (items = []) =>
        items.map((item) => item.id === conversationId ? updated : item),
      )
      queryClient.setQueryData<ConversationThread>(conversationKeys.messages(userId, conversationId), (thread) =>
        thread ? { ...thread, conversation: updated } : thread,
      )
    } catch (error) {
      if (sessionEpochRef.current !== operationEpoch) return
      if (isAuthApiError(error)) {
        expireSession()
        return
      }
      reportOperationError('会话重命名失败', error, () => { void renameConversationById(conversationId) })
    } finally {
      conversationMutationRef.current = false
      if (sessionEpochRef.current === operationEpoch) setIsConversationMutating(false)
    }
  }

  async function deleteConversationById(conversationId: number) {
    if (!token || !userId || conversationMutationRef.current || submittingRef.current || !window.confirm('确定删除这个会话吗？')) return
    const operationEpoch = sessionEpochRef.current
    conversationMutationRef.current = true
    setIsConversationMutating(true)
    clearOperationError()
    stream.stop(conversationId)
    try {
      await queryClient.cancelQueries({ queryKey: conversationKeys.list(userId) })
      if (sessionEpochRef.current !== operationEpoch) return
      await deleteMutation.mutateAsync(conversationId)
      if (sessionEpochRef.current !== operationEpoch) return
      await queryClient.cancelQueries({ queryKey: conversationKeys.list(userId) })
      if (sessionEpochRef.current !== operationEpoch) return
      const remaining = (conversationsQuery.data || []).filter((item) => item.id !== conversationId)
      queryClient.setQueryData(conversationKeys.list(userId), remaining)
      queryClient.removeQueries({ queryKey: conversationKeys.messages(userId, conversationId), exact: true })
      setPinnedConversationIds((current) => {
        const next = current.filter((id) => id !== conversationId)
        window.localStorage.setItem(PINNED_CONVERSATIONS_STORAGE_KEY, JSON.stringify(next))
        return next
      })
      if (activeConversationId === conversationId) {
        const next = remaining[0]
        if (next) openConversation(next.id)
        else newDraft()
      }
    } catch (error) {
      if (sessionEpochRef.current !== operationEpoch) return
      if (isAuthApiError(error)) {
        expireSession()
        return
      }
      reportOperationError('会话删除失败', error, () => { void deleteConversationById(conversationId) })
    } finally {
      conversationMutationRef.current = false
      if (sessionEpochRef.current === operationEpoch) setIsConversationMutating(false)
    }
  }

  async function refreshWorkspace() {
    if (submittingRef.current || conversationMutationRef.current) return
    const refreshEpoch = sessionEpochRef.current
    const refreshed = await conversationsQuery.refetch()
    if (sessionEpochRef.current !== refreshEpoch) return
    const activeStillExists = !activeConversationId || refreshed.data?.some((item) => item.id === activeConversationId)
    if (activeConversationId && activeStillExists && !stream.isRunning(activeConversationId)) await messagesQuery.refetch()
  }

  function updateSelectedResult(updater: (result: AgentQueryResponse) => AgentQueryResponse) {
    if (!activeConversationId || !selectedAssistantMessageId) return
    updateMessageResult(activeConversationId, selectedAssistantMessageId, updater)
  }

  function updateMessageResult(
    conversationId: number,
    messageId: string,
    updater: (result: AgentQueryResponse) => AgentQueryResponse,
  ) {
    setThreadMessages(conversationId, (current) => current.map((message) => {
      if (message.id !== messageId || !message.result) return message
      const result = updater(message.result)
      return { ...message, result, content: result.answer || message.content }
    }))
  }

  const activeKeyValue = activeConversationId ? String(activeConversationId) : DRAFT_KEY
  const activeConversation = conversations.find((item) => item.id === activeConversationId) || messagesQuery.data?.conversation
  const activeRunState = activeConversationId ? stream.runStates[activeConversationId] : undefined
  const isRunning = activeRunState?.status === 'connecting' || activeRunState?.status === 'streaming'
  const status = activeConversationId
    ? statusByConversation[activeConversationId] || (messagesQuery.isPending ? '正在恢复会话...' : '已加载会话')
    : draftStatus

  const value: ChatWorkspaceValue = {
    conversations,
    activeConversationId,
    activeConversation,
    isDraft,
    isWorkspaceLoading: conversationsQuery.isPending || Boolean(activeConversationId && messagesQuery.isPending),
    conversationsError: conversationsQuery.error,
    messagesError: messagesQuery.error,
    messages,
    selectedAssistantMessageId,
    selectedAssistantMessage,
    selectedResult,
    activeCitation,
    question,
    selectedChatModel,
    pendingImage: pendingImages[activeKeyValue] || null,
    isUploadingImage: Boolean(uploadingKeys[activeKeyValue]),
    isSubmitting,
    isConversationMutating,
    isRunning,
    now,
    status,
    submitError,
    operationError,
    composerRef,
    imageInputRef,
    pinnedConversationIds,
    setQuestion,
    setSelectedChatModel,
    setPendingImage,
    newDraft,
    openConversation,
    submitQuestion,
    stopActiveRun: () => {
      if (activeConversationId) stream.stop(activeConversationId)
    },
    uploadImage,
    selectAssistantMessage,
    selectCitation,
    selectSource,
    clearCitation: () => setActiveCitation(null),
    toggleConversationPin,
    renameConversationById,
    deleteConversationById,
    refreshWorkspace,
    retryMessages: async () => {
      if (!activeConversationId || !stream.isRunning(activeConversationId)) await messagesQuery.refetch()
    },
    retryConversations: async () => { await conversationsQuery.refetch() },
    retryOperation: () => operationRetryRef.current?.(),
    updateSelectedResult,
    updateMessageResult,
  }

  return <ChatWorkspaceContext.Provider value={value}>{children}</ChatWorkspaceContext.Provider>
}
