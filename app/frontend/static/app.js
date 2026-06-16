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
  agentStream: "/agent/query/stream",
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
  activeAgentAbortController: null,
  currentView: "ask",
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
  const questionInput = document.querySelector("[data-agent-question]");
  if (submitButton) {
    submitButton.disabled = false;
    submitButton.textContent = isBusy ? "停止生成" : "运行";
    submitButton.classList.toggle("command-button--stop", isBusy);
    submitButton.setAttribute("aria-label", isBusy ? "停止生成" : "运行 Agent");
  }
  if (questionInput) {
    questionInput.required = !isBusy;
  }
}

function abortAgentStream() {
  if (!state.activeAgentAbortController) {
    return;
  }
  state.activeAgentAbortController.abort();
  setAgentPanelStatus("stopping");
  setApiStatus("正在停止生成");
}

function isAgentAbortError(error) {
  return error?.name === "AbortError" || String(error?.message || "").includes("AbortError");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

const SAFE_RENDERED_TAGS = new Set([
  "A",
  "BUTTON",
  "CODE",
  "DETAILS",
  "DIV",
  "LI",
  "OL",
  "P",
  "SMALL",
  "SPAN",
  "STRONG",
  "SUMMARY",
]);

const SAFE_RENDERED_ATTRS = new Set([
  "aria-hidden",
  "aria-label",
  "class",
  "data-agent-abort-status",
  "data-citation-ref",
  "href",
  "open",
  "rel",
  "role",
  "target",
  "type",
]);

const DANGEROUS_RENDERED_TAGS = new Set([
  "SCRIPT",
  "IFRAME",
  "OBJECT",
  "EMBED",
  "STYLE",
  "LINK",
  "META",
  "FORM",
]);

const URL_RENDERED_ATTRS = new Set(["href", "src", "xlink:href", "action", "formaction"]);

function isDangerousRenderedUrl(value) {
  const normalized = String(value || "").trim().replace(/[\u0000-\u001F\u007F\s]+/g, "").toLowerCase();
  return normalized.startsWith("javascript:") || normalized.startsWith("data:text/html");
}

function sanitizeRenderedHtml(html) {
  const template = document.createElement("template");
  template.innerHTML = String(html || "");
  const nodes = [template.content];
  while (nodes.length) {
    const current = nodes.pop();
    for (const child of Array.from(current.children || [])) {
      const tagName = child.tagName;
      if (DANGEROUS_RENDERED_TAGS.has(tagName) || !SAFE_RENDERED_TAGS.has(tagName)) {
        child.remove();
        continue;
      }
      for (const attribute of Array.from(child.attributes)) {
        const name = attribute.name.toLowerCase();
        const value = attribute.value;
        if (
          name.startsWith("on") ||
          !SAFE_RENDERED_ATTRS.has(name) ||
          (URL_RENDERED_ATTRS.has(name) && isDangerousRenderedUrl(value))
        ) {
          child.removeAttribute(attribute.name);
        }
      }
      if (child.tagName === "A") {
        child.setAttribute("rel", "noreferrer");
      }
      nodes.push(child);
    }
  }
  return template.innerHTML;
}

function compactText(value, fallback = "-") {
  const text = String(value ?? "").trim();
  return text || fallback;
}

function conversationTitleFromQuestion(question) {
  const normalized = compactText(question, "新对话").replace(/\s+/g, " ");
  return normalized.length > 18 ? `${normalized.slice(0, 18)}...` : normalized;
}

function userFriendlyErrorMessage(error) {
  const message = String(error?.message || "").trim();
  if (message.includes("请求超时") || error?.name === "AbortError") {
    return "请求超时：模型或检索服务暂时没有返回，请稍后重试。";
  }
  if (message.includes("chat model provider") || message.includes("provider")) {
    return "模型服务暂时不可用，请检查本地配置后重试。";
  }
  if (message.includes("HTTP 503")) {
    return "后端服务暂时不可用，请稍后重试。";
  }
  if (message.includes("Failed to fetch") || message.includes("NetworkError")) {
    return "网络连接失败，请确认后端服务正在运行。";
  }
  return "请求失败，请稍后重试；如持续失败，请检查服务日志。";
}

function sourceForCitation(sources, citation, sourceCitation = citation) {
  const index = Number(sourceCitation) - 1;
  if (!Number.isInteger(index) || index < 0) {
    return null;
  }
  return sources?.[index] || null;
}

function sourceTitle(source) {
  return compactText(source?.title || source?.document_title, "未知来源");
}

function sourceSummary(source) {
  return compactText(source?.content || source?.snippet, "暂无摘要").slice(0, 120);
}

function citationReferenceHtml(citation, sources, isInvalid = false, sourceCitation = citation) {
  const source = sourceForCitation(sources, citation, sourceCitation);
  const label = `[${escapeHtml(citation)}]`;
  if (!source) {
    return `<span class="citation-ref citation-ref--missing ${isInvalid ? "citation-ref--invalid" : ""}">${label}</span>`;
  }
  const title = sourceTitle(source);
  const sourceType = compactText(source.source_type, "unknown");
  const summary = sourceSummary(source);
  return `<button class="citation-ref ${isInvalid ? "citation-ref--invalid" : ""}" type="button" data-citation-ref="${escapeHtml(citation)}" aria-label="查看来源 ${escapeHtml(citation)}：${escapeHtml(title)}">${label}<span class="citation-popover" role="tooltip"><strong>${escapeHtml(title)}</strong><small>${escapeHtml(sourceType)}</small><span>${escapeHtml(summary)}</span></span></button>`;
}

function citationNumbersInAnswer(answer) {
  const numbers = [];
  const seen = new Set();
  for (const match of String(answer || "").matchAll(/\[(\d+)\]/g)) {
    if (!seen.has(match[1])) {
      seen.add(match[1]);
      numbers.push(match[1]);
    }
  }
  return numbers;
}

function normalizeCitationDisplay(result = {}) {
  const rawAnswer = String(result.answer || "");
  const orderedOriginalCitations = citationNumbersInAnswer(rawAnswer);
  if (!orderedOriginalCitations.length) {
    for (const citation of result.citations || []) {
      const key = String(citation);
      if (!orderedOriginalCitations.includes(key)) {
        orderedOriginalCitations.push(key);
      }
    }
  }
  const originalToDisplay = new Map();
  const displayToOriginal = {};
  orderedOriginalCitations.forEach((original, index) => {
    const display = String(index + 1);
    originalToDisplay.set(String(original), display);
    displayToOriginal[display] = String(original);
  });
  const answer = rawAnswer.replace(/\[(\d+)\]/g, (marker, original) => {
    const display = originalToDisplay.get(String(original));
    return display ? `[${display}]` : marker;
  });
  const citations = orderedOriginalCitations.map((_, index) => index + 1);
  const invalidCitations = (result.invalid_citations || [])
    .map((citation) => originalToDisplay.get(String(citation)))
    .filter(Boolean)
    .map((citation) => Number(citation));
  return {
    ...result,
    answer,
    citations,
    invalid_citations: invalidCitations,
    citation_source_map: displayToOriginal,
  };
}

function renderInlineMarkdown(text) {
  return String(text || "")
    .split(/(\*\*[^*\n][\s\S]*?[^*\n]\*\*)/g)
    .map((part) => {
      const match = part.match(/^\*\*([^*\n][\s\S]*?[^*\n])\*\*$/);
      if (match) {
        return `<strong>${escapeHtml(match[1])}</strong>`;
      }
      return escapeHtml(part);
    })
    .join("");
}

function renderAnswerWithCitationLinks(answer, sources = [], invalidCitations = [], citationSourceMap = {}) {
  const invalidCitationSet = new Set(invalidCitations.map((citation) => String(citation)));
  const rendered = String(answer || "")
    .split(/(\[\d+\])/g)
    .map((part) => {
      const match = part.match(/^\[(\d+)\]$/);
      if (!match) {
        return renderInlineMarkdown(part);
      }
      const citation = match[1];
      return citationReferenceHtml(
        citation,
        sources,
        invalidCitationSet.has(String(citation)),
        citationSourceMap[String(citation)] || citation,
      );
    })
    .join("");
  return sanitizeRenderedHtml(rendered);
}

function formatRefusalCategory(category) {
  const labels = {
    responsibility_gate_triggered: "责任边界",
    evidence_insufficient: "证据不足",
    off_topic: "离题",
    service_error: "检索服务异常",
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
  const nodes = document.querySelectorAll(`[data-metric="${name}"]`);
  for (const node of nodes) {
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
  result = normalizeCitationDisplay(result);
  const answerBox = document.querySelector("[data-answer-box]");
  const chatMode = document.querySelector("[data-chat-mode]");
  if (!answerBox) {
    return;
  }
  if (chatMode) {
    chatMode.textContent = result.retrieval_mode || "none";
  }
  const citationBadges = (result.citations || [])
    .map((citation) =>
      citationReferenceHtml(
        citation,
        result.sources || [],
        false,
        result.citation_source_map?.[String(citation)] || citation,
      ),
    )
    .join("");
  const refused = result.refused
    ? `<div class="refusal"><strong>拒答</strong><p>${escapeHtml(result.refusal_reason || "资料不足")}</p></div>`
    : "";
  answerBox.innerHTML = `
    ${refused}
    <div class="answer-text">${renderAnswerWithCitationLinks(result.answer, result.sources || [], [], result.citation_source_map || {})}</div>
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
          <div class="agent-thinking-status" data-agent-thinking-status><span class="loading-spinner" aria-hidden="true"></span>正在思考</div>
          <div class="agent-live-steps" data-agent-live-steps hidden aria-label="Agent live steps"></div>
          <div class="answer-text thinking-text"><span class="loading-spinner" aria-hidden="true"></span>正在思考</div>
        </div>
      </article>
    `,
  );
  scrollAgentChatToBottom();
  return answerBox.lastElementChild;
}

function liveAgentEventView(eventName, payload = {}) {
  if (eventName === "tool_call_start") {
    return {
      kind: "tool-call-start",
      title: "Preparing tool",
      summary: payload.input_summary || payload.step_summary || payload.tool_name || "",
      meta: payload.tool_name || payload.action || "",
    };
  }
  if (eventName === "tool_call_result") {
    return {
      kind: payload.skipped
        ? "tool-call-result skipped"
        : payload.succeeded === false
          ? "tool-call-result failed"
          : "tool-call-result",
      title: "Tool result",
      summary: payload.observation_summary || payload.output_summary || payload.step_summary || "",
      meta: payload.tool_name || payload.action || "",
    };
  }
  return {
    kind: "agent-step",
    title: "Agent step",
    summary: userFacingAgentSummary(
      payload.step_summary || payload.decision_summary || payload.action || "",
    ),
    meta: payload.action || payload.phase || "",
  };
}

function localizeAgentAction(action) {
  const labels = {
    llm_with_tools: "分析问题并选择检索工具",
    search_knowledge: "检索知识库",
    rewrite_query: "改写问题",
    answer_with_citations: "结合证据回答",
    refuse: "拒答",
    final_answer: "完成回答",
  };
  return labels[action] || action || "处理";
}

function localizeAgentTool(toolName) {
  const labels = {
    search_knowledge: "检索知识库",
    hybrid_search_knowledge: "混合检索知识库",
    answer_with_citations: "生成带引用回答",
    rewrite_query: "改写问题",
    refuse: "拒答",
    final_answer: "完成回答",
  };
  return labels[toolName] || toolName || "工具";
}

function isSkippedAgentStep(step = {}) {
  const text = `${step.error || ""} ${step.output_summary || ""} ${step.observation_summary || ""}`.toLowerCase();
  return text.includes("skipped") || step.skipped === true;
}

function userFacingAgentSummary(summary) {
  const text = String(summary || "");
  const normalized = text.toLowerCase();
  if (!text) {
    return "";
  }
  if (normalized.includes("calling model with tool definitions") || normalized.includes("llm_with_tools")) {
    return "正在分析问题并选择检索工具";
  }
  if (normalized.includes("near-duplicate") || normalized.includes("existing evidence available")) {
    return "已有可用证据，跳过重复工具调用";
  }
  if (normalized.includes("model request failed") || normalized.includes("llm") || normalized.includes("provider")) {
    return "模型服务暂时不可用，系统已转入错误处理";
  }
  return text;
}

function agentLiveStatusText(eventName, payload = {}) {
  if (eventName === "tool_call_start") {
    return `正在调用：${localizeAgentTool(payload.tool_name || payload.action)}`;
  }
  if (eventName === "tool_call_result") {
    if (payload.skipped) {
      return `${localizeAgentTool(payload.tool_name || payload.action)} 已跳过重复调用`;
    }
    return payload.succeeded === false
      ? `${localizeAgentTool(payload.tool_name || payload.action)} 调用失败`
      : `${localizeAgentTool(payload.tool_name || payload.action)} 已返回`;
  }
  return `正在${localizeAgentAction(payload.action)}`;
}

function appendAgentLiveStep(messageElement, eventName, payload = {}) {
  if (!messageElement) {
    return;
  }
  messageElement._agentThoughtEvents = messageElement._agentThoughtEvents || [];
  messageElement._agentThoughtEvents.push({ eventName, payload });
  const status = messageElement.querySelector("[data-agent-thinking-status]");
  if (status) {
    status.textContent = agentLiveStatusText(eventName, payload);
  }
  const list = messageElement.querySelector("[data-agent-live-steps]");
  if (!list) {
    return;
  }
  const view = liveAgentEventView(eventName, payload);
  list.insertAdjacentHTML(
    "beforeend",
    `
      <article class="agent-live-step agent-live-step--${escapeHtml(view.kind)}">
        <div class="agent-live-step-heading">
          <span class="agent-live-step-kind">${escapeHtml(view.title)}</span>
          ${view.meta ? `<span class="pill neutral">${escapeHtml(view.meta)}</span>` : ""}
        </div>
        ${view.summary ? `<p class="agent-live-step-summary">${escapeHtml(view.summary)}</p>` : ""}
      </article>
    `,
  );
  scrollAgentChatToBottom();
}

function agentThoughtStepHtml(step, index) {
  const action = localizeAgentAction(step.action || step.name || step.tool_name);
  const skipped = isSkippedAgentStep(step);
  const succeeded = step.succeeded !== false || skipped;
  const statusText = skipped ? "已跳过" : succeeded ? "完成" : "已处理";
  const input = step.input_summary ? `<div class="agent-thought-line">输入：${escapeHtml(userFacingAgentSummary(step.input_summary))}</div>` : "";
  const output = step.output_summary ? `<div class="agent-thought-line">结果：${escapeHtml(userFacingAgentSummary(step.output_summary))}</div>` : "";
  const error = step.error && !skipped
    ? `<div class="agent-thought-line agent-thought-line--error">说明：${escapeHtml(userFacingAgentSummary(step.error))}</div>`
    : "";
  return `
    <li class="agent-thought-step">
      <div class="agent-thought-step-title">
        <span>${index + 1}. ${escapeHtml(action)}</span>
        <span class="pill ${succeeded ? "neutral" : "warning"}">${escapeHtml(statusText)}</span>
      </div>
      ${input}
      ${output}
      ${error}
    </li>
  `;
}

function agentThoughtHtml(result = {}) {
  const workflowSteps = result.workflow_steps || [];
  const toolCalls = result.tool_calls || [];
  const steps = workflowSteps.length
    ? workflowSteps
    : toolCalls.map((call) => ({
        action: call.tool_name,
        name: call.tool_name,
        input_summary: call.input_summary,
        output_summary: call.output_summary,
        succeeded: call.succeeded,
        error: call.error,
      }));
  if (!steps.length) {
    return "";
  }
  return `
    <details class="agent-thought-panel">
      <summary>查看思考过程</summary>
      <ol class="agent-thought-list">
        ${steps.map((step, index) => agentThoughtStepHtml(step, index)).join("")}
      </ol>
    </details>
  `;
}

function appendTokenToAgentMessage(messageElement, token) {
  if (!messageElement) {
    return;
  }
  const answerText = messageElement.querySelector(".answer-text");
  if (!answerText) {
    return;
  }
  if (messageElement.classList.contains("chat-message--thinking")) {
    messageElement.classList.remove("chat-message--thinking");
    answerText.classList.remove("thinking-text");
    answerText.textContent = "";
    const status = messageElement.querySelector("[data-agent-thinking-status]");
    if (status) {
      status.textContent = "正在生成回答";
    }
  }
  answerText.textContent += token;
  scrollAgentChatToBottom();
}

function createAgentTokenFlushScheduler({ onFlush, maxDelayMs = 32 } = {}) {
  let tokenBuffer = "";
  let frameId = null;
  let timeoutId = null;

  const clearScheduledFlush = () => {
    if (frameId !== null) {
      cancelAnimationFrame(frameId);
      frameId = null;
    }
    if (timeoutId !== null) {
      window.clearTimeout(timeoutId);
      timeoutId = null;
    }
  };

  const flush = () => {
    clearScheduledFlush();
    if (!tokenBuffer) {
      return;
    }
    const text = tokenBuffer;
    tokenBuffer = "";
    onFlush?.(text);
  };

  const schedule = () => {
    if (frameId === null) {
      frameId = requestAnimationFrame(flush);
    }
    if (timeoutId === null) {
      timeoutId = window.setTimeout(flush, maxDelayMs);
    }
  };

  return {
    push(token) {
      tokenBuffer += String(token || "");
      schedule();
    },
    flushNow() {
      flush();
    },
    cancel() {
      clearScheduledFlush();
      tokenBuffer = "";
    },
  };
}

function markAgentStreamingAborted(messageElement) {
  if (!messageElement) {
    return;
  }
  messageElement.classList.remove("chat-message--thinking");
  messageElement.classList.add("chat-message--aborted");
  const answerText = messageElement.querySelector(".answer-text");
  if (answerText) {
    const wasThinkingText = answerText.classList.contains("thinking-text");
    answerText.classList.remove("thinking-text");
    if (wasThinkingText || !answerText.textContent.trim()) {
      answerText.textContent = "";
    }
  }
  const status = messageElement.querySelector("[data-agent-thinking-status]");
  if (status) {
    status.textContent = "已停止生成";
  }
  const liveSteps = messageElement.querySelector("[data-agent-live-steps]");
  if (liveSteps && !liveSteps.children.length) {
    liveSteps.remove();
  }
  const bubble = messageElement.querySelector(".chat-message-bubble");
  if (bubble && !bubble.querySelector("[data-agent-abort-status]")) {
    bubble.insertAdjacentHTML(
      "beforeend",
      sanitizeRenderedHtml('<p class="agent-stream-status" data-agent-abort-status>已停止生成</p>'),
    );
  }
  scrollAgentChatToBottom();
}

function finalizeAgentStreamingMessage(messageElement, result) {
  result = normalizeCitationDisplay(result);
  if (!messageElement) {
    appendAgentAssistantMessage(result);
    return;
  }
  const bubble = messageElement.querySelector(".chat-message-bubble");
  if (!bubble) {
    appendAgentAssistantMessage(result);
    return;
  }
  messageElement.classList.remove("chat-message--thinking");

  const answerText = bubble.querySelector(".answer-text");
  if (!answerText || !answerText.textContent.trim()) {
    bubble.innerHTML = sanitizeRenderedHtml(`
      <div class="chat-message-role">Agent</div>
      ${agentAnswerHtml(result)}
    `);
    scrollAgentChatToBottom();
    return;
  }

  bubble.querySelector("[data-agent-thinking-status]")?.remove();
  bubble.querySelector("[data-agent-live-steps]")?.remove();
  answerText.insertAdjacentHTML("beforebegin", sanitizeRenderedHtml(agentThoughtHtml(result)));
  answerText.innerHTML = sanitizeRenderedHtml(
    renderAnswerWithCitationLinks(
      result.answer,
      result.sources || [],
      result.invalid_citations || [],
      result.citation_source_map || {},
    ),
  );

  if (result.refused) {
    const refusalCategory = result.refusal_category
      ? `<p class="refusal-category">分类：${escapeHtml(formatRefusalCategory(result.refusal_category))} / ${escapeHtml(result.refusal_category)}</p>`
      : "";
    answerText.insertAdjacentHTML(
      "beforebegin",
      `<div class="refusal"><strong>拒答</strong>${refusalCategory}<p>${escapeHtml(result.refusal_reason || "资料不足")}</p></div>`,
    );
  }

  const invalidCitationSet = new Set((result.invalid_citations || []).map((c) => String(c)));
  const citationBadges = (result.citations || [])
    .map((c) => {
      const isInvalid = invalidCitationSet.has(String(c));
      return `${citationReferenceHtml(c, result.sources || [], isInvalid, result.citation_source_map?.[String(c)] || c)}${isInvalid ? '<span class="pill danger">无效</span>' : ""}`;
    })
    .join("");
  const orphanInvalidBadges = (result.invalid_citations || [])
    .filter((c) => !(result.citations || []).map((i) => String(i)).includes(String(c)))
    .map((c) => `<span class="pill danger">[${escapeHtml(c)}] 无效</span>`)
    .join("");
  const sourceBadges = (result.sources || [])
    .slice(0, 5)
    .map((s) => `<span class="pill neutral">${escapeHtml(s.source_id)}</span>`)
    .join("");
  const modeBadge = `<span class="pill neutral">mode: ${escapeHtml(result.mode || "default")}</span>`;
  const iterationBadge = `<span class="pill neutral">iterations: ${escapeHtml(result.iteration_count ?? 0)}</span>`;

  answerText.insertAdjacentHTML(
    "afterend",
    `
    <div class="answer-meta">
      ${citationBadges || '<span class="pill neutral">无引用</span>'}
      ${orphanInvalidBadges}
      ${sourceBadges || '<span class="pill neutral">无来源</span>'}
      ${modeBadge}
      ${iterationBadge}
    </div>
    <p class="meta-line">${escapeHtml(result.reasoning_summary || "")}</p>
    `,
  );
  scrollAgentChatToBottom();
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
            <p>${escapeHtml(message || "请求失败，请稍后重试；如持续失败，请检查服务日志。")}</p>
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
  result = normalizeCitationDisplay(result);
  const invalidCitationSet = new Set((result.invalid_citations || []).map((citation) => String(citation)));
  const citationBadges = (result.citations || [])
    .map((citation) => {
      const isInvalid = invalidCitationSet.has(String(citation));
      return `${citationReferenceHtml(citation, result.sources || [], isInvalid, result.citation_source_map?.[String(citation)] || citation)}${isInvalid ? '<span class="pill danger">无效</span>' : ""}`;
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
  return sanitizeRenderedHtml(`
    ${agentThoughtHtml(result)}
    ${refused}
    <div class="answer-text">${renderAnswerWithCitationLinks(result.answer, result.sources || [], result.invalid_citations || [], result.citation_source_map || {})}</div>
    <div class="answer-meta">
      ${citationBadges || '<span class="pill neutral">无引用</span>'}
      ${orphanInvalidBadges}
      ${sourceBadges || '<span class="pill neutral">无来源</span>'}
      ${modeBadge}
      ${iterationBadge}
    </div>
    <p class="meta-line">${escapeHtml(result.reasoning_summary || "")}</p>
  `);
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
    abortAgentStream();
    return;
  }
  const questionInput = document.querySelector("[data-agent-question]");
  const question = questionInput?.value.trim();
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
      mode: "tool_calling_agent",
    };
    if (!state.currentConversationId) {
      const conversation = await createAgentConversation(conversationTitleFromQuestion(question));
      state.currentConversationId = conversation.id;
    }
    pendingUserMessage = appendAgentUserMessage(question);
    if (questionInput) {
      questionInput.value = "";
    }
    pendingThinkingMessage = appendAgentThinkingMessage();
    body.conversation_id = state.currentConversationId;
    if (sourceId) {
      body.source_id = sourceId;
    }
    let streamStarted = false;
    let result = null;
    const abortController = new AbortController();
    const tokenScheduler = createAgentTokenFlushScheduler({
      onFlush: (text) => {
        streamStarted = true;
        appendTokenToAgentMessage(pendingThinkingMessage, text);
      },
    });
    state.activeAgentAbortController = abortController;
    try {
      result = await streamAgentQuery(body, {
        abortController,
        onToken: (token) => {
          tokenScheduler.push(token);
        },
        onMetadata: (metadata) => {
          tokenScheduler.flushNow();
          result = metadata;
          finalizeAgentStreamingMessage(pendingThinkingMessage, metadata);
          pendingThinkingMessage = null;
          updateAgentModeStatus(metadata.mode || "default");
          if ((metadata.workflow_steps || []).length) {
            renderAgentWorkflowSteps(metadata.workflow_steps || []);
          } else {
            renderAgentToolCalls(metadata.tool_calls || []);
          }
        },
        onAgentStep: (payload) => {
          appendAgentLiveStep(pendingThinkingMessage, "agent_step", payload);
        },
        onToolCallStart: (payload) => {
          appendAgentLiveStep(pendingThinkingMessage, "tool_call_start", payload);
        },
        onToolCallResult: (payload) => {
          appendAgentLiveStep(pendingThinkingMessage, "tool_call_result", payload);
        },
        onDone: () => {
          tokenScheduler.flushNow();
        },
        onError: () => {
          tokenScheduler.flushNow();
        },
        onAbort: () => {
          tokenScheduler.flushNow();
        },
      });
    } catch (streamError) {
      if (isAgentAbortError(streamError)) {
        tokenScheduler.flushNow();
        markAgentStreamingAborted(pendingThinkingMessage);
        pendingThinkingMessage = null;
        result = { aborted: true, refused: false };
      } else if (streamStarted) {
        throw streamError;
      } else {
        result = await fetchJson(apiEndpoints.agent, {
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
      }
    }
    setApiStatus(result?.aborted ? "Agent 已停止生成" : result?.refused ? "Agent 已拒答" : "Agent 已完成");
    setAgentPanelStatus(result?.aborted ? "aborted" : result?.refused ? "refused" : "answered");
    await refreshConversationList();
  } catch (error) {
    pendingThinkingMessage?.remove();
    setAgentPanelStatus("error");
    updateAgentModeStatus("auto");
    appendAgentErrorMessage(userFriendlyErrorMessage(error));
    throw error;
  } finally {
    state.activeAgentAbortController = null;
    setAgentBusy(false);
  }
}

async function streamAgentQuery(body, handlers = {}) {
  const abortController = handlers.abortController || new AbortController();
  let response = null;
  try {
    response = await fetch(apiEndpoints.agentStream, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
      },
      body: JSON.stringify(body),
      signal: handlers.signal || abortController.signal,
    });
  } catch (error) {
    if (isAgentAbortError(error)) {
      await handlers.onAbort?.();
    }
    throw error;
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const detail = payload.detail || `HTTP ${response.status}`;
    throw new Error(Array.isArray(detail) ? detail.map((item) => item.msg).join("; ") : detail);
  }
  if (!response.body || !response.body.getReader) {
    throw new Error("当前浏览器不支持流式读取，已切换为同步请求");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let metadata = null;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const parsed = await consumeSseBuffer(buffer, handlers);
      buffer = parsed.remaining;
      if (parsed.metadata) {
        metadata = parsed.metadata;
      }
    }
  } catch (error) {
    if (isAgentAbortError(error)) {
      await handlers.onAbort?.();
    }
    throw error;
  }
  buffer += decoder.decode();
  if (buffer.trim()) {
    const parsed = await consumeSseBuffer(`${buffer}\n\n`, handlers);
    if (parsed.metadata) {
      metadata = parsed.metadata;
    }
  }
  if (!metadata) {
    throw new Error("流式响应缺少 metadata 事件");
  }
  return metadata;
}

