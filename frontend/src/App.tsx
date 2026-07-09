import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import {
  AlertTriangle,
  BookOpen,
  Bot,
  Database,
  ExternalLink,
  FileText,
  FileSearch,
  GitBranch,
  Image as ImageIcon,
  Loader2,
  LogOut,
  Maximize2,
  Play,
  RefreshCcw,
  ShieldCheck,
  Square,
  X,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input, Textarea } from '@/components/ui/input'
import { Panel, PanelHeader } from '@/components/ui/panel'
import {
  clearToken,
  createConversation,
  currentUser,
  deleteConversation,
  getConversationMessages,
  isRecoverableAgentStreamError,
  judgeAnswer,
  listConversations,
  listDocuments,
  login,
  persistToken,
  readStoredToken,
  register,
  renameConversation,
  runAgentQuery,
  streamAgentQuery,
  uploadAgentImage,
} from '@/lib/api/client'
import type {
  AgentQueryResponse,
  AgentWorkflowStep,
  AuthUser,
  ChatMessage,
  Conversation,
  ConversationMessage,
  DocumentRecord,
} from '@/lib/types'
import { cn, formatScore, safeText } from '@/lib/utils'

type ViewName = 'ask' | 'library' | 'evidence' | 'trace' | 'quality'
type AuthMode = 'login' | 'register'
type CitationSourceItem = {
  displayIndex: number
  originalCitation: number
  source: AgentQueryResponse['sources'][number]
  sourceIndex: number
}
type CitationView = {
  citationCount: number
  displayByOriginal: Map<number, number>
  items: CitationSourceItem[]
}

const navItems: Array<{ id: ViewName; label: string; icon: typeof Bot }> = [
  { id: 'ask', label: '智能问答', icon: Bot },
  { id: 'library', label: '语料库', icon: Database },
  { id: 'evidence', label: '证据溯源', icon: FileSearch },
  { id: 'trace', label: '运行诊断', icon: Play },
  { id: 'quality', label: '质量审阅', icon: ShieldCheck },
]

const emptyResult: AgentQueryResponse = {
  question: '',
  answer: '',
  sources: [],
  citations: [],
  refused: false,
  mode: 'tool_calling_agent',
  workflow_steps: [],
}

const ACTIVE_CONVERSATION_STORAGE_KEY = 'rfc-rag-agent.activeConversationId'
const PINNED_CONVERSATIONS_STORAGE_KEY = 'rfc-rag-agent.pinnedConversationIds'
const ACTIVE_VIEW_STORAGE_KEY = 'rfc-rag-agent.activeView'

function readStoredView(): ViewName {
  const stored = window.localStorage.getItem(ACTIVE_VIEW_STORAGE_KEY)
  return navItems.some((item) => item.id === stored) ? (stored as ViewName) : 'ask'
}

function persistView(viewName: ViewName) {
  window.localStorage.setItem(ACTIVE_VIEW_STORAGE_KEY, viewName)
}

function readStoredActiveConversationId() {
  const raw = window.localStorage.getItem(ACTIVE_CONVERSATION_STORAGE_KEY)
  const value = raw ? Number(raw) : Number.NaN
  return Number.isFinite(value) && value > 0 ? value : undefined
}

function persistActiveConversationId(conversationId: number | undefined) {
  if (!conversationId) {
    window.localStorage.removeItem(ACTIVE_CONVERSATION_STORAGE_KEY)
    return
  }
  window.localStorage.setItem(ACTIVE_CONVERSATION_STORAGE_KEY, String(conversationId))
}

function readPinnedConversationIds() {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(PINNED_CONVERSATIONS_STORAGE_KEY) || '[]')
    return Array.isArray(parsed) ? parsed.filter((value): value is number => Number.isFinite(value)) : []
  } catch {
    return []
  }
}

function persistPinnedConversationIds(conversationIds: number[]) {
  window.localStorage.setItem(PINNED_CONVERSATIONS_STORAGE_KEY, JSON.stringify(conversationIds))
}

