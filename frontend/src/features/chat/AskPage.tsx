import { useEffect, useRef, useState, type CSSProperties, type MouseEvent } from 'react'
import { AlertTriangle, BookOpen, ChevronDown, Loader2, Play, Square } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/input'
import { Panel, PanelHeader } from '@/components/ui/panel'
import { EmptyState, LoadingState, RetryState } from '@/components/states'
import { useChatWorkspace } from '@/features/chat/ChatWorkspaceContext'
import { formatDuration, resultElapsedMs, type ChatModelPreset } from '@/features/chat/model'
import { buildCitationView, renderAnswerWithCitations, type CitationView } from '@/features/evidence/citations'
import { SourcesPanel } from '@/features/evidence/SourcesPanel'
import {
  currentLiveStepTitle,
  stepDurationLabel,
  stepLabel,
  stepStatusLabel,
  stepSummary,
  workflowStepsForMessage,
} from '@/features/trace/workflow'
import { cn } from '@/lib/utils'
import type { AgentWorkflowStep, ChatMessage } from '@/lib/types'

const chatModelOptions: Array<{ value: ChatModelPreset; label: string }> = [
  { value: 'deepseek-v4-flash', label: 'DeepSeek V4 Flash' },
  { value: 'deepseek-v4-pro', label: 'DeepSeek V4 Pro' },
]