async function consumeSseBuffer(buffer, handlers = {}) {
  let remaining = buffer;
  let metadata = null;
  while (true) {
    const boundary = remaining.indexOf("\n\n");
    if (boundary === -1) {
      break;
    }
    const rawEvent = remaining.slice(0, boundary);
    remaining = remaining.slice(boundary + 2);
    const event = parseSseEvent(rawEvent);
    if (!event.name) {
      continue;
    }
    if (event.name === "token") {
      await handlers.onToken?.(event.data.text || "");
    } else if (event.name === "metadata") {
      metadata = event.data;
      await handlers.onMetadata?.(event.data);
    } else if (event.name === "agent_step") {
      await handlers.onAgentStep?.(event.data);
    } else if (event.name === "tool_call_start") {
      await handlers.onToolCallStart?.(event.data);
    } else if (event.name === "tool_call_result") {
      await handlers.onToolCallResult?.(event.data);
    } else if (event.name === "done") {
      await handlers.onDone?.(event.data);
    } else if (event.name === "error") {
      await handlers.onError?.(event.data);
      throw new Error(event.data.detail || "流式响应失败");
    }
  }
  return { remaining, metadata };
}

function waitForAgentTokenPaint() {
  return new Promise((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(resolve));
  });
}

function parseSseEvent(rawEvent) {
  let name = "";
  const dataLines = [];
  for (const line of rawEvent.split(/\r?\n/)) {
    if (line.startsWith("event:")) {
      name = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trim());
    }
  }
  const rawData = dataLines.join("\n") || "{}";
  return {
    name,
    data: JSON.parse(rawData),
  };
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