function App() {
  const [authMode, setAuthMode] = useState<AuthMode>('login')
  const [authChecking, setAuthChecking] = useState(true)
  const [authVisible, setAuthVisible] = useState(false)
  const [rememberMe, setRememberMe] = useState(true)
  const [user, setUser] = useState<AuthUser | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [view, setView] = useState<ViewName>(() => readStoredView())
  const [status, setStatus] = useState('就绪')
  const [loginIdentity, setLoginIdentity] = useState('')
  const [loginPassword, setLoginPassword] = useState('')
  const [registerName, setRegisterName] = useState('')
  const [registerEmail, setRegisterEmail] = useState('')
  const [registerPassword, setRegisterPassword] = useState('')
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [, setMessagesByConversation] = useState<Record<number, ChatMessage[]>>({})
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeConversationId, setActiveConversationId] = useState<number | undefined>()
  const [workspaceHydrating, setWorkspaceHydrating] = useState(false)
  const [pinnedConversationIds, setPinnedConversationIds] = useState<number[]>(() => readPinnedConversationIds())
  const [conversationMenu, setConversationMenu] = useState<{ id: number; x: number; y: number } | null>(null)
  const [documents, setDocuments] = useState<DocumentRecord[]>([])
  const [sourceFilter, setSourceFilter] = useState('')
  const [isRunning, setIsRunning] = useState(false)
  const [isJudgeRunning, setIsJudgeRunning] = useState(false)
  const [isUploadingImage, setIsUploadingImage] = useState(false)
  const [lastResult, setLastResult] = useState<AgentQueryResponse | null>(null)
  const [lastError, setLastError] = useState('')
  const [activeCitation, setActiveCitation] = useState<number | null>(null)
  const [pendingImage, setPendingImage] = useState<{ path: string; filename: string } | null>(null)
  const [now, setNow] = useState(Date.now())
  const loginInputRef = useRef<HTMLInputElement | null>(null)
  const imageInputRef = useRef<HTMLInputElement | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const activeConversationIdRef = useRef<number | undefined>(undefined)
  const messagesByConversationRef = useRef<Record<number, ChatMessage[]>>({})

  // oxlint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    const stored = readStoredToken()
    if (!stored) {
      setAuthChecking(false)
      setStatus('请登录')
      return
    }
    currentUser(stored)
      .then((loadedUser) => {
        setToken(stored)
        setUser(loadedUser)
        setStatus('已连接')
      })
      .catch(() => {
        clearToken()
        setStatus('请登录')
      })
      .finally(() => setAuthChecking(false))
  }, [])

  useEffect(() => {
    if (!token) return
    let cancelled = false
    async function loadInitialWorkspace() {
      setWorkspaceHydrating(true)
      setStatus('正在恢复会话...')
      try {
        const documentDataPromise = listDocuments(token as string).catch(() => [])
        const conversationData = await listConversations(token as string).catch(() => [])
        if (cancelled) return
        const loadedConversations = Array.isArray(conversationData) ? conversationData : []
        setConversations((previous) => mergeConversations(loadedConversations, previous))
        const preferredConversationId = readStoredActiveConversationId()
        const targetConversation =
          loadedConversations.find((conversation) => conversation.id === preferredConversationId) || loadedConversations[0]
        const messageDataPromise =
          !activeConversationIdRef.current && targetConversation
            ? getConversationMessages(token as string, targetConversation.id).catch(() => null)
            : Promise.resolve(null)
        const [documentData, payload] = await Promise.all([documentDataPromise, messageDataPromise])
        if (cancelled) return
        setDocuments(Array.isArray(documentData) ? documentData : [])
        if (payload) {
          const hydrated = hydrateConversationMessages(payload.messages || [])
          setActiveConversationId(payload.conversation.id)
          activeConversationIdRef.current = payload.conversation.id
          persistActiveConversationId(payload.conversation.id)
          setMessages(hydrated)
          updateConversationMessages(payload.conversation.id, hydrated)
          setLastResult(latestResultFromMessages(hydrated))
        }
        setStatus('已连接')
      } catch (error) {
        if (!cancelled) {
          setStatus(error instanceof Error ? error.message : '工作台加载失败')
        }
      } finally {
        if (!cancelled) {
          setWorkspaceHydrating(false)
        }
      }
    }
    loadInitialWorkspace()
    return () => {
      cancelled = true
    }
  }, [token])

  useEffect(() => {
    if (!isRunning) return
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [isRunning])

  useEffect(() => {
    activeConversationIdRef.current = activeConversationId
  }, [activeConversationId])

  useEffect(() => {
    persistView(view)
  }, [view])

  useEffect(() => {
    if (!conversationMenu) return
    function closeMenu() {
      setConversationMenu(null)
    }
    window.addEventListener('click', closeMenu)
    window.addEventListener('keydown', closeMenu)
    return () => {
      window.removeEventListener('click', closeMenu)
      window.removeEventListener('keydown', closeMenu)
    }
  }, [conversationMenu])

  const currentResult = lastResult || emptyResult
  const workflowSteps = agentThoughtStepsFromResult(currentResult)
  const activeNavIndex = Math.max(0, navItems.findIndex((item) => item.id === view))
  const sortedConversations = sortConversationsByPinned(conversations, pinnedConversationIds)

  function revealAuth() {
    setAuthVisible(true)
    window.setTimeout(() => loginInputRef.current?.focus(), 260)
  }

  function updateConversationMessages(
    conversationId: number,
    updater: ChatMessage[] | ((items: ChatMessage[]) => ChatMessage[]),
  ) {
    const previous = messagesByConversationRef.current[conversationId] || []
    const next = typeof updater === 'function' ? updater(previous) : updater
    const nextCache = {
      ...messagesByConversationRef.current,
      [conversationId]: next,
    }
    messagesByConversationRef.current = nextCache
    setMessagesByConversation(nextCache)
    if (activeConversationIdRef.current === conversationId) {
      setMessages(next)
    }
  }

  function clearConversationMessages(conversationId: number) {
    updateConversationMessages(conversationId, [])
  }

  async function refreshWorkspace(nextToken = token, options: { loadInitialConversation?: boolean } = {}) {
    if (!nextToken) return
    try {
      const [conversationData, documentData] = await Promise.all([
        listConversations(nextToken).catch(() => []),
        listDocuments(nextToken).catch(() => []),
      ])
      const loadedConversations = Array.isArray(conversationData) ? conversationData : []
      setConversations((previous) => mergeConversations(loadedConversations, previous))
      setDocuments(Array.isArray(documentData) ? documentData : [])
      if (options.loadInitialConversation && !activeConversationId && loadedConversations.length) {
        await loadConversationMessages(loadedConversations[0].id, nextToken)
      }
      setStatus('已连接')
    } catch (error) {
      setStatus(error instanceof Error ? error.message : '工作台加载失败')
    }
  }

  async function submitAuth(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setLastError('')
    try {
      let responseToken = ''
      let responseUser: AuthUser
      if (authMode === 'login') {
        const response = await login(loginIdentity, loginPassword)
        responseToken = response.access_token
        responseUser = response.user
      } else {
        await register(registerName, registerEmail, registerPassword)
        const response = await login(registerName, registerPassword)
        responseToken = response.access_token
        responseUser = response.user
      }
      persistToken(responseToken, rememberMe)
      setToken(responseToken)
      setUser(responseUser)
      setStatus('已连接')
    } catch (error) {
      setLastError(error instanceof Error ? error.message : '会话加载失败')
    }
  }

  function logout() {
    abortRef.current?.abort()
    clearToken()
    persistActiveConversationId(undefined)
    setToken(null)
    setUser(null)
    setWorkspaceHydrating(false)
    setMessages([])
    messagesByConversationRef.current = {}
    setMessagesByConversation({})
    setPinnedConversationIds([])
    persistPinnedConversationIds([])
    setConversationMenu(null)
    setLastResult(null)
    setAuthVisible(false)
    setStatus('请登录')
  }

  async function newConversation() {
    if (!token) return
    const conversation = await createConversation(token)
    setConversations((items) => [conversation, ...items])
    setActiveConversationId(conversation.id)
    activeConversationIdRef.current = conversation.id
    persistActiveConversationId(conversation.id)
    clearConversationMessages(conversation.id)
    setLastResult(null)
    setActiveCitation(null)
  }

  function toggleConversationPin(conversationId: number) {
    setPinnedConversationIds((previous) => {
      const next = previous.includes(conversationId)
        ? previous.filter((item) => item !== conversationId)
        : [conversationId, ...previous]
      persistPinnedConversationIds(next)
      return next
    })
    setConversationMenu(null)
  }

  async function renameConversationById(conversationId: number) {
    if (!token) return
    const conversation = conversations.find((item) => item.id === conversationId)
    const nextTitle = window.prompt('重命名会话', conversation?.title || '')
    if (!nextTitle?.trim()) {
      setConversationMenu(null)
      return
    }
    try {
      const updated = await renameConversation(token, conversationId, nextTitle.trim())
      setConversations((items) => items.map((item) => (item.id === conversationId ? updated : item)))
      setStatus('会话已重命名')
    } catch (error) {
      setLastError(error instanceof Error ? error.message : '会话重命名失败')
    } finally {
      setConversationMenu(null)
    }
  }

  async function deleteConversationById(conversationId: number) {
    if (!token) return
    const conversation = conversations.find((item) => item.id === conversationId)
    const confirmed = window.confirm(`删除会话“${conversation?.title || `会话 ${conversationId}`}”？`)
    if (!confirmed) {
      setConversationMenu(null)
      return
    }
    try {
      await deleteConversation(token, conversationId)
      delete messagesByConversationRef.current[conversationId]
      setMessagesByConversation({ ...messagesByConversationRef.current })
      setPinnedConversationIds((previous) => {
        const next = previous.filter((item) => item !== conversationId)
        persistPinnedConversationIds(next)
        return next
      })
      const remaining = conversations.filter((item) => item.id !== conversationId)
      setConversations(remaining)
      if (activeConversationIdRef.current === conversationId) {
        const nextConversation = sortConversationsByPinned(remaining, pinnedConversationIds).find((item) => item.id !== conversationId)
        if (nextConversation) {
          await loadConversationMessages(nextConversation.id, token)
        } else {
          setActiveConversationId(undefined)
          activeConversationIdRef.current = undefined
          persistActiveConversationId(undefined)
          setMessages([])
          setLastResult(null)
          setActiveCitation(null)
        }
      }
      setStatus('会话已删除')
    } catch (error) {
      setLastError(error instanceof Error ? error.message : '会话删除失败')
    } finally {
      setConversationMenu(null)
    }
  }

  async function loadConversationMessages(conversationId: number, nextToken = token) {
    if (!nextToken) return
    setLastError('')
    const cachedMessages = messagesByConversationRef.current[conversationId]
    if (cachedMessages?.some((message) => message.pending)) {
      setActiveConversationId(conversationId)
      activeConversationIdRef.current = conversationId
      persistActiveConversationId(conversationId)
      setMessages(cachedMessages)
      setLastResult(latestResultFromMessages(cachedMessages))
      setActiveCitation(null)
      setStatus('Agent 运行中')
      return
    }
    const payload = await getConversationMessages(nextToken, conversationId)
    const hydrated = hydrateConversationMessages(payload.messages || [])
    const latest = latestResultFromMessages(hydrated)
    setActiveConversationId(payload.conversation.id)
    activeConversationIdRef.current = payload.conversation.id
    persistActiveConversationId(payload.conversation.id)
    setMessages(hydrated)
    updateConversationMessages(payload.conversation.id, hydrated)
    setLastResult(latest)
    setActiveCitation(null)
    setConversations((items) => {
      const exists = items.some((item) => item.id === payload.conversation.id)
      return exists ? items.map((item) => (item.id === payload.conversation.id ? payload.conversation : item)) : [payload.conversation, ...items]
    })
    setStatus('已加载会话')
  }

  async function submitQuestion(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!token || !question.trim() || isRunning) return
    const userQuestion = question.trim()
    const startedAt = Date.now()
    let conversationId = activeConversationId
    if (!conversationId) {
      const conversation = await createConversation(token, conversationTitleFromQuestion(userQuestion))
      conversationId = conversation.id
      setActiveConversationId(conversation.id)
      activeConversationIdRef.current = conversation.id
      persistActiveConversationId(conversation.id)
      setConversations((items) => [conversation, ...items.filter((item) => item.id !== conversation.id)])
      clearConversationMessages(conversation.id)
      setLastResult(null)
      setActiveCitation(null)
    }
    setQuestion('')
    const attachment = pendingImage
    const imagePath = attachment?.path || null
    if (attachment) {
      setPendingImage(null)
    }
    setIsRunning(true)
    setNow(startedAt)
    setLastError('')
    setStatus('Agent 运行中')
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: attachment ? `${userQuestion}\n\n[已附加图片：${attachment.filename}]` : userQuestion,
    }
    const assistantId = crypto.randomUUID()
    updateConversationMessages(conversationId, (items) => [
      ...items,
      userMessage,
      { id: assistantId, role: 'assistant', content: '', pending: true, startedAt, events: [] },
    ])
    const controller = new AbortController()
    abortRef.current = controller
    try {
      await streamAgentQuery(
        token,
        userQuestion,
        conversationId,
        imagePath,
        {
          onToken: (chunk) => {
            updateConversationMessages(conversationId, (items) =>
              items.map((message) =>
                message.id === assistantId ? { ...message, content: message.content + chunk } : message,
              ),
            )
          },
          onAgentEvent: (event, payload) => {
            const step = sseEventToWorkflowStep(event, payload)
            updateConversationMessages(conversationId, (items) =>
              items.map((message) =>
                message.id === assistantId ? { ...message, events: [...(message.events || []), step].slice(-8) } : message,
              ),
            )
          },
          onHeartbeat: () => setStatus('Agent 运行中'),
          onMetadata: (metadata) => {
            if (activeConversationIdRef.current === conversationId) {
              setLastResult((previous) => ({ ...(previous || emptyResult), ...metadata } as AgentQueryResponse))
            }
          },
          onDone: (result) => {
            const completedAt = Date.now()
            const elapsedMs = resultElapsedMs(result) ?? completedAt - startedAt
            const warning = chainWarningFromResult(result)
            if (activeConversationIdRef.current === conversationId) {
              setLastResult(result)
            }
            updateConversationMessages(conversationId, (items) =>
              items.map((message) =>
                message.id === assistantId
                  ? {
                      ...message,
                      content: result.answer || message.content,
                      pending: false,
                      completedAt,
                      elapsedMs,
                      result,
                      chainWarning: warning,
                    }
                  : message,
              ),
            )
            setStatus(warning ? 'Agent 完成，但链路有告警' : result.refused ? 'Agent 已拒答' : 'Agent 已完成')
          },
        },
        controller.signal,
      )
    } catch (streamError) {
      const completedAt = Date.now()
      if (controller.signal.aborted) {
        setStatus('Agent 已停止')
        updateConversationMessages(conversationId, (items) =>
          items.map((message) =>
            message.id === assistantId
              ? { ...message, pending: false, completedAt, elapsedMs: completedAt - startedAt, error: '已停止生成' }
              : message,
          ),
        )
      } else if (!isRecoverableAgentStreamError(streamError)) {
        const message = streamError instanceof Error ? streamError.message : 'Agent 运行失败'
        setLastError(message)
        setStatus('Agent 运行失败')
        updateConversationMessages(conversationId, (items) =>
          items.map((item) =>
            item.id === assistantId
              ? { ...item, pending: false, completedAt, elapsedMs: completedAt - startedAt, error: message }
              : item,
          ),
        )
      } else {
        try {
          const result = await runAgentQuery(token, userQuestion, conversationId, imagePath)
          const fallbackCompletedAt = Date.now()
          const elapsedMs = resultElapsedMs(result) ?? fallbackCompletedAt - startedAt
          const warning = chainWarningFromResult(result)
          if (activeConversationIdRef.current === conversationId) {
            setLastResult(result)
          }
          updateConversationMessages(conversationId, (items) =>
            items.map((message) =>
              message.id === assistantId
                ? {
                    ...message,
                    content: result.answer,
                    pending: false,
                    completedAt: fallbackCompletedAt,
                    elapsedMs,
                    result,
                    chainWarning: warning,
                  }
                : message,
            ),
          )
          setStatus(warning ? 'Agent 完成，但链路有告警' : result.refused ? 'Agent 已拒答' : 'Agent 已完成')
        } catch (fallbackError) {
          const message = fallbackError instanceof Error ? fallbackError.message : 'Agent 运行失败'
          setLastError(message || (streamError instanceof Error ? streamError.message : 'Agent 运行失败'))
          setStatus('Agent 运行失败')
          updateConversationMessages(conversationId, (items) =>
            items.map((item) =>
              item.id === assistantId
                ? { ...item, pending: false, completedAt, elapsedMs: completedAt - startedAt, error: message }
                : item,
            ),
          )
        }
      }
    } finally {
      setIsRunning(false)
      abortRef.current = null
    }
  }

  function stopAgent() {
    abortRef.current?.abort()
  }

  async function runJudge() {
    if (!token || !lastResult || isJudgeRunning || chainWarningFromResult(lastResult)) return
    setIsJudgeRunning(true)
    setLastError('')
    try {
      const latestUserQuestion = [...messages].reverse().find((message) => message.role === 'user')?.content || ''
      const judgeTarget = lastResult.question?.trim()
        ? lastResult
        : { ...lastResult, question: latestUserQuestion.trim() }
      if (!judgeTarget.question.trim()) {
        throw new Error('请先完成一次有效 Agent 回答，再运行 Judge。')
      }
      const judged = await judgeAnswer(token, judgeTarget)
      const merged = {
        ...judgeTarget,
        judge_scores: judged.judge_scores,
        judge_reasons: judged.judge_reasons,
        judge_provider: judged.judge_provider,
        judge_model: judged.judge_model,
        judge_status: judged.judge_status,
      }
      setLastResult(merged)
      if (activeConversationId) updateConversationMessages(activeConversationId, (items) =>
        items.map((message) => (message.result === lastResult ? { ...message, result: merged } : message)),
      )
    } catch (error) {
      setLastError(error instanceof Error ? error.message : 'Judge 濠㈡儼绮剧憴?')
    } finally {
      setIsJudgeRunning(false)
    }
  }

  async function handleImageSelected(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!token || !file) return
    if (!file.type.startsWith('image/')) {
      setLastError('请先选择图片文件')
      return
    }
    setIsUploadingImage(true)
    setLastError('')
    try {
      const uploaded = await uploadAgentImage(token, file)
      setPendingImage({ path: uploaded.path, filename: uploaded.filename || file.name })
      setStatus(`已上传图片：${uploaded.filename || file.name}`)
    } catch (error) {
      setLastError(error instanceof Error ? error.message : '图片上传失败')
    } finally {
      setIsUploadingImage(false)
      if (event.target) {
        event.target.value = ''
      }
    }
  }

  function selectCitation(index: number) {
    setActiveCitation(index)
    window.setTimeout(() => {
      document.getElementById(`source-card-${index}`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    }, 30)
  }

  if (authChecking || !user || !token) {
    return (
      <main className={cn('auth-screen', authVisible && 'is-login-visible')}>
        <div className="auth-hero">
          <div className="brand-lockup">
            <span className="brand-mark">R</span>
            <div>
              <strong>RFC-RAG-Agent</strong>
              <small>面向堆石混凝土工程知识的 RAG Agent</small>
            </div>
          </div>
          <section className="auth-copy">
            <h1>
              可追溯的工程知识 <span>AI Agent</span>
            </h1>
            <p>面向堆石混凝土工程资料的检索、引用、证据和审阅工作台。</p>
            <Button type="button" className="auth-start-button" onClick={revealAuth}>
              进入工作台
            </Button>
          </section>
          <div className="auth-capability-grid">
            <article className="auth-capability-card hybrid">
              <div className="capability-demo" aria-hidden="true">
                <div className="hybrid-path top">
                  <span>BM25</span>
                  <i />
                </div>
                <div className="hybrid-path bottom">
                  <span>Vector</span>
                  <i />
                </div>
                <div className="hybrid-core">
                  <Database size={18} />
                  <b>K</b>
                </div>
                <div className="hybrid-rank">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
              <strong>混合检索</strong>
              <span>BM25 + 向量召回，动态 K 与 rerank 排序</span>
            </article>
            <article className="auth-capability-card graph">
              <div className="capability-demo" aria-hidden="true">
                <div className="graph-links" />
                <span className="graph-node node-a">实体</span>
                <span className="graph-node node-b">关系</span>
                <span className="graph-node node-c">机理</span>
                <GitBranch className="graph-icon" size={18} />
              </div>
              <strong>GraphRAG</strong>
              <span>结合实体关系，补全工程机理线索</span>
            </article>
            <article className="auth-capability-card multimodal">
              <div className="capability-demo" aria-hidden="true">
                <div className="modal-stack doc">
                  <FileText size={15} />
                  <span>PDF</span>
                </div>
                <div className="modal-stack image">
                  <ImageIcon size={15} />
                  <span>Image</span>
                </div>
                <div className="modal-stack table">
                  <FileSearch size={15} />
                  <span>Table</span>
                </div>
                <div className="modal-scan" />
              </div>
              <strong>多模态</strong>
              <span>图表与图片证据入链，支持引用溯源</span>
            </article>
          </div>
        </div>
        <Panel className="auth-card">
          <PanelHeader className="auth-card-header">
            <div className="auth-card-kicker">RFC-RAG-Agent</div>
            <h2>{authMode === 'login' ? '登录工作台' : '创建账号'}</h2>
          </PanelHeader>
          <form className="auth-form" onSubmit={submitAuth}>
            <div className="auth-tabs">
              <Button type="button" variant={authMode === 'login' ? 'default' : 'secondary'} onClick={() => setAuthMode('login')}>
                登录
              </Button>
              <Button type="button" variant={authMode === 'register' ? 'default' : 'secondary'} onClick={() => setAuthMode('register')}>
                创建账号
              </Button>
            </div>
            {authMode === 'register' && (
              <>
                <label className="auth-field">
                  <span>用户名</span>
                  <Input value={registerName} onChange={(event) => setRegisterName(event.target.value)} placeholder="EthanCui" />
                </label>
                <label className="auth-field">
                  <span>邮箱</span>
                  <Input value={registerEmail} onChange={(event) => setRegisterEmail(event.target.value)} placeholder="name@example.com" />
                </label>
                <label className="auth-field">
                  <span>密码</span>
                  <Input value={registerPassword} onChange={(event) => setRegisterPassword(event.target.value)} type="password" placeholder="至少 8 位字符" />
                </label>
              </>
            )}
            {authMode === 'login' && (
              <>
                <label className="auth-field">
                  <span>用户名或邮箱</span>
                  <Input ref={loginInputRef} value={loginIdentity} onChange={(event) => setLoginIdentity(event.target.value)} placeholder="输入账号" />
                </label>
                <label className="auth-field">
                  <span>密码</span>
                  <Input value={loginPassword} onChange={(event) => setLoginPassword(event.target.value)} type="password" placeholder="输入密码" />
                </label>
              </>
            )}
            <label className="remember-row">
              <input checked={rememberMe} onChange={(event) => setRememberMe(event.target.checked)} type="checkbox" />
              <span>记住登录状态</span>
            </label>
            <Button type="submit" disabled={authChecking}>
              {authChecking ? <Loader2 className="spin" size={16} /> : null}
              {authMode === 'login' ? '登录' : '创建账号'}
            </Button>
            {lastError ? <p className="error-text">{lastError}</p> : null}
          </form>
        </Panel>
      </main>
    )
  }

  return (
    <main className="app-shell">
      <header className="top-nav">
        <button className="brand-lockup reset-button" type="button" onClick={() => setView('ask')}>
          <span className="brand-mark">R</span>
          <span>
            <strong>RFC-RAG-Agent</strong>
            <small>面向堆石混凝土工程知识的 RAG Agent</small>
          </span>
        </button>
        <nav className="nav-links" style={{ '--active-index': activeNavIndex } as CSSProperties}>
          {navItems.map((item) => {
            const Icon = item.icon
            return (
              <button key={item.id} className={cn(view === item.id && 'active')} type="button" onClick={() => setView(item.id)}>
                <Icon size={15} />
                {item.label}
              </button>
            )
          })}
        </nav>
        <div className="header-actions">
          <Badge className="auth-badge">已登录：{user.username}</Badge>
          <Button variant="secondary" size="sm" onClick={logout}>
            <LogOut size={15} />
            退出登录
          </Button>
          <Button variant="secondary" size="sm" onClick={() => refreshWorkspace()}>
            <RefreshCcw size={15} />
            刷新
          </Button>
        </div>
      </header>

      <section className="workspace-grid">
        {view === 'ask' ? (
          <AskView
            activeConversationId={activeConversationId}
            activeCitation={activeCitation}
            conversationMenu={conversationMenu}
            conversations={sortedConversations}
            deleteConversation={deleteConversationById}
            imageInputRef={imageInputRef}
            isUploadingImage={isUploadingImage}
            isRunning={isRunning}
            isWorkspaceHydrating={workspaceHydrating}
            loadConversationMessages={loadConversationMessages}
            messages={messages}
            newConversation={newConversation}
            now={now}
            onImageSelected={handleImageSelected}
            pendingImage={pendingImage}
            pinnedConversationIds={pinnedConversationIds}
            question={question}
            renameConversation={renameConversationById}
            selectCitation={selectCitation}
            setActiveConversationId={setActiveConversationId}
            setActiveCitation={setActiveCitation}
            setConversationMenu={setConversationMenu}
            setPendingImage={setPendingImage}
            setQuestion={setQuestion}
            status={status}
            stopAgent={stopAgent}
            submitQuestion={submitQuestion}
            toggleConversationPin={toggleConversationPin}
          />
        ) : null}
        {view === 'library' ? (
          <LibraryView
            documents={documents}
            lastError={lastError}
            sourceFilter={sourceFilter}
            setSourceFilter={setSourceFilter}
          />
        ) : null}
        {view === 'evidence' ? (
          <EvidenceView activeCitation={activeCitation} result={currentResult} selectCitation={selectCitation} setActiveCitation={setActiveCitation} />
        ) : null}
        {view === 'trace' ? <TraceView result={currentResult} workflowSteps={workflowSteps} /> : null}
        {view === 'quality' ? (
          <QualityView isJudgeRunning={isJudgeRunning} lastError={lastError} result={currentResult} runJudge={runJudge} />
        ) : null}
      </section>
    </main>
  )
}

