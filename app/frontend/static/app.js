const apiEndpoints = {
  sources: "/sources",
  sourceSync: "/sources/sync",
  sourceReindex: (sourceId) => `/sources/${encodeURIComponent(sourceId)}/reindex`,
  documents: "/documents",
  documentChunks: (documentId) => `/documents/${encodeURIComponent(documentId)}/chunks`,
  keywordSearch: "/search",
  vectorSearch: "/search/vector",
  hybridSearch: "/search/hybrid",
  chat: "/chat",
  agent: "/agent/query",
  conversations: "/conversations",
  conversation: (conversationId) => `/conversations/${encodeURIComponent(conversationId)}`,
  conversationMessages: (conversationId) => `/conversations/${encodeURIComponent(conversationId)}/messages`,
};

const state = {
  sources: [],
  documents: [],
  sourceFilters: {
    keyword: "",
    status: "",
    permission: "",
  },
  conversations: [],
  currentConversationId: null,
  agentRequestInFlight: false,
};

async function fetchJson(url, options = {}) {
  const { timeoutMs, ...fetchOptions } = options;
  const controller = timeoutMs ? new AbortController() : null;
  const timeoutId = controller ? window.setTimeout(() => controller.abort(), timeoutMs) : null;
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(fetchOptions.headers || {}),
    },
    ...fetchOptions,
    signal: controller?.signal || fetchOptions.signal,
  }).catch((error) => {
    if (timeoutId) {
      window.clearTimeout(timeoutId);
    }
    if (error.name === "AbortError") {
      throw new Error("请求超时：后端或模型服务暂时没有返回，请稍后重试或检查模型配置");
    }
    throw error;
  });
  try {
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = payload.detail || `HTTP ${response.status}`;
      throw new Error(Array.isArray(detail) ? detail.map((item) => item.msg).join("; ") : detail);
    }
    return payload;
  } finally {
    if (timeoutId) {
      window.clearTimeout(timeoutId);
    }
  }
}

function setApiStatus(message) {
  const status = document.querySelector("[data-api-status]");
  if (status) {
    status.textContent = message;
  }
}

function setAgentPanelStatus(message) {
  const status = document.querySelector("[data-agent-status]");
  if (status) {
    status.textContent = message;
  }
}