export function AskPage() {
  const workspace = useChatWorkspace()
  const [conversationMenu, setConversationMenu] = useState<{ id: number; x: number; y: number } | null>(null)
  const [modelMenuOpen, setModelMenuOpen] = useState(false)
  const messageListRef = useRef<HTMLDivElement | null>(null)
  const modelSelectRef = useRef<HTMLDivElement | null>(null)
  const conversationMenuRef = useRef<HTMLDivElement | null>(null)
  const shouldStickToBottomRef = useRef(true)
  const latestMessage = workspace.messages[workspace.messages.length - 1]
  const messageScrollSignature = [
    workspace.activeConversationId || 'draft',
    workspace.messages.length,
    latestMessage?.id || 'none',
    latestMessage?.content.length || 0,
    latestMessage?.pending ? 'pending' : 'done',
    latestMessage?.events?.length || 0,
  ].join(':')

  useEffect(() => {
    if (!workspace.messages.length || !messageListRef.current) return
    const element = messageListRef.current
    if (latestMessage?.pending && !shouldStickToBottomRef.current) return
    const frame = window.requestAnimationFrame(() => {
      element.scrollTo({ top: element.scrollHeight, behavior: latestMessage?.pending ? 'smooth' : 'auto' })
    })
    return () => window.cancelAnimationFrame(frame)
  }, [latestMessage?.pending, messageScrollSignature, workspace.messages.length])

  useEffect(() => {
    if (!conversationMenu && !modelMenuOpen) return
    function closeMenus(event: globalThis.MouseEvent) {
      if (modelSelectRef.current?.contains(event.target as Node)) return
      if (conversationMenuRef.current?.contains(event.target as Node)) return
      setConversationMenu(null)
      setModelMenuOpen(false)
    }
    window.addEventListener('mousedown', closeMenus)
    return () => window.removeEventListener('mousedown', closeMenus)
  }, [conversationMenu, modelMenuOpen])

  const menuConversation = conversationMenu
    ? workspace.conversations.find((conversation) => conversation.id === conversationMenu.id)
    : undefined
  const selectedModel = chatModelOptions.find((option) => option.value === workspace.selectedChatModel) || chatModelOptions[0]

  function restoreQuestionFor(messageId: string) {
    const index = workspace.messages.findIndex((message) => message.id === messageId)
    const previousUserMessage = [...workspace.messages.slice(0, index)].reverse().find((message) => message.role === 'user')
    if (!previousUserMessage) return
    workspace.setQuestion(previousUserMessage.content)
    window.requestAnimationFrame(() => workspace.composerRef.current?.focus())
  }

  return (
    <div className="ask-layout">
      <Panel className="conversation-panel">
        <PanelHeader className="compact-header">
          <strong>会话记录</strong>
          <Button size="sm" variant="secondary" disabled={workspace.isSubmitting || workspace.isConversationMutating || workspace.isUploadingImage} onClick={workspace.newDraft}>新建</Button>
        </PanelHeader>
        <div className="conversation-list">
          {workspace.isDraft ? (
            <button className="conversation-item active draft" disabled={workspace.isSubmitting || workspace.isConversationMutating || workspace.isUploadingImage} type="button" onClick={() => workspace.composerRef.current?.focus()}>
              <span>新对话</span>
            </button>
          ) : null}
          {workspace.conversationsError ? (
            <RetryState
              compact
              title="会话列表加载失败"
              error={workspace.conversationsError}
              onRetry={() => void workspace.retryConversations()}
            />
          ) : null}
          {!workspace.conversationsError && workspace.conversations.map((conversation) => (
            <button
              key={conversation.id}
              disabled={workspace.isSubmitting || workspace.isConversationMutating || workspace.isUploadingImage}
              className={cn(
                'conversation-item',
                conversation.id === workspace.activeConversationId && 'active',
                workspace.pinnedConversationIds.includes(conversation.id) && 'pinned',
              )}
              type="button"
              onClick={() => workspace.openConversation(conversation.id)}
              onContextMenu={(event) => {
                event.preventDefault()
                setConversationMenu({ id: conversation.id, x: event.clientX, y: event.clientY })
              }}
            >
              <span>{conversation.title || `会话 ${conversation.id}`}</span>
              {workspace.pinnedConversationIds.includes(conversation.id) ? <Badge className="pinned-badge">置顶</Badge> : null}
            </button>
          ))}
          {!workspace.isDraft && !workspace.conversations.length && !workspace.conversationsError ? (
            workspace.isWorkspaceLoading
              ? <LoadingState compact label="正在恢复会话记录..." />
              : <EmptyState compact title="暂无会话" description="点击新建并开始提问。" />
          ) : null}
        </div>
        {conversationMenu && menuConversation ? (
          <div
            className="conversation-context-menu"
            ref={conversationMenuRef}
            style={{ left: conversationMenu.x, top: conversationMenu.y } as CSSProperties}
            onClick={(event) => event.stopPropagation()}
            onContextMenu={(event) => event.preventDefault()}
          >
            <button type="button" onClick={() => { workspace.toggleConversationPin(menuConversation.id); setConversationMenu(null) }}>
              {workspace.pinnedConversationIds.includes(menuConversation.id) ? '取消置顶' : '置顶会话'}
            </button>
            <button type="button" onClick={() => { void workspace.renameConversationById(menuConversation.id); setConversationMenu(null) }}>重命名</button>
            <button className="danger" type="button" onClick={() => { void workspace.deleteConversationById(menuConversation.id); setConversationMenu(null) }}>删除</button>
          </div>
        ) : null}
      </Panel>

      <Panel className="chat-panel">
        <PanelHeader className="chat-header">
          <div><h2>智能问答工作台</h2><p>{workspace.status}</p></div>
          <Badge className="status-badge">{workspace.isRunning ? '运行中' : workspace.isDraft ? '新对话' : '就绪'}</Badge>
        </PanelHeader>
        <div
          className="message-list"
          ref={messageListRef}
          onScroll={(event) => {
            const element = event.currentTarget
            shouldStickToBottomRef.current = element.scrollHeight - element.scrollTop - element.clientHeight < 120
          }}
        >
          {workspace.messagesError ? (
            <RetryState title="消息加载失败" error={workspace.messagesError} onRetry={() => void workspace.retryMessages()} />
          ) : null}
          {!workspace.messagesError && workspace.messages.map((message) => (
            <MessageBubble
              activeCitation={workspace.activeCitation?.messageId === message.id ? workspace.activeCitation.index : null}
              isSelected={workspace.selectedAssistantMessageId === message.id}
              key={message.id}
              message={message}
              now={workspace.now}
              onCitation={(index) => workspace.selectCitation(message.id, index)}
              onRetry={() => restoreQuestionFor(message.id)}
              onSelect={() => workspace.selectAssistantMessage(message.id)}
            />
          ))}
          {!workspace.messagesError && !workspace.messages.length ? (
            workspace.isWorkspaceLoading
              ? <LoadingState label="正在恢复会话消息..." />
              : <EmptyState title={workspace.isDraft ? '开始新的对话' : '暂无消息'} description="输入问题后，Agent 回答会显示在这里。" />
          ) : null}
        </div>

        <form className="composer" onSubmit={(event) => void workspace.submitQuestion(event)}>
          <Textarea
            className="composer-input"
            disabled={workspace.isSubmitting}
            ref={workspace.composerRef}
            value={workspace.question}
            onChange={(event) => workspace.setQuestion(event.target.value)}
            onKeyDown={(event) => {
              if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing) return
              event.preventDefault()
              event.currentTarget.form?.requestSubmit()
            }}
            placeholder="输入工程知识问题，回车发送，Shift+Enter 换行"
          />
          <input hidden ref={workspace.imageInputRef} type="file" accept="image/*" onChange={(event) => void workspace.uploadImage(event)} />
          {workspace.pendingImage ? (
            <div className="attachment-row"><span>已选择图片：<strong>{workspace.pendingImage.filename}</strong></span><button type="button" onClick={() => workspace.setPendingImage(null)}>移除</button></div>
          ) : null}
          {workspace.submitError ? (
            <RetryState
              compact
              title={workspace.isDraft ? '会话创建或上传失败' : '操作失败'}
              error={workspace.submitError}
              onRetry={() => void workspace.submitQuestion()}
              retryLabel="重新发送"
            />
          ) : null}
          {workspace.operationError ? (
            <RetryState
              compact
              title={workspace.operationError.title}
              error={workspace.operationError.error}
              onRetry={workspace.retryOperation}
              retryLabel={workspace.operationError.retryLabel}
            />
          ) : null}
          <div className="composer-actions">
            <div className="model-select" ref={modelSelectRef}>
              <span className="model-select-label">模型</span>
              <button
                aria-expanded={modelMenuOpen}
                className="model-select-trigger"
                disabled={workspace.isRunning || workspace.isSubmitting}
                onClick={() => setModelMenuOpen((value) => !value)}
                type="button"
              >
                <span>{selectedModel.label}</span><ChevronDown size={15} />
              </button>
              {modelMenuOpen && !workspace.isRunning && !workspace.isSubmitting ? (
                <div className="model-select-menu" role="listbox">
                  {chatModelOptions.map((option) => (
                    <button
                      aria-selected={option.value === workspace.selectedChatModel}
                      className={cn('model-select-option', option.value === workspace.selectedChatModel && 'active')}
                      key={option.value}
                      onClick={() => { workspace.setSelectedChatModel(option.value); setModelMenuOpen(false) }}
                      role="option"
                      type="button"
                    >{option.label}</button>
                  ))}
                </div>
              ) : null}
            </div>
            <Button disabled={workspace.isRunning || workspace.isUploadingImage || workspace.isSubmitting} type="button" variant="secondary" onClick={() => workspace.imageInputRef.current?.click()}>
              {workspace.isUploadingImage ? <Loader2 className="spin" size={16} /> : <BookOpen size={16} />}
              {workspace.isUploadingImage ? '上传中' : '上传图片'}
            </Button>
            {workspace.isRunning ? (
              <Button type="button" variant="danger" onClick={workspace.stopActiveRun}><Square size={16} />停止</Button>
            ) : (
              <Button type="submit" disabled={!workspace.question.trim() || workspace.isUploadingImage || workspace.isSubmitting}>
                {workspace.isSubmitting ? <Loader2 className="spin" size={16} /> : <Play size={16} />}
                {workspace.isSubmitting ? '准备会话' : '发送'}
              </Button>
            )}
          </div>
        </form>
      </Panel>
      <SourcesPanel />
    </div>
  )
}

