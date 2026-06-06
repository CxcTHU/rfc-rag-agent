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
};

const state = {
  sources: [],
  documents: [],
  sourceFilters: {
    keyword: "",
    status: "",
    permission: "",
  },
};

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload.detail || `HTTP ${response.status}`;
    throw new Error(Array.isArray(detail) ? detail.map((item) => item.msg).join("; ") : detail);
  }
  return payload;
}

function setApiStatus(message) {
  const status = document.querySelector("[data-api-status]");
  if (status) {
    status.textContent = message;
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

function renderAgentAnswer(result) {
  const answerBox = document.querySelector("[data-agent-answer-box]");
  const status = document.querySelector("[data-agent-status]");
  if (!answerBox) {
    return;
  }
  if (status) {
    status.textContent = result.refused ? "refused" : "answered";
  }
  const citationBadges = (result.citations || [])
    .map((citation) => `<span class="pill">[${escapeHtml(citation)}]</span>`)
    .join("");
  const sourceBadges = (result.sources || [])
    .slice(0, 5)
    .map((source) => `<span class="pill neutral">${escapeHtml(source.source_id)}</span>`)
    .join("");
  const refused = result.refused
    ? `<div class="refusal"><strong>拒答</strong><p>${escapeHtml(result.refusal_reason || "资料不足")}</p></div>`
    : "";
  answerBox.innerHTML = `
    ${refused}
    <div class="answer-text">${escapeHtml(result.answer)}</div>
    <div class="answer-meta">
      ${citationBadges || '<span class="pill neutral">无引用</span>'}
      ${sourceBadges || '<span class="pill neutral">无来源</span>'}
    </div>
    <p class="meta-line">${escapeHtml(result.reasoning_summary || "")}</p>
  `;
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
  const question = document.querySelector("[data-agent-question]")?.value.trim();
  const topK = Number(document.querySelector("[data-agent-top-k]")?.value || 5);
  const maxToolCalls = Number(document.querySelector("[data-agent-max-tool-calls]")?.value || 2);
  const sourceId = document.querySelector("[data-agent-source-id]")?.value.trim();
  if (!question) {
    setApiStatus("请输入 Agent 任务");
    return;
  }
  setApiStatus("Agent 运行中");
  const body = {
    question,
    top_k: topK,
    max_tool_calls: maxToolCalls,
  };
  if (sourceId) {
    body.source_id = sourceId;
  }
  const result = await fetchJson(apiEndpoints.agent, {
    method: "POST",
    body: JSON.stringify(body),
  });
  renderAgentAnswer(result);
  renderAgentToolCalls(result.tool_calls || []);
  setApiStatus(result.refused ? "Agent 已拒答" : "Agent 已完成");
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
      setApiStatus(`Agent 失败：${error.message}`);
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