function setAgentBusy(isBusy) {
  state.agentRequestInFlight = isBusy;
  const submitButton = document.querySelector("[data-agent-submit]");
  if (submitButton) {
    submitButton.disabled = isBusy;
    submitButton.textContent = isBusy ? "运行中" : "运行";
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function compactText(value, fallback = "-") {
  const text = String(value ?? "").trim();
  return text || fallback;
}

function formatRefusalCategory(category) {
  const labels = {
    responsibility_gate_triggered: "责任边界",
    evidence_insufficient: "证据不足",
    off_topic: "离题",
  };
  return labels[category] || compactText(category, "未分类");
}

function sourceMatchesKeyword(source, keyword) {
  if (!keyword) {
    return true;
  }
  const haystack = [
    source.title,
    source.source_id,
    source.doi,
    source.url,
    source.pdf_url,
    source.authors,
    source.category,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return haystack.includes(keyword.toLowerCase());
}

function filteredSources() {
  return state.sources.filter((source) => {
    const statusMatch = !state.sourceFilters.status || source.status === state.sourceFilters.status;
    const permissionMatch =
      !state.sourceFilters.permission ||
      source.fulltext_permission === state.sourceFilters.permission;
    return (
      statusMatch &&
      permissionMatch &&
      sourceMatchesKeyword(source, state.sourceFilters.keyword)
    );
  });
}

function countSourcesByStatus(status) {
  return state.sources.filter((source) => source.status === status).length;
}

function updateMetric(name, value) {
  const node = document.querySelector(`[data-metric="${name}"]`);
  if (node) {
    node.textContent = String(value);
  }
}

function renderMetrics() {
  updateMetric("sourcesTotal", state.sources.length);
  updateMetric("sourcesCollected", countSourcesByStatus("collected"));
  updateMetric("sourcesImported", countSourcesByStatus("imported"));
  updateMetric("documentsTotal", state.documents.length);
  updateMetric(
    "chunksTotal",
    state.documents.reduce((total, documentItem) => total + Number(documentItem.chunk_count || 0), 0),
  );
}

function renderSources() {
  const body = document.querySelector("[data-sources-body]");
  const count = document.querySelector("[data-sources-count]");
  if (!body) {
    return;
  }
  const sources = filteredSources();
  if (count) {
    count.textContent = `${sources.length} / ${state.sources.length}`;
  }
  if (!sources.length) {
    body.innerHTML = '<tr><td colspan="7" class="empty-cell">没有匹配来源</td></tr>';
    return;
  }
  body.innerHTML = sources
    .map((source) => {
      const link = source.url
        ? `<a href="${escapeHtml(source.url)}" target="_blank" rel="noreferrer">${escapeHtml(source.source_id)}</a>`
        : `<span class="meta-line">${escapeHtml(source.source_id)}</span>`;
      return `
        <tr>
          <td class="title-cell">
            <strong>${escapeHtml(source.title)}</strong>
            ${link}
          </td>
          <td><span class="pill">${escapeHtml(source.status)}</span></td>
          <td><span class="pill neutral">${escapeHtml(source.trust_level)}</span></td>
          <td>${escapeHtml(source.fulltext_permission)}</td>
          <td>${escapeHtml(compactText(source.year))}</td>
          <td>${escapeHtml(compactText(source.category))}</td>
          <td><button class="inline-action" type="button" data-reindex-source="${escapeHtml(source.source_id)}">reindex</button></td>
        </tr>
      `;
    })
    .join("");
}

function renderDocuments() {
  const body = document.querySelector("[data-documents-body]");
  const count = document.querySelector("[data-documents-count]");
  if (!body) {
    return;
  }
  if (count) {
    count.textContent = String(state.documents.length);
  }
  if (!state.documents.length) {
    body.innerHTML = '<tr><td colspan="6" class="empty-cell">暂无资料</td></tr>';
    return;
  }
  body.innerHTML = state.documents
    .map(
      (documentItem) => `
        <tr>
          <td class="title-cell">
            <strong>${escapeHtml(documentItem.title)}</strong>
            <span class="meta-line">#${escapeHtml(documentItem.id)}</span>
          </td>
          <td>${escapeHtml(documentItem.source_type)}</td>
          <td>${escapeHtml(documentItem.file_name)}</td>
          <td><span class="pill neutral">${escapeHtml(documentItem.status)}</span></td>
          <td>${escapeHtml(documentItem.chunk_count)}</td>
          <td><button class="inline-action" type="button" data-view-chunks="${escapeHtml(documentItem.id)}">chunks</button></td>
        </tr>
      `,
    )
    .join("");
}

function renderSearchResults(results) {
  const list = document.querySelector("[data-search-results]");
  const count = document.querySelector("[data-search-count]");
  if (!list) {
    return;
  }
  if (count) {
    count.textContent = String(results.length);
  }
  if (!results.length) {
    list.innerHTML = '<div class="empty-state">暂无结果</div>';
    return;
  }
  list.innerHTML = results
    .map(
      (result) => `
        <article class="result-item">
          <h3>${escapeHtml(result.document_title)}</h3>
          <p>${escapeHtml(result.source_type)} · chunk ${escapeHtml(result.chunk_index)} · score ${Number(result.score || 0).toFixed(3)}</p>
          <div class="result-snippet">${escapeHtml(result.content)}</div>
        </article>
      `,
    )
    .join("");
}

function renderChunks(payload) {
  const list = document.querySelector("[data-chunks-list]");
  const count = document.querySelector("[data-chunks-count]");
  if (!list) {
    return;
  }
  const chunks = payload.chunks || [];
  if (count) {
    count.textContent = String(chunks.length);
  }
  if (!chunks.length) {
    list.innerHTML = '<div class="empty-state">暂无片段</div>';
    return;
  }
  list.innerHTML = chunks
    .map(
      (chunk) => `
        <article class="chunk-item">
          <h3>${escapeHtml(payload.title)} · chunk ${escapeHtml(chunk.chunk_index)}</h3>
          <p>${escapeHtml(compactText(chunk.heading_path))} · ${escapeHtml(chunk.char_count)} chars</p>
          <div class="chunk-snippet">${escapeHtml(chunk.content)}</div>
        </article>
      `,
    )
    .join("");
}

async function submitSearch() {
  const query = document.querySelector("[data-search-query]")?.value.trim();
  const mode = document.querySelector("[data-search-mode]")?.value || "keyword";
  const topK = Number(document.querySelector("[data-search-top-k]")?.value || 5);
  if (!query) {
    setApiStatus("请输入检索词");
    return;
  }
  setApiStatus("检索中");
  const searchEndpoints = {
    keyword: apiEndpoints.keywordSearch,
    vector: apiEndpoints.vectorSearch,
    hybrid: apiEndpoints.hybridSearch,
  };
  const endpoint = searchEndpoints[mode] || apiEndpoints.keywordSearch;
  const payload = await fetchJson(endpoint, {
    method: "POST",
    body: JSON.stringify({ query, top_k: topK }),
  });
  renderSearchResults(payload.results || []);
  setApiStatus("已检索");
}

async function viewDocumentChunks(documentId) {
  setApiStatus("加载片段");
  const payload = await fetchJson(apiEndpoints.documentChunks(documentId));
  renderChunks(payload);
  setApiStatus("已加载片段");
}

async function syncSources() {
  setApiStatus("同步来源中");
  const payload = await fetchJson(apiEndpoints.sourceSync, {
    method: "POST",
    body: JSON.stringify({ include_defaults: true }),
  });
  await loadWorkspaceData();
  setApiStatus(
    `同步完成：total ${payload.total}, created ${payload.created}, updated ${payload.updated}, duplicates ${payload.duplicates}`,
  );
}

async function reindexSource(sourceId) {
  setApiStatus(`reindex ${sourceId}`);
  const payload = await fetchJson(apiEndpoints.sourceReindex(sourceId), {
    method: "POST",
    body: JSON.stringify({}),
  });
  await loadWorkspaceData();
  setApiStatus(`reindex 完成：document ${payload.document_id}，需要时刷新向量索引`);
}

function renderAnswer(result) {
  const answerBox = document.querySelector("[data-answer-box]");
  const chatMode = document.querySelector("[data-chat-mode]");
  if (!answerBox) {
    return;
  }
  if (chatMode) {
    chatMode.textContent = result.retrieval_mode || "none";
  }
  const citationBadges = (result.citations || [])
    .map((citation) => `<span class="pill">[${escapeHtml(citation)}]</span>`)
    .join("");
  const refused = result.refused
    ? `<div class="refusal"><strong>拒答</strong><p>${escapeHtml(result.refusal_reason || "资料不足")}</p></div>`
    : "";
  answerBox.innerHTML = `
    ${refused}
    <div class="answer-text">${escapeHtml(result.answer)}</div>
    <div class="answer-meta">
      ${citationBadges || '<span class="pill neutral">无引用</span>'}
      <span class="pill neutral">${escapeHtml(result.model_provider)} / ${escapeHtml(result.model_name)}</span>
    </div>
  `;
}

function renderCitations(sources) {
  const list = document.querySelector("[data-citations-list]");
  const count = document.querySelector("[data-citations-count]");
  if (!list) {
    return;
  }
  if (count) {
    count.textContent = String(sources.length);
  }
  if (!sources.length) {
    list.innerHTML = '<div class="empty-state">暂无引用</div>';
    return;
  }
  list.innerHTML = sources
    .map(
      (source) => `
        <article class="citation-item">
          <h3>[${escapeHtml(source.source_id)}] ${escapeHtml(source.document_title)}</h3>
          <p>${escapeHtml(source.source_type)} · chunk ${escapeHtml(source.chunk_index)} · score ${Number(source.score || 0).toFixed(3)}</p>
          <p class="meta-line">${escapeHtml(compactText(source.source_path))}</p>
          <div class="citation-snippet">${escapeHtml(source.content)}</div>
        </article>
      `,
    )
    .join("");
}

function renderAgentToolCalls(toolCalls) {
  const list = document.querySelector("[data-agent-tools-list]");
  const count = document.querySelector("[data-agent-tools-count]");
  if (!list) {
    return;
  }
  if (count) {
    count.textContent = String(toolCalls.length);
  }
  if (!toolCalls.length) {
    list.innerHTML = '<div class="empty-state">暂无工具调用</div>';
    return;
  }
  list.innerHTML = toolCalls
    .map(
      (call) => `
        <article class="tool-call-item">
          <h3>${escapeHtml(call.tool_name)}</h3>
          <p>${escapeHtml(call.succeeded ? "success" : "failed")}</p>
          <div class="result-snippet">${escapeHtml(call.input_summary)}</div>
          <div class="result-snippet">${escapeHtml(call.output_summary)}</div>
          ${
            call.error
              ? `<p class="meta-line">${escapeHtml(call.error)}</p>`
              : ""
          }
        </article>
      `,
    )
    .join("");
}

function renderAgentWorkflowSteps(workflowSteps) {
  const list = document.querySelector("[data-agent-tools-list]");
  const count = document.querySelector("[data-agent-tools-count]");
  if (!list) {
    return;
  }
  if (count) {
    count.textContent = String(workflowSteps.length);
  }
  if (!workflowSteps.length) {
    list.innerHTML = '<div class="empty-state">暂无迭代步骤</div>';
    return;
  }
  list.innerHTML = workflowSteps
    .map((step, index) => {
      const succeeded = step.succeeded !== false;
      return `
        <article class="tool-call-item workflow-step-item">
          <div class="workflow-step-heading">
            <span class="workflow-step-index">${index + 1}</span>
            <h3>${escapeHtml(step.name)}</h3>
            <span class="pill ${succeeded ? "neutral" : "warning"}">${escapeHtml(succeeded ? "success" : "failed")}</span>
          </div>
          <div class="result-snippet"><strong>输入</strong><br />${escapeHtml(step.input_summary)}</div>
          <div class="result-snippet"><strong>输出</strong><br />${escapeHtml(step.output_summary)}</div>
          ${
            step.error
              ? `<p class="meta-line">${escapeHtml(step.error)}</p>`
              : ""
          }
        </article>
      `;
    })
    .join("");
}

function clearAgentEmptyState() {
  const answerBox = document.querySelector("[data-agent-answer-box]");
  const emptyState = answerBox?.querySelector(".empty-state");
  if (emptyState) {
    emptyState.remove();
  }
}

function scrollAgentChatToBottom() {
  const answerBox = document.querySelector("[data-agent-answer-box]");
  if (answerBox) {
    answerBox.scrollTop = answerBox.scrollHeight;
  }
}

function clearAgentChat() {
  const answerBox = document.querySelector("[data-agent-answer-box]");
  if (!answerBox) {
    return;
  }
  answerBox.innerHTML = '<div class="empty-state">暂无 Agent 结果</div>';
  renderAgentToolCalls([]);
}

function appendAgentUserMessage(question) {
  const answerBox = document.querySelector("[data-agent-answer-box]");
  if (!answerBox) {
    return null;
  }
  clearAgentEmptyState();
  answerBox.insertAdjacentHTML(
    "beforeend",
    `
      <article class="chat-message chat-message--user">
        <div class="chat-message-bubble">
          <div class="chat-message-role">用户</div>
          <div class="answer-text">${escapeHtml(question)}</div>
        </div>
      </article>
    `,
  );
  scrollAgentChatToBottom();
  return answerBox.lastElementChild;
}

function appendAgentSummaryMessage(content) {
  const answerBox = document.querySelector("[data-agent-answer-box]");
  if (!answerBox) {
    return;
  }
  clearAgentEmptyState();
  answerBox.insertAdjacentHTML(
    "beforeend",
    `
      <article class="chat-message chat-message--summary">
        <div class="chat-message-bubble">
          <div class="chat-message-role">摘要</div>
          <div class="answer-text">${escapeHtml(content)}</div>
        </div>
      </article>
    `,
  );
  scrollAgentChatToBottom();
}

function appendAgentThinkingMessage() {
  const answerBox = document.querySelector("[data-agent-answer-box]");
  if (!answerBox) {
    return null;
  }
  clearAgentEmptyState();
  answerBox.insertAdjacentHTML(
    "beforeend",
    `
      <article class="chat-message chat-message--assistant chat-message--thinking" aria-live="polite">
        <div class="chat-message-bubble">
          <div class="chat-message-role">Agent</div>
          <div class="answer-text thinking-text">正在思考<span aria-hidden="true">...</span></div>
        </div>
      </article>
    `,
  );
  scrollAgentChatToBottom();
  return answerBox.lastElementChild;
}

function appendAgentErrorMessage(message) {
  const answerBox = document.querySelector("[data-agent-answer-box]");
  if (!answerBox) {
    return;
  }
  clearAgentEmptyState();
  answerBox.insertAdjacentHTML(
    "beforeend",
    `
      <article class="chat-message chat-message--assistant chat-message--error" aria-live="assertive">
        <div class="chat-message-bubble">
          <div class="chat-message-role">Agent</div>
          <div class="refusal">
            <strong>生成失败</strong>
            <p>${escapeHtml(message || "请求失败，请稍后重试")}</p>
          </div>
        </div>
      </article>
    `,
  );
  scrollAgentChatToBottom();
}

function appendAgentAssistantMessage(result) {
  const answerBox = document.querySelector("[data-agent-answer-box]");
  if (!answerBox) {
    return;
  }
  clearAgentEmptyState();
  answerBox.insertAdjacentHTML(
    "beforeend",
    `
      <article class="chat-message chat-message--assistant">
        <div class="chat-message-bubble">
          <div class="chat-message-role">Agent</div>
          ${agentAnswerHtml(result)}
        </div>
      </article>
    `,
  );
  scrollAgentChatToBottom();
}

function updateAgentModeStatus(mode) {
  const status = document.querySelector("[data-agent-mode-status]");
  if (!status) {
    return;
  }
  const labels = {
    auto: "系统自动",
    pending: "判断中",
    default: "default",
    agentic: "agentic",
  };
  const normalized = mode || "auto";
  status.textContent = labels[normalized] || normalized;
}

function agentAnswerHtml(result) {
  const invalidCitationSet = new Set((result.invalid_citations || []).map((citation) => String(citation)));
  const citationBadges = (result.citations || [])
    .map((citation) => {
      const isInvalid = invalidCitationSet.has(String(citation));
      return `<span class="pill ${isInvalid ? "danger" : ""}">[${escapeHtml(citation)}]${isInvalid ? " 无效" : ""}</span>`;
    })
    .join("");
  const orphanInvalidBadges = (result.invalid_citations || [])
    .filter((citation) => !(result.citations || []).map((item) => String(item)).includes(String(citation)))
    .map((citation) => `<span class="pill danger">[${escapeHtml(citation)}] 无效</span>`)
    .join("");
  const sourceBadges = (result.sources || [])
    .slice(0, 5)
    .map((source) => `<span class="pill neutral">${escapeHtml(source.source_id)}</span>`)
    .join("");
  const modeBadge = `<span class="pill neutral">mode: ${escapeHtml(result.mode || "default")}</span>`;
  const iterationBadge = `<span class="pill neutral">iterations: ${escapeHtml(result.iteration_count ?? 0)}</span>`;
  const refusalCategory = result.refusal_category
    ? `<p class="refusal-category">分类：${escapeHtml(formatRefusalCategory(result.refusal_category))} / ${escapeHtml(result.refusal_category)}</p>`
    : "";
  const refused = result.refused
    ? `<div class="refusal"><strong>拒答</strong>${refusalCategory}<p>${escapeHtml(result.refusal_reason || "资料不足")}</p></div>`
    : "";
  return `
    ${refused}
    <div class="answer-text">${escapeHtml(result.answer)}</div>
    <div class="answer-meta">
      ${citationBadges || '<span class="pill neutral">无引用</span>'}
      ${orphanInvalidBadges}
      ${sourceBadges || '<span class="pill neutral">无来源</span>'}
      ${modeBadge}
      ${iterationBadge}
    </div>
    <p class="meta-line">${escapeHtml(result.reasoning_summary || "")}</p>
  `;
}

function renderAgentAnswer(result) {
  const status = document.querySelector("[data-agent-status]");
  updateAgentModeStatus(result.mode || "default");
  if (status) {
    status.textContent = result.refused ? "refused" : "answered";
  }
  appendAgentAssistantMessage(result);
}

function renderStoredConversationMessages(messages) {
  clearAgentChat();
  for (const message of messages) {
    if (message.role === "user") {
      appendAgentUserMessage(message.content);
    } else if (message.role === "assistant") {
      const metadata = message.metadata || {};
      appendAgentAssistantMessage({
        answer: message.content,
        mode: message.mode || metadata.mode || "default",
        tool_calls: metadata.tool_calls || [],
        search_results: metadata.search_results || [],
        sources: metadata.sources || [],
        citations: metadata.citations || [],
        refused: metadata.refused || false,
        refusal_reason: metadata.refusal_reason || null,
        reasoning_summary: metadata.reasoning_summary || "",
        workflow_steps: metadata.workflow_steps || [],
        iteration_count: metadata.iteration_count || 0,
        invalid_citations: metadata.invalid_citations || [],
        refusal_category: metadata.refusal_category || null,
      });
    } else if (message.role === "summary") {
      appendAgentSummaryMessage(message.content);
    }
  }
}

function renderConversationList() {
  const select = document.querySelector("[data-conversation-list]");
  if (!select) {
    return;
  }
  if (!state.conversations.length) {
    select.innerHTML = '<option value="">暂无会话</option>';
    return;
  }
  select.innerHTML = state.conversations
    .map((conversation) => {
      const selected = String(conversation.id) === String(state.currentConversationId) ? " selected" : "";
      return `<option value="${escapeHtml(conversation.id)}"${selected}>${escapeHtml(conversation.title)}</option>`;
    })
    .join("");
}

function setConversationListPlaceholder(message) {
  const select = document.querySelector("[data-conversation-list]");
  if (select) {
    select.innerHTML = `<option value="">${escapeHtml(message)}</option>`;
  }
}

async function refreshConversationList() {
  try {
    const payload = await fetchJson(apiEndpoints.conversations);
    state.conversations = payload.conversations || [];
    renderConversationList();
  } catch (error) {
    state.conversations = [];
    state.currentConversationId = null;
    setConversationListPlaceholder("加载失败");
    throw error;
  }
}

async function createAgentConversation(title = "新对话") {
  const conversation = await fetchJson(apiEndpoints.conversations, {
    method: "POST",
    body: JSON.stringify({ title }),
  });
  state.currentConversationId = conversation.id;
  await refreshConversationList();
  clearAgentChat();
  updateAgentModeStatus("auto");
  return conversation;
}

async function loadConversationMessages(conversationId) {
  if (!conversationId) {
    clearAgentChat();
    return;
  }
  const payload = await fetchJson(apiEndpoints.conversationMessages(conversationId));
  state.currentConversationId = payload.conversation.id;
  renderStoredConversationMessages(payload.messages || []);
  renderConversationList();
  updateAgentModeStatus("auto");
}

async function loadAgentConversations() {
  await refreshConversationList();
  if (state.conversations.length) {
    await loadConversationMessages(state.conversations[0].id);
  } else {
    await createAgentConversation();
  }
}

async function deleteCurrentConversation() {
  if (!state.currentConversationId) {
    return;
  }
  await fetchJson(apiEndpoints.conversation(state.currentConversationId), {
    method: "DELETE",
  });
  state.currentConversationId = null;
  await refreshConversationList();
  if (state.conversations.length) {
    await loadConversationMessages(state.conversations[0].id);
  } else {
    await createAgentConversation();
  }
}

async function submitChat() {
  const question = document.querySelector("[data-chat-question]")?.value.trim();
  const topK = Number(document.querySelector("[data-chat-top-k]")?.value || 5);
  const retrievalMode = document.querySelector("[data-chat-retrieval-mode]")?.value || "auto";
  const minScore = Number(document.querySelector("[data-chat-min-score]")?.value || 0);
  if (!question) {
    setApiStatus("请输入问题");
    return;
  }
  setApiStatus("问答中");
  const result = await fetchJson(apiEndpoints.chat, {
    method: "POST",
    body: JSON.stringify({
      question,
      top_k: topK,
      retrieval_mode: retrievalMode,
      min_score: minScore,
    }),
  });
  renderAnswer(result);
  renderCitations(result.sources || []);
  setApiStatus(result.refused ? "已拒答" : "已回答");
}

async function submitAgent() {
  if (state.agentRequestInFlight) {
    setApiStatus("Agent 正在运行，请等待当前请求完成");
    return;
  }
  const question = document.querySelector("[data-agent-question]")?.value.trim();
  const topK = Number(document.querySelector("[data-agent-top-k]")?.value || 5);
  const maxToolCalls = Number(document.querySelector("[data-agent-max-tool-calls]")?.value || 2);
  const sourceId = document.querySelector("[data-agent-source-id]")?.value.trim();
  if (!question) {
    setApiStatus("请输入 Agent 任务");
    return;
  }
  let pendingUserMessage = null;
  let pendingThinkingMessage = null;
  setAgentBusy(true);
  try {
    setApiStatus("Agent 运行中");
    setAgentPanelStatus("running");
    updateAgentModeStatus("pending");
    const body = {
      question,
      top_k: topK,
      max_tool_calls: maxToolCalls,
    };
    if (!state.currentConversationId) {
      const conversation = await createAgentConversation();
      state.currentConversationId = conversation.id;
    }
    pendingUserMessage = appendAgentUserMessage(question);
    pendingThinkingMessage = appendAgentThinkingMessage();
    body.conversation_id = state.currentConversationId;
    if (sourceId) {
      body.source_id = sourceId;
    }
    const result = await fetchJson(apiEndpoints.agent, {
      method: "POST",
      body: JSON.stringify(body),
      timeoutMs: 45000,
    });
    pendingThinkingMessage?.remove();
    pendingThinkingMessage = null;
    renderAgentAnswer(result);
    if ((result.workflow_steps || []).length) {
      renderAgentWorkflowSteps(result.workflow_steps || []);
    } else {
      renderAgentToolCalls(result.tool_calls || []);
    }
    setApiStatus(result.refused ? "Agent 已拒答" : "Agent 已完成");
    await refreshConversationList();
  } catch (error) {
    pendingThinkingMessage?.remove();
    setAgentPanelStatus("error");
    updateAgentModeStatus("auto");
    appendAgentErrorMessage(error.message);
    throw error;
  } finally {
    setAgentBusy(false);
  }
}

function renderAll() {
  renderMetrics();
  renderSources();
  renderDocuments();
}

async function loadWorkspaceData() {
  setApiStatus("加载中");
  const [sourcesPayload, documentsPayload] = await Promise.all([
    fetchJson(apiEndpoints.sources),
    fetchJson(apiEndpoints.documents),
  ]);
  state.sources = sourcesPayload.sources || [];
  state.documents = documentsPayload.documents || [];
  renderAll();
  setApiStatus("已加载");
}

function bindSourceFilters() {
  const keywordInput = document.querySelector("[data-source-filter]");
  const statusSelect = document.querySelector("[data-status-filter]");
  const permissionSelect = document.querySelector("[data-permission-filter]");
  keywordInput?.addEventListener("input", (event) => {
    state.sourceFilters.keyword = event.target.value.trim();
    renderSources();
  });
  statusSelect?.addEventListener("change", (event) => {
    state.sourceFilters.status = event.target.value;
    renderSources();
  });
  permissionSelect?.addEventListener("change", (event) => {
    state.sourceFilters.permission = event.target.value;
    renderSources();
  });
}

function bindCommands() {
  document.querySelector("[data-refresh-all]")?.addEventListener("click", () => {
    loadWorkspaceData().catch((error) => {
      setApiStatus(`加载失败：${error.message}`);
    });
  });
  document.querySelector("[data-chat-form]")?.addEventListener("submit", (event) => {
    event.preventDefault();
    submitChat().catch((error) => {
      setApiStatus(`问答失败：${error.message}`);
    });
  });
  document.querySelector("[data-search-form]")?.addEventListener("submit", (event) => {
    event.preventDefault();
    submitSearch().catch((error) => {
      setApiStatus(`检索失败：${error.message}`);
    });
  });
  document.querySelector("[data-agent-form]")?.addEventListener("submit", (event) => {
    event.preventDefault();
    submitAgent().catch((error) => {
      updateAgentModeStatus("auto");
      setApiStatus(`Agent 失败：${error.message}`);
    });
  });
  document.querySelector("[data-new-conversation]")?.addEventListener("click", () => {
    createAgentConversation().catch((error) => {
      setApiStatus(`新建会话失败：${error.message}`);
    });
  });
  document.querySelector("[data-refresh-conversations]")?.addEventListener("click", () => {
    loadAgentConversations().catch((error) => {
      setApiStatus(`刷新会话失败：${error.message}`);
    });
  });
  document.querySelector("[data-delete-conversation]")?.addEventListener("click", () => {
    deleteCurrentConversation().catch((error) => {
      setApiStatus(`删除会话失败：${error.message}`);
    });
  });
  document.querySelector("[data-conversation-list]")?.addEventListener("change", (event) => {
    loadConversationMessages(event.target.value).catch((error) => {
      setApiStatus(`切换会话失败：${error.message}`);
    });
  });
  document.querySelector("[data-sync-sources]")?.addEventListener("click", () => {
    syncSources().catch((error) => {
      setApiStatus(`同步失败：${error.message}`);
    });
  });
  document.addEventListener("click", (event) => {
    const chunkButton = event.target.closest("[data-view-chunks]");
    if (chunkButton) {
      viewDocumentChunks(chunkButton.dataset.viewChunks).catch((error) => {
        setApiStatus(`片段加载失败：${error.message}`);
      });
      return;
    }
    const reindexButton = event.target.closest("[data-reindex-source]");
    if (reindexButton) {
      reindexSource(reindexButton.dataset.reindexSource).catch((error) => {
        setApiStatus(`reindex 失败：${error.message}`);
      });
    }
  });
}

async function initializeShell() {
  bindSourceFilters();
  bindCommands();
  try {
    await fetchJson("/health");
    await loadWorkspaceData();
    await loadAgentConversations();
  } catch (error) {
    setApiStatus(`连接异常：${error.message}`);
  }
}

window.rfcRagFrontend = {
  apiEndpoints,
  fetchJson,
  setApiStatus,
};

initializeShell();