function AskView(props: {
  activeConversationId?: number
  activeCitation: number | null
  conversationMenu: { id: number; x: number; y: number } | null
  conversations: Conversation[]
  deleteConversation: (id: number) => void
  imageInputRef: React.RefObject<HTMLInputElement | null>
  isUploadingImage: boolean
  isRunning: boolean
  isWorkspaceHydrating: boolean
  loadConversationMessages: (id: number) => void
  messages: ChatMessage[]
  newConversation: () => void
  now: number
  onImageSelected: (event: React.ChangeEvent<HTMLInputElement>) => void
  pendingImage: { path: string; filename: string } | null
  pinnedConversationIds: number[]
  question: string
  renameConversation: (id: number) => void
  selectCitation: (index: number) => void
  setActiveConversationId: (id: number | undefined) => void
  setActiveCitation: (index: number | null) => void
  setConversationMenu: (menu: { id: number; x: number; y: number } | null) => void
  setPendingImage: (image: { path: string; filename: string } | null) => void
  setQuestion: (value: string) => void
  status: string
  stopAgent: () => void
  submitQuestion: (event: React.FormEvent<HTMLFormElement>) => void
  toggleConversationPin: (id: number) => void
}) {
  const latestResult = [...props.messages].reverse().find((message) => message.result)?.result || emptyResult
  const menuConversation = props.conversationMenu
    ? props.conversations.find((conversation) => conversation.id === props.conversationMenu?.id)
    : undefined
  const messageListRef = useRef<HTMLDivElement | null>(null)
  const shouldStickToBottomRef = useRef(true)
  const latestMessage = props.messages[props.messages.length - 1]
  const messageScrollSignature = [
    props.activeConversationId || 'none',
    props.messages.length,
    latestMessage?.id || 'none',
    latestMessage?.content.length || 0,
    latestMessage?.pending ? 'pending' : 'done',
    latestMessage?.events?.length || 0,
  ].join(':')

  useEffect(() => {
    if (!props.messages.length) return
    const element = messageListRef.current
    if (!element) return
    const forceScroll = !latestMessage?.pending || shouldStickToBottomRef.current
    if (!forceScroll) return
    const frame = window.requestAnimationFrame(() => {
      element.scrollTo({
        top: element.scrollHeight,
        behavior: latestMessage?.pending ? 'smooth' : 'auto',
      })
    })
    return () => window.cancelAnimationFrame(frame)
  }, [latestMessage?.pending, messageScrollSignature, props.messages.length])

  return (
    <div className="ask-layout">
      <Panel className="conversation-panel">
        <PanelHeader className="compact-header">
          <strong>会话记录</strong>
          <Button size="sm" variant="secondary" onClick={props.newConversation}>
            新建
          </Button>
        </PanelHeader>
        <div className="conversation-list">
          {props.conversations.length ? (
            props.conversations.map((conversation) => (
              <button
                key={conversation.id}
                className={cn(
                  'conversation-item',
                  conversation.id === props.activeConversationId && 'active',
                  props.pinnedConversationIds.includes(conversation.id) && 'pinned',
                )}
                type="button"
                onClick={() => props.loadConversationMessages(conversation.id)}
                onContextMenu={(event) => {
                  event.preventDefault()
                  props.setConversationMenu({ id: conversation.id, x: event.clientX, y: event.clientY })
                }}
              >
                <span>{conversation.title || `会话 ${conversation.id}`}</span>
                {props.pinnedConversationIds.includes(conversation.id) ? <Badge className="pinned-badge">置顶</Badge> : null}
              </button>
            ))
          ) : (
            <p className="muted">
              {props.isWorkspaceHydrating ? '正在恢复会话记录...' : '暂无会话。开始提问后，左侧会显示历史对话。'}
            </p>
          )}
        </div>
        {props.conversationMenu && menuConversation ? (
          <div
            className="conversation-context-menu"
            style={{ left: props.conversationMenu.x, top: props.conversationMenu.y }}
            onClick={(event) => event.stopPropagation()}
            onContextMenu={(event) => event.preventDefault()}
          >
            <button type="button" onClick={() => props.toggleConversationPin(menuConversation.id)}>
              {props.pinnedConversationIds.includes(menuConversation.id) ? '取消置顶' : '置顶会话'}
            </button>
            <button type="button" onClick={() => props.renameConversation(menuConversation.id)}>
              重命名
            </button>
            <button className="danger" type="button" onClick={() => props.deleteConversation(menuConversation.id)}>
              删除
            </button>
          </div>
        ) : null}
      </Panel>
      <Panel className="chat-panel">
        <PanelHeader className="chat-header">
          <div>
            <h2>智能问答工作台</h2>
            <p>{props.status}</p>
          </div>
          <Badge className="status-badge">{props.isRunning ? '运行中' : '就绪'}</Badge>
        </PanelHeader>
        <div
          className="message-list"
          ref={messageListRef}
          onScroll={(event) => {
            const element = event.currentTarget
            shouldStickToBottomRef.current = element.scrollHeight - element.scrollTop - element.clientHeight < 120
          }}
        >
          {props.messages.length ? (
            props.messages.map((message) => (
              <MessageBubble
                activeCitation={props.activeCitation}
                key={message.id}
                message={message}
                now={props.now}
                selectCitation={props.selectCitation}
              />
            ))
          ) : (
            <div className="empty-state">
              {props.isWorkspaceHydrating ? '正在恢复最近一次对话...' : null}
            </div>
          )}
        </div>
        <form className="composer" onSubmit={props.submitQuestion}>
          <Textarea
            value={props.question}
            onChange={(event) => props.setQuestion(event.target.value)}
            onKeyDown={(event) => {
              if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing) return
              event.preventDefault()
              event.currentTarget.form?.requestSubmit()
            }}
            placeholder="输入工程知识问题，回车发送，Shift+Enter 换行"
          />
          <input hidden ref={props.imageInputRef} type="file" accept="image/*" onChange={props.onImageSelected} />
          {props.pendingImage ? (
            <div className="attachment-row">
              <span>
                已选择图片：<strong>{props.pendingImage.filename}</strong>
              </span>
              <button type="button" onClick={() => props.setPendingImage(null)}>
                移除
              </button>
            </div>
          ) : null}
          <div className="composer-actions">
            <Button
              disabled={props.isRunning || props.isUploadingImage}
              type="button"
              variant="secondary"
              onClick={() => props.imageInputRef.current?.click()}
            >
              {props.isUploadingImage ? <Loader2 className="spin" size={16} /> : <BookOpen size={16} />}
              {props.isUploadingImage ? '上传中' : '上传图片'}
            </Button>
            {props.isRunning ? (
              <Button type="button" variant="danger" onClick={props.stopAgent}>
                <Square size={16} />
                停止
              </Button>
            ) : (
              <Button type="submit">
                <Play size={16} />
                发送
              </Button>
            )}
          </div>
        </form>
      </Panel>
      <SourcesPanel
        activeCitation={props.activeCitation}
        result={latestResult}
        isHydrating={props.isWorkspaceHydrating}
        selectCitation={props.selectCitation}
        setActiveCitation={props.setActiveCitation}
      />
    </div>
  )
}