export function MessageBubble({
  activeCitation,
  isSelected,
  message,
  now,
  onCitation,
  onRetry,
  onSelect,
}: {
  activeCitation: number | null
  isSelected: boolean
  message: ChatMessage
  now: number
  onCitation: (index: number) => void
  onRetry: () => void
  onSelect: () => void
}) {
  const isAssistant = message.role === 'assistant'
  const backendElapsed = resultElapsedMs(message.result)
  const wallClockElapsed = message.startedAt ? (message.pending ? now : message.completedAt || now) - message.startedAt : 0
  const elapsed = message.pending ? wallClockElapsed : message.elapsedMs ?? backendElapsed ?? wallClockElapsed
  const hasAssistantTiming = isAssistant && (
    message.pending || typeof message.elapsedMs === 'number' || typeof backendElapsed === 'number' ||
    (typeof message.startedAt === 'number' && typeof message.completedAt === 'number')
  )
  const steps = workflowStepsForMessage(message)
  const citationView = isAssistant ? buildCitationView(message.result, message.content) : buildCitationView()

  function handleBubbleClick(event: MouseEvent<HTMLElement>) {
    if (!isAssistant || (event.target as HTMLElement).closest('button, a')) return
    onSelect()
  }

  return (
    <article
      aria-current={isSelected ? 'true' : undefined}
      className={cn('message-bubble', message.role, message.chainWarning && 'warning', isSelected && 'selected')}
      data-message-id={message.id}
      aria-label={isAssistant ? '选择此 Agent 回答并查看对应来源' : undefined}
      onClick={handleBubbleClick}
      onKeyDown={(event) => {
        if (!isAssistant || event.target !== event.currentTarget || (event.key !== 'Enter' && event.key !== ' ')) return
        event.preventDefault()
        onSelect()
      }}
      tabIndex={isAssistant ? 0 : undefined}
    >
      <div className="message-title-row">
        <strong>{message.role === 'user' ? 'User' : message.role === 'system' ? 'Summary' : 'Agent'}</strong>
        {isAssistant && message.pending ? <span className="thinking-timer">思考 {formatDuration(elapsed)}</span> : null}
        {isAssistant && !message.pending && hasAssistantTiming ? <span className="thinking-timer done">已处理 {formatDuration(elapsed)}</span> : null}
      </div>
      {message.chainWarning ? <div className="chain-warning"><AlertTriangle size={16} /><span>{message.chainWarning}</span></div> : null}
      {isAssistant && (steps.length || message.pending) ? (
        <ThinkingPanel
          activeCitation={activeCitation}
          citationView={citationView}
          elapsedMs={elapsed}
          isPending={Boolean(message.pending)}
          onCitation={onCitation}
          steps={steps}
        />
      ) : null}
      {message.content ? (
        <div className={cn('message-content', !isAssistant && 'user-content')}>
          {isAssistant ? renderAnswerWithCitations(message.content, activeCitation, onCitation, citationView) : message.content}
        </div>
      ) : null}
      {message.error ? <RetryState compact title="Agent 运行失败" error={message.error} onRetry={onRetry} retryLabel="放回输入框" /> : null}
      {message.pending ? <Loader2 className="spin" size={16} /> : null}
      {isAssistant && citationView.citationCount ? <Badge className="citation-count-badge">{citationView.citationCount} 个引用</Badge> : null}
      {isAssistant && citationView.invalidCitationCount ? <Badge className="invalid-citation-badge">{citationView.invalidCitationCount} 个无效引用</Badge> : null}
    </article>
  )
}

