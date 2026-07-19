export type AuthUser = {
  id: number
  username: string
  email: string
  is_active: boolean
  created_at: string
}

export type TokenResponse = {
  access_token: string
  token_type: string
  expires_in: number
  user: AuthUser
}

export type Conversation = {
  id: number
  title: string
  created_at?: string
  updated_at?: string
}

export type ConversationMessage = {
  id: number
  conversation_id: number
  role: 'user' | 'assistant' | 'summary' | string
  content: string
  mode?: string | null
  metadata?: Record<string, unknown>
  created_at?: string
}

export type ConversationMessagesResponse = {
  conversation: Conversation
  messages: ConversationMessage[]
}

export type AgentSource = {
  source_id?: string
  title: string
  source_type: string
  document_id?: number | null
  chunk_id?: number | null
  chunk_index?: number | null
  content?: string | null
  score?: number | null
  chunk_type?: string
  source_image_path?: string | null
  image_url?: string | null
  caption?: string | null
  page_number?: number | null
  table_content?: string | null
}

export type AgentWorkflowStep = {
  name: string
  step_id?: string | null
  input_summary?: string | null
  output_summary?: string | null
  step_summary?: string | null
  observation_summary?: string | null
  action?: string
  phase?: string
  tool_name?: string | null
  payload?: Record<string, unknown>
  succeeded?: boolean | null
  skipped?: boolean
  error?: string | null
  client_event_at?: number
  client_elapsed_ms?: number
}

export type AgentQueryResponse = {
  question: string
  answer: string
  sources: AgentSource[]
  citations: number[]
  refused: boolean
  refusal_reason?: string | null
  mode: string
  workflow_steps: AgentWorkflowStep[]
  runtime_workflow_steps?: AgentWorkflowStep[]
  tool_calls?: AgentWorkflowStep[]
  iteration_count?: number
  invalid_citations?: number[]
  refusal_category?: string | null
  latency_trace?: Record<string, unknown>
  judge_scores?: Record<string, number | string>
  judge_reasons?: Record<string, string>
  judge_provider?: string
  judge_model?: string
  judge_status?: string
  citation_source_map?: Record<string, number | string>
  chat_provider?: string | null
  chat_model?: string | null
}

export type ChatMessage = {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  result?: AgentQueryResponse
  pending?: boolean
  error?: string
  startedAt?: number
  completedAt?: number
  elapsedMs?: number
  events?: AgentWorkflowStep[]
  chainWarning?: string
}

export type SourceRecord = {
  id?: number
  source_id: string
  title: string
  source_type: string
  status?: string
  trust_level?: string
  fulltext_permission?: string
  document_id?: number | null
  authors?: string | null
  year?: string | null
  venue?: string | null
  url?: string | null
  pdf_url?: string | null
}

export type DocumentRecord = {
  id?: number
  document_id?: number
  title: string
  source_type?: string
  source_path?: string | null
  open_url?: string | null
  status?: string
  file_name?: string
  file_extension?: string
  chunk_count?: number
}

export type JudgeResponse = {
  judge_scores: Record<string, number | string>
  judge_reasons: Record<string, string>
  judge_provider: string
  judge_model: string
  judge_status: string
}