function bindEnterToSubmit() {
  document.addEventListener(
    "keydown",
    (event) => {
      const textarea = event.target?.closest?.("textarea[data-agent-question], textarea[data-chat-question]");
      if (!textarea || event.key !== "Enter" || event.shiftKey || event.isComposing) {
        return;
      }
      const form = textarea.closest("form");
      if (!form) {
        return;
      }
      event.preventDefault();
      if (typeof form.requestSubmit === "function") {
        form.requestSubmit();
      } else {
        form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      }
    },
    true,
  );
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
  document.querySelector("[data-agent-submit]")?.addEventListener("click", (event) => {
    if (!state.agentRequestInFlight) {
      return;
    }
    event.preventDefault();
    abortAgentStream();
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
  bindEnterToSubmit();
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

function switchView(viewName) {
  const targetView = viewName === "library" ? "library" : "ask";
  state.currentView = targetView;
  document.querySelectorAll("[data-view]").forEach((section) => {
    const isActive = section.dataset.view === targetView;
    section.hidden = !isActive;
    section.classList.toggle("is-active", isActive);
  });
  document.querySelectorAll("[data-view-target]").forEach((link) => {
    const isActive = link.dataset.viewTarget === targetView;
    if (isActive) {
      link.setAttribute("aria-current", "page");
    } else {
      link.removeAttribute("aria-current");
    }
  });
}

function bindViewNavigation() {
  document.querySelectorAll("[data-view-target]").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      switchView(link.dataset.viewTarget);
      window.history.replaceState(null, "", link.getAttribute("href") || "#ask-view");
    });
  });
  if (window.location.hash === "#library-view" || window.location.hash === "#library-panel") {
    switchView("library");
  } else {
    switchView("ask");
  }
}

async function initializeShell() {
  bindViewNavigation();
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
  abortAgentStream,
  fetchJson,
  isAgentAbortError,
  markAgentStreamingAborted,
  sanitizeRenderedHtml,
  setApiStatus,
};

initializeShell();