function MessageBubble({
  activeCitation,
  message,
  now,
  selectCitation,
}: {
  activeCitation: number | null
  message: ChatMessage
  now: number
  selectCitation: (index: number) => void
}) {
  const isAssistant = message.role === 'assistant'
  const backendElapsed = resultElapsedMs(message.result)
  const wallClockElapsed = message.startedAt ? (message.pending ? now : message.completedAt || now) - message.startedAt : 0
  const elapsed = message.pending ? wallClockElapsed : message.elapsedMs ?? backendElapsed ?? wallClockElapsed
  const hasAssistantTiming =
    isAssistant &&
    (message.pending ||
      typeof message.elapsedMs === 'number' ||
      typeof backendElapsed === 'number' ||
      (typeof message.startedAt === 'number' && typeof message.completedAt === 'number'))
  const steps = finalWorkflowSteps(message)
  const citationView = buildCitationView(message.result, message.content)
  return (
    <article className={cn('message-bubble', message.role, message.chainWarning && 'warning')}>
      <div className="message-title-row">
        <strong>{message.role === 'user' ? 'User' : message.role === 'system' ? 'Summary' : 'Agent'}</strong>
        {isAssistant && message.pending ? <span className="thinking-timer">思考 {formatDuration(elapsed)}</span> : null}
        {isAssistant && !message.pending && hasAssistantTiming ? <span className="thinking-timer done">已处理 {formatDuration(elapsed)}</span> : null}
      </div>
      {message.chainWarning ? (
        <div className="chain-warning">
          <AlertTriangle size={16} />
          <span>{message.chainWarning}</span>
        </div>
      ) : null}
      {message.role === 'assistant' && steps.length ? (
        <ThinkingDetails
          activeCitation={activeCitation}
          citationView={citationView}
          isPending={Boolean(message.pending)}
          selectCitation={selectCitation}
          steps={steps}
        />
      ) : null}
      <div className="message-content">
        {message.error
          ? message.error
          : renderAnswerWithCitations(
              message.content || (message.pending ? '正在思考...' : ''),
              activeCitation,
              selectCitation,
              citationView,
            )}
      </div>
      {message.pending ? <Loader2 className="spin" size={16} /> : null}
      {citationView.citationCount ? <Badge className="citation-count-badge">{citationView.citationCount} 个引用</Badge> : null}
    </article>
  )
}

function ThinkingDetails({
  activeCitation,
  citationView,
  isPending,
  selectCitation,
  steps,
}: {
  activeCitation: number | null
  citationView: CitationView
  isPending: boolean
  selectCitation: (index: number) => void
  steps: AgentWorkflowStep[]
}) {
  const [expanded, setExpanded] = useState(false)
  const latestActiveStepIndex = steps.findLastIndex((step) => !isSkippedAgentStep(step))
  const currentStepIndex = latestActiveStepIndex >= 0 ? latestActiveStepIndex : steps.length - 1
  const currentStep = steps[currentStepIndex]
  const visibleSteps = expanded ? steps : isPending && currentStep ? [currentStep] : []
  return (
    <section className={cn('thinking-details', expanded && 'expanded')}>
      <button
        aria-expanded={expanded}
        className="thinking-summary"
        onClick={() => setExpanded((value) => !value)}
        type="button"
      >
        <span>{isPending ? `\u5f53\u524d\uff1a${stepLabel(currentStep)}` : expanded ? '\u6536\u8d77\u601d\u8003\u8fc7\u7a0b' : '\u67e5\u770b\u601d\u8003\u8fc7\u7a0b'}</span>
        {currentStep ? <small>{expanded ? `${steps.length} \u4e2a\u6b65\u9aa4` : `\u6700\u8fd1\uff1a${stepLabel(currentStep)}`}</small> : null}
      </button>
      <div className={cn('thinking-step-list', !expanded && isPending && 'current-only', expanded && 'expanded')}>
        {visibleSteps.map((step, visibleIndex) => {
          const stepIndex = expanded ? visibleIndex : currentStepIndex
          return (
            <article
              className={cn('thinking-step', step.succeeded === false && 'failed', step.skipped && 'skipped')}
              key={`${step.name}-${stepIndex}-${visibleIndex}`}
            >
              <div className="thinking-step-head">
                <strong>
                  {stepIndex + 1}. {stepLabel(step)}
                </strong>
                <Badge>{stepStatusLabel(step)}</Badge>
              </div>
              <div className="thinking-step-summary">
                {renderAnswerWithCitations(stepSummary(step), activeCitation, selectCitation, citationView)}
              </div>
            </article>
          )
        })}
      </div>
    </section>
  )
}

