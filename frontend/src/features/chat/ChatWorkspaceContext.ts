import { createContext, useContext, type ChangeEvent, type FormEvent } from 'react'
import type { AgentQueryResponse, ChatMessage, Conversation } from '@/lib/types'
import type { ActiveCitation, ChatModelPreset, PendingImage } from '@/features/chat/model'

export type ChatWorkspaceValue = {
  conversations: Conversation[]
  activeConversationId?: number
  activeConversation?: Conversation
  isDraft: boolean
  isWorkspaceLoading: boolean
  conversationsError: unknown
  messagesError: unknown
  messages: ChatMessage[]
  selectedAssistantMessageId: string | null
  selectedAssistantMessage: ChatMessage | null
  selectedResult: AgentQueryResponse | null
  activeCitation: ActiveCitation
  question: string
  selectedChatModel: ChatModelPreset
  pendingImage: PendingImage | null
  isUploadingImage: boolean
  isSubmitting: boolean
  isConversationMutating: boolean
  isRunning: boolean
  now: number
  status: string
  submitError: unknown
  operationError: { title: string; error: unknown; retryLabel: string } | null
  composerRef: React.RefObject<HTMLTextAreaElement | null>
  imageInputRef: React.RefObject<HTMLInputElement | null>
  pinnedConversationIds: number[]
  setQuestion: (value: string) => void
  setSelectedChatModel: (value: ChatModelPreset) => void
  setPendingImage: (image: PendingImage | null) => void
  newDraft: () => void
  openConversation: (conversationId: number) => void
  submitQuestion: (event?: FormEvent<HTMLFormElement>) => Promise<void>
  stopActiveRun: () => void
  uploadImage: (event: ChangeEvent<HTMLInputElement>) => Promise<void>
  selectAssistantMessage: (messageId: string) => void
  selectCitation: (messageId: string, index: number) => void
  selectSource: (index: number, hasCitation: boolean) => void
  clearCitation: () => void
  toggleConversationPin: (conversationId: number) => void
  renameConversationById: (conversationId: number) => Promise<void>
  deleteConversationById: (conversationId: number) => Promise<void>
  refreshWorkspace: () => Promise<void>
  retryMessages: () => Promise<void>
  retryConversations: () => Promise<void>
  retryOperation: () => void
  updateSelectedResult: (updater: (result: AgentQueryResponse) => AgentQueryResponse) => void
  updateMessageResult: (
    conversationId: number,
    messageId: string,
    updater: (result: AgentQueryResponse) => AgentQueryResponse,
  ) => void
}

export const ChatWorkspaceContext = createContext<ChatWorkspaceValue | null>(null)

export function useChatWorkspace() {
  const value = useContext(ChatWorkspaceContext)
  if (!value) throw new Error('useChatWorkspace must be used within ChatWorkspaceProvider')
  return value
}