export function ThinkingPanel({
  activeCitation,
  citationView,
  elapsedMs,
  isPending,
  onCitation,
  steps,
}: {
  activeCitation: number | null
  citationView: CitationView
  elapsedMs: number
  isPending: boolean
  onCitation: (index: number) => void
  steps: AgentWorkflowStep[]
}) {
  const [expanded, setExpanded] = useState(false)
  const elapsedLabel = formatDuration(elapsedMs)
  const latest = steps[steps.length - 1]
  return (
    <section className={cn('thinking-details', expanded && 'expanded')}>
      <button
        aria-expanded={isPending ? false : expanded}
        className={cn('thinking-summary', isPending && 'live')}
        disabled={isPending}
        onClick={() => { if (!isPending) setExpanded((value) => !value) }}
        type="button"
      >
        <span>{isPending ? `当前：${currentLiveStepTitle(steps)}` : expanded ? '收起思考过程' : '查看过程'}</span>
        <small>{isPending ? `已思考 ${elapsedLabel}` : `${steps.length} 个真实步骤${elapsedMs > 0 ? ` · 已处理 ${elapsedLabel}` : ''}`}</small>
      </button>
      {isPending ? (
        <div className="thinking-live-status" aria-live="polite">
          <span className="thinking-live-dot" aria-hidden="true" />
          <p>{latest ? stepSummary(latest) || stepLabel(latest) : '等待后端返回真实 Agent 步骤...'}</p>
        </div>
      ) : null}
      <div className={cn('thinking-step-list', expanded && 'expanded')}>
        {expanded && !isPending ? steps.map((step, index) => (
          <article className={cn('thinking-step', step.succeeded === false && 'failed', step.skipped && 'skipped')} key={`${step.name}-${index}`}>
            <div className="thinking-step-head">
              <strong>{index + 1}. {stepLabel(step)}</strong>
              <span className="thinking-step-meta">
                {stepDurationLabel(step) ? <small>{stepDurationLabel(step)}</small> : null}
                <Badge>{stepStatusLabel(step)}</Badge>
              </span>
            </div>
            <div className="thinking-step-summary">
              {renderAnswerWithCitations(stepSummary(step), activeCitation, onCitation, citationView)}
            </div>
          </article>
        )) : null}
      </div>
    </section>
  )
}