function SourcesPanel({
  activeCitation,
  isHydrating,
  result,
  selectCitation,
  setActiveCitation,
}: {
  activeCitation: number | null
  isHydrating?: boolean
  result: AgentQueryResponse
  selectCitation: (index: number) => void
  setActiveCitation: (index: number | null) => void
}) {
  const citationView = buildCitationView(result)
  const visibleSources = citationView.items.length
    ? citationView.items
    : result.sources.map((source, index) => ({
        displayIndex: index + 1,
        originalCitation: index + 1,
        source,
        sourceIndex: index,
      }))
  return (
    <Panel className="sources-panel">
      <PanelHeader className="compact-header">
        <div>
          <strong>Sources</strong>
          <p>
            {result.sources.length
              ? citationView.items.length
                ? `${citationView.items.length} 个引用来源 / ${result.sources.length} 个检索来源`
                : `${result.sources.length} 个检索来源`
              : isHydrating
                ? '正在恢复最近一次回答的来源...'
                : '暂无来源，完成一次带证据回答后显示。'}
          </p>
        </div>
        {activeCitation ? (
          <Button size="sm" variant="secondary" onClick={() => setActiveCitation(null)}>
            取消高亮
          </Button>
        ) : null}
      </PanelHeader>
      <div className="source-card-list">
        {visibleSources.length ? (
          visibleSources.map((item) => (
            <SourceCard
              active={activeCitation === item.displayIndex}
              index={item.displayIndex}
              key={`${item.source.chunk_id || item.source.source_id || item.source.title}-${item.sourceIndex}-${item.displayIndex}`}
              onSelect={selectCitation}
              source={item.source}
            />
          ))
        ) : (
          <div className="empty-state compact">
            {isHydrating ? '正在恢复最近一次回答的引用来源...' : '暂无来源。完成一次带证据回答后，这里会显示引用来源。'}
          </div>
        )}
      </div>
    </Panel>
  )
}

function SourceCard({
  active,
  index,
  onSelect,
  source,
}: {
  active: boolean
  index: number
  onSelect: (index: number) => void
  source: AgentQueryResponse['sources'][number]
}) {
  const title = safeText(source.title, '未命名来源')
  const meta = sourceMetaLine(source)
  const openUrl = sourceOpenUrl(source)
  return (
    <article className={cn('source-card', active && 'active')} id={`source-card-${index}`}>
      <button className="source-card-title" type="button" onClick={() => onSelect(index)}>
        <Badge className="source-index-badge">[{index}]</Badge>
        <span>{title}</span>
      </button>
      <div className="source-meta-row">
        <Badge className="source-type-badge">{source.source_type || '未知来源'}</Badge>
        {source.chunk_type ? <Badge className="source-type-badge">{source.chunk_type}</Badge> : null}
      </div>
      <p>{meta}</p>
      {openUrl ? (
        <a className="source-open-link" href={openUrl} target="_blank" rel="noreferrer">
          <ExternalLink size={14} />
          <span>打开原文</span>
        </a>
      ) : null}
      {source.image_url ? <img alt={source.caption || source.title} src={source.image_url} /> : null}
    </article>
  )
}

function LibraryView(props: {
  documents: DocumentRecord[]
  lastError: string
  sourceFilter: string
  setSourceFilter: (value: string) => void
}) {
  const chunkTotal = props.documents.reduce((total, document) => total + Number(document.chunk_count || 0), 0)
  const imported = props.documents.filter((document) => document.status === 'imported').length
  const localFiles = props.documents.filter((document) => document.source_type === 'local_file').length
  const filter = props.sourceFilter.trim().toLowerCase()
  const filteredDocuments = filter
    ? props.documents.filter((document) =>
        [document.title, document.file_name, document.status, document.source_type].some((value) => (value || '').toLowerCase().includes(filter)),
      )
    : props.documents
  return (
    <Panel className="corpus-panel">
      <PanelHeader className="table-toolbar">
        <div>
          <h2>语料库</h2>
          <p>浏览已入库论文和文档，支持直接打开原文。</p>
        </div>
        <Input value={props.sourceFilter} onChange={(event) => props.setSourceFilter(event.target.value)} placeholder="请输入" />
      </PanelHeader>
      {props.lastError ? <p className="error-text">{props.lastError}</p> : null}
      <div className="metrics-row">
        <Metric label="文档数" value={props.documents.length} />
        <Metric label="已导入" value={imported} />
        <Metric label="本地原文" value={localFiles} />
        <Metric label="Chunk 数" value={chunkTotal} />
      </div>
      {!props.documents.length ? (
        <div className="empty-state">暂无语料库数据。请确认 /documents 接口可用并已完成导入。</div>
      ) : null}
      <SectionTitle title="论文文档" description={`${filteredDocuments.length} / ${props.documents.length} 个文档`} />
      <DataTable
        className="corpus-table-wrap"
        columns={['标题', '来源类型', '状态', 'Chunk 数', '操作']}
        rows={filteredDocuments.map((document) => [
          document.open_url ? (
            <a key="title-link" className="table-link" href={document.open_url} target="_blank" rel="noreferrer">
              {document.title}
            </a>
          ) : (
            document.title
          ),
          document.file_name || '-',
          document.status || '-',
          String(document.chunk_count ?? '-'),
          document.open_url ? (
            <a
              key="open-link"
              className="table-action-link"
              href={document.open_url}
              target="_blank"
              rel="noreferrer"
              aria-label={`打开原文：${document.title}`}
            >
              <ExternalLink size={14} />
              <span>打开原文</span>
            </a>
          ) : (
            <span key="missing-original" className="muted-text">无原文</span>
          ),
        ])}
      />
    </Panel>
  )
}

function EvidenceView({
  activeCitation,
  result,
  selectCitation,
  setActiveCitation,
}: {
  activeCitation: number | null
  result: AgentQueryResponse
  selectCitation: (index: number) => void
  setActiveCitation: (index: number | null) => void
}) {
  const citationView = buildCitationView(result)
  const visibleSources = citationView.items.length
    ? citationView.items
    : result.sources.map((source, index) => ({
        displayIndex: index + 1,
        originalCitation: index + 1,
        source,
        sourceIndex: index,
      }))
  const mediaEvidenceCount = imageEvidenceSources(result).length + tableEvidenceSources(result).length
  return (
    <Panel>
      <PanelHeader className="compact-header">
        <div>
          <h2>证据溯源</h2>
          <p>
            {result.sources.length
              ? citationView.items.length
                ? `${citationView.items.length} 个引用来源 / ${result.sources.length} 个检索来源`
                : `${result.sources.length} 个检索来源`
              : '暂无来源，完成一次 Agent 回答后显示。'}
          </p>
        </div>
        <Badge>{mediaEvidenceCount} 条媒体证据</Badge>
        {activeCitation ? (
          <Button size="sm" variant="secondary" onClick={() => setActiveCitation(null)}>
            取消高亮
          </Button>
        ) : null}
      </PanelHeader>
      <div className="evidence-grid">
        {visibleSources.length ? (
          <>
            {visibleSources.map((item) => (
              <SourceCard
                active={activeCitation === item.displayIndex}
                index={item.displayIndex}
                key={`${item.source.chunk_id || item.source.source_id || item.source.title}-${item.sourceIndex}-${item.displayIndex}`}
                onSelect={selectCitation}
                source={item.source}
              />
            ))}
            <EvidenceMedia result={result} />
          </>
        ) : (
          <div className="empty-state">暂无图表或表格证据。完成一次包含图片、表格或 citation 的 Agent 回答后，这里会显示证据卡片。</div>
        )}
      </div>
    </Panel>
  )
}

function EvidenceMedia({ result }: { result: AgentQueryResponse }) {
  const figures = imageEvidenceSources(result)
  const tables = tableEvidenceSources(result)
  if (!figures.length && !tables.length) return null
  return (
    <>
      {figures.map(({ source, imageUrl }, index) => (
        <article className="evidence-card media-card" key={`figure-${imageUrl}-${index}`}>
          <div className="evidence-card-head">
            <Badge>Figure {index + 1}</Badge>
            <span>{figureSourceLine(source, index + 1)}</span>
          </div>
          <img alt={source.caption || source.title} src={imageUrl} />
          <strong>{source.caption || source.title}</strong>
          <OriginalDocumentLink source={source} />
        </article>
      ))}
      {tables.map((source, index) => (
        <article className="evidence-card table-evidence-card" key={`table-${source.chunk_id || source.source_id || index}`}>
          <div className="evidence-card-head">
            <Badge>Table {index + 1}</Badge>
            <span>{sourceMetaLine(source)}</span>
          </div>
          <strong>{source.title}</strong>
          <div className="table-evidence-content">
            {renderAnswerWithCitations(source.table_content || source.content || '暂无表格内容', null, () => undefined)}
          </div>
          <OriginalDocumentLink source={source} />
        </article>
      ))}
    </>
  )
}

function OriginalDocumentLink({ source }: { source: AgentQueryResponse['sources'][number] }) {
  const openUrl = sourceOpenUrl(source)
  if (!openUrl) return null
  return (
    <a className="source-open-link" href={openUrl} target="_blank" rel="noreferrer">
      <ExternalLink size={14} />
      <span>打开原文</span>
    </a>
  )
}

function TraceView({ result, workflowSteps }: { result: AgentQueryResponse; workflowSteps: AgentWorkflowStep[] }) {
  const trace = result.latency_trace || {}
  const warning = chainWarningFromResult(result)
  const citationView = buildCitationView(result)
  return (
    <Panel>
      <PanelHeader>
        <h2>运行诊断</h2>
        <p>{result.question || '暂无问题'}</p>
      </PanelHeader>
      {warning ? (
        <div className="diagnostic-warning">
          <AlertTriangle size={18} />
          <span>{warning}</span>
        </div>
      ) : null}
      <div className="trace-metrics">
        <Metric label="状态" value={warning ? '链路告警' : result.refused ? '已拒答' : result.answer ? '已完成' : '待回答'} />
        <Metric label="Workflow" value={workflowSteps.length} />
        <Metric label="引用" value={citationView.citationCount} />
        <Metric label="Sources" value={result.sources.length} />
      </div>
      <div className="trace-steps">
        {workflowSteps.length ? (
          workflowSteps.map((step, index) => (
            <article key={`${step.name}-${index}`} className={cn('trace-step', step.succeeded === false && 'failed')}>
              <Badge>{String(index + 1).padStart(2, '0')}</Badge>
              <h3>{stepLabel(step)}</h3>
              <p>{stepSummary(step)}</p>
            </article>
          ))
        ) : (
          <div className="empty-state">暂无运行步骤。Agent 思考过程会从 SSE 事件、workflow_steps 或 tool_calls 中生成。</div>
        )}
      </div>
      <pre className="trace-json">{Object.keys(trace).length ? JSON.stringify(trace, null, 2) : '暂无 latency_trace'}</pre>
    </Panel>
  )
}

function QualityView(props: {
  isJudgeRunning: boolean
  lastError: string
  result: AgentQueryResponse
  runJudge: () => void
}) {
  const scores = props.result.judge_scores || {}
  const warning = chainWarningFromResult(props.result)
  const disabledReason = !props.result.answer
    ? '请先完成一次有效 Agent 回答，再运行 Judge。'
    : warning
      ? '当前回答包含链路失败提示，请先修复回答链路后再运行 Judge。'
      : ''
  return (
    <Panel>
      <PanelHeader className="quality-header">
        <div>
          <h2>质量审阅</h2>
          <p>默认评测最近一次有效 Agent 回答。</p>
        </div>
        <Button onClick={props.runJudge} disabled={!props.result.answer || Boolean(warning) || props.isJudgeRunning}>
          {props.isJudgeRunning ? <Loader2 className="spin" size={16} /> : null}
          运行 Judge
        </Button>
      </PanelHeader>
      {disabledReason ? <div className="empty-state">{disabledReason}</div> : null}
      <div className="quality-grid">
        <QualityCard title="Faithfulness" score={scores.faithfulness} reason={props.result.judge_reasons?.faithfulness} />
        <QualityCard title="Citation Support" score={scores.citation_support} reason={props.result.judge_reasons?.citation_support} />
        <QualityCard title="Answer Coverage" score={scores.answer_coverage} reason={props.result.judge_reasons?.answer_coverage} />
        <QualityCard title="Safety / Refusal" score={scores.safety_leak_check || scores.refusal_correctness} reason={props.result.judge_reasons?.safety_leak_check} />
      </div>
      {props.lastError ? <p className="error-text">{props.lastError}</p> : null}
    </Panel>
  )
}

function Metric({ label, value }: { label: number | string; value: number | string }) {
  return (
    <article className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  )
}

function QualityCard({ title, score, reason }: { title: string; score: unknown; reason?: string }) {
  return (
    <article className="quality-card">
      <h3>{title}</h3>
      <Badge>{formatScore(score)}</Badge>
      <p>{reason || '待 Judge 回填。'}</p>
    </article>
  )
}

function SectionTitle({ title, description }: { title: string; description: string }) {
  return (
    <div className="section-title">
      <h3>{title}</h3>
      <span>{description}</span>
    </div>
  )
}

function DataTable({ className, columns, rows }: { className?: string; columns: string[]; rows: ReactNode[][] }) {
  return (
    <div className={cn('data-table-wrap', className)}>
      <table className="data-table">
        <thead>
          <tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr>
        </thead>
        <tbody>
          {rows.length ? (
            rows.map((row, index) => (
              <tr key={`row-${index}`}>
                {row.map((cell, cellIndex) => <td key={`cell-${index}-${cellIndex}`}>{cell}</td>)}
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan={columns.length}>暂无数据</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

function hydrateConversationMessages(records: ConversationMessage[]): ChatMessage[] {
  let latestUserQuestion = ''
  return records
    .map((record) => {
      const createdAt = record.created_at ? Date.parse(record.created_at) : undefined
      if (record.role === 'user') {
        latestUserQuestion = record.content
        return {
          id: `stored-${record.id}`,
          role: 'user' as const,
          content: record.content,
        }
      }
      if (record.role === 'summary') {
        return {
          id: `stored-${record.id}`,
          role: 'system' as const,
          content: record.content,
        }
      }
      const result = resultFromStoredAssistant(record, latestUserQuestion)
      const elapsedMs = resultElapsedMs(result)
      return {
        id: `stored-${record.id}`,
        role: 'assistant' as const,
        content: result.answer,
        result,
        startedAt: elapsedMs ? createdAt : undefined,
        completedAt: elapsedMs ? createdAt : undefined,
        elapsedMs,
        chainWarning: chainWarningFromResult(result),
      }
    })
    .filter((message) => message.content || message.result) as ChatMessage[]
}

function resultFromStoredAssistant(record: ConversationMessage, fallbackQuestion = ''): AgentQueryResponse {
  const metadata = (record.metadata || {}) as Partial<AgentQueryResponse>
  return {
    ...emptyResult,
    ...metadata,
    answer: record.content || metadata.answer || '',
    question: metadata.question || fallbackQuestion,
    mode: record.mode || metadata.mode || emptyResult.mode,
    sources: Array.isArray(metadata.sources) ? metadata.sources : [],
    citations: Array.isArray(metadata.citations) ? metadata.citations : [],
    workflow_steps: Array.isArray(metadata.workflow_steps) ? metadata.workflow_steps : [],
    tool_calls: Array.isArray(metadata.tool_calls) ? metadata.tool_calls : [],
    invalid_citations: Array.isArray(metadata.invalid_citations) ? metadata.invalid_citations : [],
    latency_trace: metadata.latency_trace || {},
  }
}

function latestResultFromMessages(items: ChatMessage[]) {
  return [...items].reverse().find((message) => message.result)?.result || null
}

function mergeConversations(primary: Conversation[], fallback: Conversation[]) {
  const seen = new Set<number>()
  return [...primary, ...fallback].filter((conversation) => {
    if (seen.has(conversation.id)) return false
    seen.add(conversation.id)
    return true
  })
}

function sortConversationsByPinned(conversations: Conversation[], pinnedIds: number[]) {
  const pinnedOrder = new Map(pinnedIds.map((id, index) => [id, index]))
  return [...conversations].sort((left, right) => {
    const leftPinned = pinnedOrder.has(left.id)
    const rightPinned = pinnedOrder.has(right.id)
    if (leftPinned && rightPinned) {
      return (pinnedOrder.get(left.id) || 0) - (pinnedOrder.get(right.id) || 0)
    }
    if (leftPinned) return -1
    if (rightPinned) return 1
    return 0
  })
}

function conversationTitleFromQuestion(question: string) {
  const compact = question.replace(/\s+/g, ' ').trim()
  return compact.length > 28 ? `${compact.slice(0, 28)}...` : compact || '新会话'
}

function buildCitationView(result?: AgentQueryResponse | null, text?: string): CitationView {
  const answerText = text || result?.answer || ''
  const orderedOriginals = uniqueNumbers([...extractCitationNumbers(answerText), ...(result?.citations || [])])
  const displayByOriginal = new Map<number, number>()
  const items: CitationSourceItem[] = []
  orderedOriginals.forEach((originalCitation, index) => {
    const displayIndex = index + 1
    displayByOriginal.set(originalCitation, displayIndex)
    const sourceIndex = sourceIndexForCitation(result, originalCitation)
    const source = sourceIndex === null ? null : result?.sources[sourceIndex]
    if (sourceIndex !== null && source) {
      items.push({
        displayIndex,
        originalCitation,
        source,
        sourceIndex,
      })
    }
  })
  return {
    citationCount: orderedOriginals.length,
    displayByOriginal,
    items,
  }
}

function extractCitationNumbers(text: string) {
  const citations: number[] = []
  const pattern = /\[(\d+)\]/g
  let match: RegExpExecArray | null
  while ((match = pattern.exec(text)) !== null) {
    citations.push(Number(match[1]))
  }
  return citations
}

function uniqueNumbers(values: Array<number | string>) {
  const seen = new Set<number>()
  const unique: number[] = []
  values.forEach((value) => {
    const numberValue = Number(value)
    if (!Number.isFinite(numberValue) || numberValue < 1 || seen.has(numberValue)) return
    seen.add(numberValue)
    unique.push(numberValue)
  })
  return unique
}

function sourceIndexForCitation(result: AgentQueryResponse | null | undefined, citation: number) {
  if (!result?.sources.length) return null
  const mapped = result.citation_source_map?.[String(citation)] || result.citation_source_map?.[`[${citation}]`]
  if (typeof mapped === 'number') {
    return normalizedSourceIndex(mapped, result.sources.length)
  }
  if (typeof mapped === 'string') {
    const numeric = Number(mapped)
    if (Number.isFinite(numeric)) {
      return normalizedSourceIndex(numeric, result.sources.length)
    }
    const mappedIndex = result.sources.findIndex(
      (source) => source.source_id === mapped || String(source.chunk_id || '') === mapped || `${source.source_id}:${source.chunk_id}` === mapped,
    )
    if (mappedIndex >= 0) return mappedIndex
  }
  return normalizedSourceIndex(citation, result.sources.length)
}

function normalizedSourceIndex(value: number, sourceCount: number) {
  if (value === 0 && sourceCount > 0) return 0
  if (value >= 1 && value <= sourceCount) return value - 1
  if (value >= 0 && value < sourceCount) return value
  return null
}

function sourceMetaLine(source: AgentQueryResponse['sources'][number]) {
  const parts = [
    source.page_number ? `第 ${source.page_number} 页` : '',
    source.chunk_index !== undefined && source.chunk_index !== null ? `Chunk ${source.chunk_index}` : '',
    source.chunk_id ? `ID ${source.chunk_id}` : '',
  ].filter(Boolean)
  return parts.length ? parts.join(' / ') : '未提供页码或 chunk 信息'
}

function sourceOpenUrl(source: AgentQueryResponse['sources'][number]) {
  const documentId = source.document_id
  if (documentId === undefined || documentId === null) return ''
  return `/documents/${encodeURIComponent(String(documentId))}/open`
}

function imageEvidenceSources(result: AgentQueryResponse) {
  if (result.refused) return []
  const citationView = buildCitationView(result)
  const cited = citationView.items.map((item) => ({ source: item.source, citation: item.displayIndex }))
  const fallback = result.sources.map((source, index) => ({ source, citation: index + 1 }))
  const seen = new Set<string>()
  const figures: Array<{ source: AgentQueryResponse['sources'][number]; citation: number; imageUrl: string }> = []
  for (const candidate of [...cited, ...fallback]) {
    const imageUrl = candidate.source.image_url || ''
    if (!imageUrl || candidate.source.chunk_type !== 'image_description' || seen.has(imageUrl)) continue
    seen.add(imageUrl)
    figures.push({ ...candidate, imageUrl })
    if (figures.length >= 4) break
  }
  return figures
}

function tableEvidenceSources(result: AgentQueryResponse) {
  if (result.refused) return []
  const seen = new Set<string | number>()
  return result.sources
    .filter((source) => source.chunk_type === 'table' || Boolean(source.table_content))
    .filter((source) => {
      const key = source.source_id || source.chunk_id || source.title
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
    .slice(0, 3)
}

function figureOriginalLabel(source: AgentQueryResponse['sources'][number]) {
  const imagePath = String(source.source_image_path || source.image_url || '')
  const pageMatch = imagePath.match(/page(\d+)_img(\d+)/i)
  if (!pageMatch) return '原图'
  return `第 ${pageMatch[1]} 页 / 图 ${pageMatch[2]}`
}

function figureSourceLine(source: AgentQueryResponse['sources'][number], figureNumber = 1) {
  const pagePart = source.page_number ? `第 ${source.page_number} 页` : figureOriginalLabel(source)
  return `图 ${figureNumber} - ${pagePart} - ${safeText(source.title, '未命名来源')}`
}

function normalizeMarkdownTableSyntax(line: string) {
  return line
    .replace(/\uFF5C/g, '|')
    .replace(/[\uFF1A\uFE55]/g, ':')
    .replace(/[\u2010-\u2015\u2212\uFE58\uFE63\uFF0D]/g, '-')
}

function splitMarkdownTableRow(line: string) {
  const trimmed = normalizeMarkdownTableSyntax(line).trim().replace(/^\|/, '').replace(/\|$/, '')
  return trimmed.split('|').map((cell) => cell.trim())
}

function isMarkdownTableSeparator(line: string) {
  const cells = splitMarkdownTableRow(line).filter((cell) => cell)
  return cells.length > 1 && cells.every((cell) => /^:?-{1,}:?$/.test(cell.replace(/\s+/g, '')))
}

function isMarkdownTableLine(line: string) {
  return normalizeMarkdownTableSyntax(line).includes('|') && splitMarkdownTableRow(line).filter((cell) => cell).length > 1
}

function parseMarkdownTable(lines: string[]) {
  const rows = lines
    .filter((line) => !isMarkdownTableSeparator(line))
    .map(splitMarkdownTableRow)
    .filter((cells) => cells.length > 1)
  return rows.length >= 2 ? rows : null
}

function isNumericLikeTableCell(cell: string) {
  const normalized = cell.replace(/[\s,，%％/／·.-]/g, '')
  if (!normalized) return false
  const numericChars = normalized.match(/[0-9０-９.．×xX+\-－~～]/g)?.length || 0
  return numericChars / normalized.length >= 0.58
}

function isLongTokenTableCell(cell: string) {
  return /[A-Za-z0-9/_-]{16,}/.test(cell)
}

function MarkdownAnswerTable({
  header,
  rows,
  tableKey,
  activeCitation,
  selectCitation,
  citationView,
}: {
  header: string[]
  rows: string[][]
  tableKey: string
  activeCitation: number | null
  selectCitation: (index: number) => void
  citationView: CitationView
}) {
  const [expanded, setExpanded] = useState(false)
  const columnCount = header.length
  const rowCount = rows.length
  const isWide = columnCount >= 6
  const isLarge = rowCount >= 8 || columnCount >= 8
  const tableClassName = cn('markdown-table', 'is-compact', isWide && 'is-wide', isLarge && 'is-large')

  const renderCell = (cell: string, keyPrefix: string) => (
    <span className={cn(isLongTokenTableCell(cell) && 'markdown-table-cell-long-token')}>
      {renderInlineAnswer(cell, activeCitation, selectCitation, citationView, keyPrefix)}
    </span>
  )

  const renderTableElement = (keyScope: string) => (
    <table className={tableClassName}>
      <thead>
        <tr>
          {header.map((cell, index) => (
            <th
              className={cn(isNumericLikeTableCell(cell) && 'is-numeric')}
              key={`${keyScope}-h-${index}`}
            >
              {renderCell(cell, `${keyScope}-h-${index}`)}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, rowIndex) => (
          <tr key={`${keyScope}-r-${rowIndex}`}>
            {header.map((_, cellIndex) => {
              const cell = row[cellIndex] || ''
              return (
                <td
                  className={cn(isNumericLikeTableCell(cell) && 'is-numeric')}
                  key={`${keyScope}-r-${rowIndex}-c-${cellIndex}`}
                >
                  {renderCell(cell, `${keyScope}-r-${rowIndex}-c-${cellIndex}`)}
                </td>
              )
            })}
          </tr>
        ))}
      </tbody>
    </table>
  )

  return (
    <>
      <div className={cn('markdown-table-shell', isWide && 'is-wide', isLarge && 'is-large')}>
        <div className="markdown-table-toolbar">
          <span>
            表格 {columnCount}列 x {rowCount}行
          </span>
          {isWide ? <span>横向滚动查看</span> : null}
          {isLarge ? (
            <button type="button" onClick={() => setExpanded(true)} aria-label="展开表格">
              <Maximize2 aria-hidden="true" size={14} />
              展开
            </button>
          ) : null}
        </div>
        <div className="markdown-table-wrap">{renderTableElement(tableKey)}</div>
      </div>
      {expanded ? (
        <div className="markdown-table-modal" role="dialog" aria-modal="true" aria-label="展开表格">
          <div className="markdown-table-modal-panel">
            <div className="markdown-table-modal-header">
              <strong>
                表格 {columnCount}列 x {rowCount}行
              </strong>
              <button type="button" onClick={() => setExpanded(false)} aria-label="关闭展开表格">
                <X aria-hidden="true" size={16} />
              </button>
            </div>
            <div className="markdown-table-modal-body">{renderTableElement(`${tableKey}-expanded`)}</div>
          </div>
        </div>
      ) : null}
    </>
  )
}

function renderAnswerWithCitations(
  text: string,
  activeCitation: number | null,
  selectCitation: (index: number) => void,
  citationView = buildCitationView(undefined, text),
): ReactNode[] {
  const lines = text.replace(/\r\n/g, '\n').split('\n')
  const blocks: ReactNode[] = []
  let paragraph: string[] = []
  let listItems: string[] = []
  let tableLines: string[] = []
  let listStart = 1
  let nextListStart = 1

  const flushParagraph = () => {
    if (!paragraph.length) return
    const key = `p-${blocks.length}`
    blocks.push(
      <p className="answer-paragraph" key={key}>
        {paragraph.map((line, index) => (
          <FragmentWithBreak
            key={`${key}-${index}`}
            line={line}
            needsBreak={index > 0}
            activeCitation={activeCitation}
            citationView={citationView}
            selectCitation={selectCitation}
          />
        ))}
      </p>,
    )
    paragraph = []
  }

  const flushList = () => {
    if (!listItems.length) return
    const key = `ol-${blocks.length}`
    blocks.push(
      <ol className="answer-list" key={key} start={listStart}>
        {listItems.map((item, index) => (
          <li key={`${key}-${index}`}>{renderInlineAnswer(item, activeCitation, selectCitation, citationView, `${key}-${index}`)}</li>
        ))}
      </ol>,
    )
    nextListStart = listStart + listItems.length
    listItems = []
    listStart = nextListStart
  }

  const flushTable = () => {
    if (!tableLines.length) return
    const table = parseMarkdownTable(tableLines)
    if (table) {
      const [header, , ...rows] = table
      const key = `table-${blocks.length}`
      blocks.push(
        <MarkdownAnswerTable
          activeCitation={activeCitation}
          citationView={citationView}
          header={header}
          key={key}
          rows={rows}
          selectCitation={selectCitation}
          tableKey={key}
        />,
      )
    } else {
      paragraph.push(...tableLines)
    }
    tableLines = []
  }

  for (const rawLine of lines) {
    const line = rawLine.trim()
    if (!line) {
      flushTable()
      flushParagraph()
      flushList()
      continue
    }
    if (isMarkdownTableLine(line)) {
      flushParagraph()
      flushList()
      tableLines.push(line)
      continue
    }
    flushTable()
    const heading = line.match(/^#{1,4}\s+(.+)$/)
    if (heading) {
      flushParagraph()
      flushList()
      blocks.push(
        <h3 className="answer-heading" key={`h-${blocks.length}`}>
          {renderInlineAnswer(heading[1], activeCitation, selectCitation, citationView, `h-${blocks.length}`)}
        </h3>,
      )
      continue
    }
    const bullet = line.match(/^[-*]\s+(.+)$/)
    const numbered = line.match(/^(d+)[.)、]s+(.+)$/)
    const structuredItem = structuredAnswerListItem(line)
    if (bullet || numbered) {
      flushParagraph()
      if (!listItems.length) {
        listStart = numbered ? Number(numbered[1]) || nextListStart : nextListStart
      }
      listItems.push(bullet ? bullet[1] : numbered?.[2] || line)
      continue
    }
    if (structuredItem) {
      flushParagraph()
      if (!listItems.length) {
        listStart = nextListStart
      }
      listItems.push(structuredItem)
      continue
    }
    flushList()
    paragraph.push(line)
  }

  flushTable()
  flushParagraph()
  flushList()
  return blocks.length ? blocks : [text]
}

function structuredAnswerListItem(line: string) {
  const match = line.match(/^(?:[-*]\s*)?(\*\*[^*]+?\*\*|[^：:]{2,28}?)[：:]\s*(.+)$/)
  if (!match) return null
  const title = match[1].replace(/\*\*/g, '').trim()
  const body = match[2].trim()
  if (!body || title.length > 28 || /[。！？?!]$/.test(title)) return null
  if (/^(https?|sources?|agent|user)$/i.test(title)) return null
  return `**${title}**：${body}`
}

function FragmentWithBreak({
  activeCitation,
  citationView,
  line,
  needsBreak,
  selectCitation,
}: {
  activeCitation: number | null
  citationView: CitationView
  line: string
  needsBreak: boolean
  selectCitation: (index: number) => void
}) {
  return (
    <>
      {needsBreak ? <br /> : null}
      {renderInlineAnswer(line, activeCitation, selectCitation, citationView, line)}
    </>
  )
}

function renderInlineAnswer(
  text: string,
  activeCitation: number | null,
  selectCitation: (index: number) => void,
  citationView: CitationView,
  keyPrefix: string,
): ReactNode[] {
  const nodes: ReactNode[] = []
  const pattern = /(\*\*[^*]+?\*\*|\[(\d+)\])/g
  let cursor = 0
  let match: RegExpExecArray | null
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > cursor) {
      nodes.push(text.slice(cursor, match.index))
    }
    const token = match[1]
    const citation = token.match(/^\[(\d+)\]$/)
    const bold = token.match(/^\*\*(.+)\*\*$/)
    if (citation) {
      const originalIndex = Number(citation[1])
      const displayIndex = citationView.displayByOriginal.get(originalIndex) || originalIndex
      nodes.push(
        <button
          className={cn('citation-link', activeCitation === displayIndex && 'active')}
          key={`${keyPrefix}-citation-${match.index}-${originalIndex}`}
          onClick={() => selectCitation(displayIndex)}
          type="button"
        >
          [{displayIndex}]
        </button>,
      )
    } else if (bold) {
      nodes.push(
        <strong key={`${keyPrefix}-bold-${match.index}`}>
          {renderInlineAnswer(bold[1], activeCitation, selectCitation, citationView, `${keyPrefix}-bold-${match.index}`)}
        </strong>,
      )
    }
    cursor = match.index + match[0].length
  }
  if (cursor < text.length) {
    nodes.push(text.slice(cursor))
  }
  return nodes.length ? nodes : [text]
}

function finalWorkflowSteps(message: ChatMessage) {
  const eventSteps = message.events || []
  if (eventSteps.length) return normalizeDisplaySteps(eventSteps)
  return agentThoughtStepsFromResult(message.result, { includeRetrievalDiagnostics: false })
}

function agentThoughtStepsFromResult(
  result: AgentQueryResponse | null | undefined,
  options: { includeRetrievalDiagnostics?: boolean } = {},
) {
  if (!result) return []
  const workflowSteps = result.workflow_steps || []
  const toolCalls = result.tool_calls || []
  let baseSteps = workflowSteps.length
    ? workflowSteps
    : toolCalls.map((call) => ({
        action: call.tool_name || call.name,
        name: call.tool_name || call.name,
        tool_name: call.tool_name,
        input_summary: call.input_summary,
        output_summary: call.output_summary,
        observation_summary: call.observation_summary,
        step_summary: call.step_summary,
        succeeded: call.succeeded,
        skipped: call.skipped,
        error: call.error,
      }))
  const retrievalTraceStep = options.includeRetrievalDiagnostics === false ? null : retrievalTraceStepFromResult(result)
  if (retrievalTraceStep) {
    baseSteps = [...baseSteps, retrievalTraceStep]
  }
  return normalizeDisplaySteps(baseSteps)
}

function normalizeDisplaySteps(steps: AgentWorkflowStep[]) {
  return dedupeDisplaySteps(mergeToolLifecycleSteps(steps))
}

function mergeToolLifecycleSteps(steps: AgentWorkflowStep[]) {
  const merged: AgentWorkflowStep[] = []
  const latestToolStep = new Map<string, number>()
  for (const step of steps) {
    const toolName = step.tool_name || ''
    const eventName = String(step.action || step.name || '')
    const isToolLifecycle = Boolean(toolName) && (eventName === 'tool_call_start' || eventName === 'tool_call_result')
    if (!isToolLifecycle) {
      merged.push(step)
      continue
    }
    if (eventName === 'tool_call_start') {
      latestToolStep.set(toolName, merged.length)
      merged.push({
        ...step,
        name: toolName,
        action: toolName,
      })
      continue
    }
    const existingIndex = latestToolStep.get(toolName)
    if (existingIndex === undefined) {
      latestToolStep.set(toolName, merged.length)
      merged.push({
        ...step,
        name: toolName,
        action: toolName,
      })
      continue
    }
    const previous = merged[existingIndex]
    const resultSummary = step.output_summary || step.observation_summary || step.step_summary
    merged[existingIndex] = {
      ...previous,
      ...step,
      name: toolName,
      action: toolName,
      input_summary: step.input_summary || previous.input_summary,
      output_summary: resultSummary || previous.output_summary,
      observation_summary: step.observation_summary || previous.observation_summary,
      step_summary: step.step_summary || (resultSummary ? undefined : previous.step_summary),
      succeeded: step.succeeded ?? previous.succeeded,
      skipped: step.skipped || previous.skipped,
      error: step.error || previous.error,
    }
  }
  return merged
}

function dedupeDisplaySteps(steps: AgentWorkflowStep[]) {
  const seen = new Set<string>()
  const deduped: AgentWorkflowStep[] = []
  for (const step of steps) {
    const key = [
      step.name || step.tool_name || step.action || '',
      step.input_summary || '',
      step.output_summary || step.observation_summary || step.step_summary || '',
      step.error || '',
    ].join('|')
    if (seen.has(key)) continue
    seen.add(key)
    deduped.push(step)
  }
  return deduped
}

function stepSummary(step: AgentWorkflowStep) {
  const summary = userFacingAgentSummary(
    step.step_summary || step.observation_summary || step.output_summary || step.input_summary || '',
    step,
  )
  return summary || (step.error ? userFacingAgentSummary(step.error, step) : '') || '暂无步骤摘要'
}

function retrievalTraceStepFromResult(result: AgentQueryResponse) {
  const trace = result.latency_trace || {}
  const selected = arrayTraceValue(trace, 'retrieval_selected_chunk_ids') || arrayTraceValue(trace, 'selected_chunk_ids')
  const candidates = arrayTraceValue(trace, 'retrieval_candidate_chunk_ids') || arrayTraceValue(trace, 'candidate_chunk_ids')
  if (!selected && !candidates) return null
  const parts: string[] = []
  if (selected) {
    parts.push(`selected_chunk_ids=${selected.slice(0, 12).join(',')}`)
  }
  if (!parts.length && candidates) {
    parts.push(`candidate_chunk_ids=${candidates.slice(0, 12).join(',')}`)
  }
  return {
    action: 'retrieval_diagnostics',
    name: 'retrieval_diagnostics',
    input_summary: '',
    output_summary: parts.join('; '),
    succeeded: true,
  }
}

function arrayTraceValue(trace: Record<string, unknown>, key: string) {
  const value = trace[key]
  return Array.isArray(value) ? value : null
}

function stepStatusLabel(step: AgentWorkflowStep) {
  if (isSkippedAgentStep(step)) return '已跳过'
  if (step.succeeded === false) return '失败'
  if (step.error) return '有错误'
  return '已完成'
}

function isSkippedAgentStep(step: AgentWorkflowStep) {
  const text = `${step.error || ''} ${step.output_summary || ''} ${step.observation_summary || ''}`.toLowerCase()
  return text.includes('skipped') || step.skipped === true
}

function skippedToolSummary(toolName = '', reasonText = '') {
  const label = localizeAgentTool(toolName)
  const normalized = String(reasonText || '').toLowerCase()
  if (normalized.includes('near-duplicate')) {
    return `已跳过：${label}；原因：与已执行检索重复`
  }
  if (normalized.includes('existing evidence available')) {
    return `已跳过：${label}；原因：已有可用证据`
  }
  if (normalized.includes('per-iteration search tool budget reached')) {
    return `已跳过：${label}；原因：本轮检索工具预算已用完`
  }
  return `已跳过：${label}`
}

function userFacingAgentSummary(summary: string, context: Partial<AgentWorkflowStep> = {}) {
  const text = String(summary || '')
  const normalized = text.toLowerCase()
  if (!text) return ''
  if (normalized.includes('calling model with tool definitions') || normalized.includes('llm_with_tools')) {
    return '正在分析问题并选择检索工具'
  }
  if (
    normalized.includes('near-duplicate') ||
    normalized.includes('existing evidence available') ||
    normalized.includes('per-iteration search tool budget reached')
  ) {
    return skippedToolSummary(context.tool_name || context.name || context.action, text)
  }
  if (normalized.includes('model request failed') || normalized.includes('llm') || normalized.includes('provider')) {
    return '模型请求失败，请检查 provider 配置或网络连接'
  }
  return text
}

function sseEventToWorkflowStep(event: string, payload: Record<string, unknown>): AgentWorkflowStep {
  const name = String(payload.tool_name || payload.action || payload.phase || event)
  return {
    name,
    action: String(payload.action || event),
    tool_name: typeof payload.tool_name === 'string' ? payload.tool_name : undefined,
    input_summary: typeof payload.input_summary === 'string' ? payload.input_summary : undefined,
    output_summary:
      typeof payload.output_summary === 'string'
        ? payload.output_summary
        : typeof payload.step_summary === 'string'
          ? payload.step_summary
          : undefined,
    observation_summary: typeof payload.observation_summary === 'string' ? payload.observation_summary : undefined,
    succeeded: typeof payload.succeeded === 'boolean' ? payload.succeeded : event !== 'tool_call_result' ? undefined : true,
    skipped: Boolean(payload.skipped),
    error: typeof payload.error === 'string' ? payload.error : null,
    payload,
  }
}

function stepLabel(step: AgentWorkflowStep) {
  const raw = step.tool_name || step.name || step.action || 'Agent 步骤'
  return localizeAgentAction(raw)
}

function localizeAgentAction(action = '') {
  if (action === 'search_progress') return '检索进度'
  if (action === 'answer_progress') return '生成回答'
  const labels: Record<string, string> = {
    agent_step: 'Agent 步骤',
    tool_call_start: '调用工具',
    tool_call_result: '工具结果',
    llm_with_tools: '分析问题并选择检索工具',
    hybrid_search_knowledge: '混合检索',
    search_knowledge: '检索知识库',
    search_figures: '检索示例图片',
    search_tables: '检索表格证据',
    analyze_user_image: '分析上传图片',
    rewrite_query: '改写查询',
    answer_with_citations: '生成带引用回答',
    retrieval_diagnostics: '检索诊断',
    refuse: '拒答判断',
    final_answer: '最终回答',
  }
  return labels[action] || action || '未知步骤'
}

function localizeAgentTool(toolName = '') {
  const labels: Record<string, string> = {
    search_knowledge: '检索知识库',
    hybrid_search_knowledge: '混合检索',
    search_figures: '检索示例图片',
    search_tables: '检索表格证据',
    analyze_user_image: '分析上传图片',
    answer_with_citations: '生成带引用回答',
    retrieval_diagnostics: '检索诊断',
    rewrite_query: '改写查询',
    refuse: '拒答判断',
    final_answer: '最终回答',
  }
  return labels[toolName] || toolName || '未知工具'
}

function chainWarningFromResult(result: AgentQueryResponse | null) {
  const answer = String(result?.answer || '').trim()
  if (!answer) return ''
  const normalized = answer.toLowerCase()
  if (answer.startsWith('链路失败') || (normalized.includes('reranker') && normalized.includes('fallback'))) {
    return answer
  }
  return ''
}
function resultElapsedMs(result: AgentQueryResponse | null | undefined) {
  const value = result?.latency_trace?.time_to_final_ms
  const elapsed = typeof value === 'number' ? value : typeof value === 'string' ? Number(value) : NaN
  return Number.isFinite(elapsed) && elapsed >= 0 ? elapsed : undefined
}

function formatDuration(ms: number) {
  return `${Math.max(0, Math.ceil(ms / 1000))}秒`
}

export default App
