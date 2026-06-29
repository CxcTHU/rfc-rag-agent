const apiEndpoints = {
  authRegister: "/auth/register",
  authLogin: "/auth/login",
  authMe: "/auth/me",
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
  imageUpload: "/agent/upload-image",
  feedback: "/feedback",
  conversations: "/conversations",
  conversation: (conversationId) => `/conversations/${encodeURIComponent(conversationId)}`,
  conversationMessages: (conversationId) => `/conversations/${encodeURIComponent(conversationId)}/messages`,
};

const AUTH_TOKEN_STORAGE_KEY = "rfc-rag-agent.authToken";

function storedAuthToken() {
  return window.localStorage?.getItem(AUTH_TOKEN_STORAGE_KEY) || window.sessionStorage?.getItem(AUTH_TOKEN_STORAGE_KEY) || "";
}

function authRememberMeSelected() {
  const activeForm = document.querySelector(".auth-form:not([hidden])");
  const checkbox = activeForm?.querySelector("[data-auth-remember]");
  return checkbox ? Boolean(checkbox.checked) : true;
}

const state = {
  sources: [],
  documents: [],
  authToken: storedAuthToken(),
  currentUser: null,
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
  citationSets: {},
  nextCitationSetId: 1,
  contextMenuConversationId: null,
  pendingUploadedImage: null,
  figureLightboxRotation: 0,
};

const ANSWER_SEGMENT_MAX_CHARS = 1200;
const AGENT_THINKING_TIMER_INTERVAL_MS = 500;

function authHeaders() {
  return state.authToken ? { Authorization: `Bearer ${state.authToken}` } : {};
}

async function fetchJson(url, options = {}) {
  const { timeoutMs, ...fetchOptions } = options;
  const controller = timeoutMs ? new AbortController() : null;
  const timeoutId = controller ? window.setTimeout(() => controller.abort(), timeoutMs) : null;
  const response = await fetch(url, {
    ...fetchOptions,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(fetchOptions.headers || {}),
    },
    signal: controller?.signal || fetchOptions.signal,
  }).catch((error) => {
    if (timeoutId) {
      window.clearTimeout(timeoutId);
    }
    if (error.name === "AbortError") {
      throw new Error("Request timed out: backend or model service did not respond. Please retry later.");
    }
    throw error;
  });
  try {
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = payload.detail || `HTTP ${response.status}`;
      const error = new Error(Array.isArray(detail) ? detail.map((item) => item.msg).join("; ") : detail);
      error.status = response.status;
      error.url = url;
      throw error;
    }
    return payload;
  } finally {
    if (timeoutId) {
      window.clearTimeout(timeoutId);
    }
  }
}

async function fetchMultipartJson(url, formData, options = {}) {
  const response = await fetch(url, {
    method: options.method || "POST",
    headers: authHeaders(),
    body: formData,
    signal: options.signal,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload.detail || `HTTP ${response.status}`;
    const error = new Error(Array.isArray(detail) ? detail.map((item) => item.msg).join("; ") : detail);
    error.status = response.status;
    error.url = url;
    throw error;
  }
  return payload;
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

function authRequiredMessage() {
  return "请先登录或创建账号，再使用 Agent 对话。";
}

function setAuthHelp(message, isError = false) {
  const help = document.querySelector("[data-auth-help]");
  if (!help) {
    return;
  }
  help.textContent = message || "用户名至少 3 位且不能有空格；密码需为 8 到 72 位字符。";
  help.classList.toggle("is-error", Boolean(isError));
}

function authErrorMessage(error) {
  const message = String(error?.message || "").trim();
  if (message.includes("value is not a valid email address")) {
    return "请输入有效邮箱，例如 ethan@example.com。";
  }
  if (message.includes("String should have at least 8 characters") || message.includes("at least 8")) {
    return "密码至少需要 8 位字符。";
  }
  if (message.includes("String should have at least 3 characters") || message.includes("at least 3")) {
    return "用户名至少需要 3 位字符。";
  }
  if (message.includes("username must not contain whitespace")) {
    return "用户名不能包含空格。";
  }
  if (message.includes("already")) {
    return "该用户名或邮箱已经注册，请尝试直接登录。";
  }
  if (error?.status === 404 || message.includes("Not Found") || message.includes("HTTP 404")) {
    return `请求的接口不存在：${error?.url || "未知接口"}。请按 Ctrl + F5 强制刷新后重试。`;
  }
  return message || "认证失败，请检查表单后重试。";
}

function setAuthMode(mode) {
  const targetMode = mode === "register" ? "register" : "login";
  document.querySelectorAll("[data-auth-mode]").forEach((button) => {
    const isActive = button.dataset.authMode === targetMode;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-selected", String(isActive));
  });
  const loginForm = document.querySelector("[data-auth-login-form]");
  const registerForm = document.querySelector("[data-auth-register-form]");
  if (loginForm) {
    loginForm.hidden = targetMode !== "login";
  }
  if (registerForm) {
    registerForm.hidden = targetMode !== "register";
  }
  setAuthHelp(targetMode === "register" ? "用户名至少 3 位且不能有空格；密码需为 8 到 72 位字符。" : "可使用用户名或邮箱登录。");
}

function ensureAuthenticated() {
  if (state.authToken) {
    return true;
  }
  setApiStatus(authRequiredMessage());
  setAgentPanelStatus("sign_in_required");
  setConversationListPlaceholder("登录后加载会话");
  return false;
}

function renderAuthState() {
  const statusNode = document.querySelector("[data-auth-status]");
  const usernameNode = document.querySelector("[data-auth-username]");
  const logoutButton = document.querySelector("[data-auth-logout]");
  const authScreen = document.querySelector("[data-auth-screen]");
  const workspace = document.querySelector("[data-workspace-band]");
  const appShell = document.querySelector("[data-app-shell]");
  const isSignedIn = Boolean(state.authToken && state.currentUser);
  appShell?.classList.toggle("is-signed-in", isSignedIn);
  appShell?.classList.toggle("is-signed-out", !isSignedIn);
  if (authScreen) {
    authScreen.hidden = isSignedIn;
  }
  if (workspace) {
    workspace.hidden = !isSignedIn;
  }
  if (statusNode) {
    statusNode.textContent = isSignedIn ? "已登录" : state.authToken ? "已保存登录状态" : "访客";
  }
  if (usernameNode) {
    usernameNode.textContent = state.currentUser?.username || "未登录";
  }
  if (logoutButton) {
    logoutButton.hidden = !state.authToken;
  }
}

function setAuthSession(token, user, { remember = true } = {}) {
  state.authToken = token || "";
  state.currentUser = user || null;
  if (state.authToken) {
    const storage = remember ? window.localStorage : window.sessionStorage;
    const fallbackStorage = remember ? window.sessionStorage : window.localStorage;
    storage?.setItem(AUTH_TOKEN_STORAGE_KEY, state.authToken);
    fallbackStorage?.removeItem(AUTH_TOKEN_STORAGE_KEY);
  } else {
    window.localStorage?.removeItem(AUTH_TOKEN_STORAGE_KEY);
    window.sessionStorage?.removeItem(AUTH_TOKEN_STORAGE_KEY);
  }
  renderAuthState();
}

function clearAuthSession() {
  setAuthSession("", null);
  state.conversations = [];
  state.currentConversationId = null;
  renderConversationList();
  setConversationListPlaceholder("登录后加载会话");
}

async function loadCurrentUserFromToken() {
  if (!state.authToken) {
    renderAuthState();
    return;
  }
  try {
    state.currentUser = await fetchJson(apiEndpoints.authMe);
  } catch (error) {
    clearAuthSession();
    setApiStatus(`需要重新登录：${error.message}`);
  }
  renderAuthState();
}

async function submitAuthLogin() {
  const identity = document.querySelector("[data-auth-login-identity]")?.value.trim();
  const password = document.querySelector("[data-auth-login-password]")?.value || "";
  if (!identity || !password) {
    setAuthHelp("请输入用户名或邮箱，以及密码。", true);
    setApiStatus("请输入用户名或邮箱和密码");
    return;
  }
  try {
    const payload = await fetchJson(apiEndpoints.authLogin, {
      method: "POST",
      body: JSON.stringify({ username_or_email: identity, password }),
    });
    setAuthSession(payload.access_token, payload.user, { remember: authRememberMeSelected() });
    setAuthHelp("登录成功，正在加载工作台...");
    setApiStatus("已登录");
    enterApp("ask", "#ask-view");
    await loadAgentConversations();
  } catch (error) {
    const message = authErrorMessage(error);
    setAuthHelp(message, true);
    throw new Error(message);
  }
}

async function submitAuthRegister() {
  const username = document.querySelector("[data-auth-register-username]")?.value.trim();
  const email = document.querySelector("[data-auth-register-email]")?.value.trim();
  const password = document.querySelector("[data-auth-register-password]")?.value || "";
  if (!username || !email || !password) {
    setAuthHelp("请输入用户名、邮箱和密码。", true);
    setApiStatus("请输入用户名、邮箱和密码");
    return;
  }
  if (username.length < 3 || /\s/.test(username)) {
    setAuthHelp("用户名至少 3 位，且不能包含空格。", true);
    setApiStatus("用户名不符合要求");
    return;
  }
  if (password.length < 8 || password.length > 72) {
    setAuthHelp("密码需为 8 到 72 位字符。", true);
    setApiStatus("密码不符合要求");
    return;
  }
  try {
    await fetchJson(apiEndpoints.authRegister, {
      method: "POST",
      body: JSON.stringify({ username, email, password }),
    });
    const payload = await fetchJson(apiEndpoints.authLogin, {
      method: "POST",
      body: JSON.stringify({ username_or_email: username, password }),
    });
    setAuthSession(payload.access_token, payload.user, { remember: authRememberMeSelected() });
    setAuthHelp("账号创建成功，正在进入工作台...");
    setApiStatus("已创建账号并登录");
    enterApp("ask", "#ask-view");
    await loadAgentConversations();
  } catch (error) {
    const message = authErrorMessage(error);
    setAuthHelp(message, true);
    throw new Error(message);
  }
}

// Legacy stop-generation contract markers: 停止生成 已停止生成 鍋滄鐢熸垚 宸插仠姝㈢敓鎴?
function setAgentBusy(isBusy) {
  state.agentRequestInFlight = isBusy;
  const submitButton = document.querySelector("[data-agent-submit]");
  const questionInput = document.querySelector("[data-agent-question]");
  if (submitButton) {
    submitButton.disabled = false;
    submitButton.textContent = isBusy ? "Stop" : "Run";
    submitButton.classList.toggle("command-button--stop", isBusy);
    submitButton.setAttribute("aria-label", isBusy ? "Stop generation" : "Run Agent");
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
  setApiStatus("Stopping generation");
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
  "ARTICLE",
  "BUTTON",
  "BR",
  "CODE",
  "DETAILS",
  "DIV",
  "IMG",
  "LI",
  "OL",
  "P",
  "SECTION",
  "SMALL",
  "SPAN",
  "STRONG",
  "SUMMARY",
  "TABLE",
  "TBODY",
  "TD",
  "TH",
  "THEAD",
  "TR",
]);

const SAFE_RENDERED_ATTRS = new Set([
  "aria-hidden",
  "aria-label",
  "alt",
  "class",
  "data-agent-abort-status",
  "data-citation-ref",
  "data-citation-set",
  "data-citation-source",
  "data-figure-meta",
  "data-figure-open",
  "data-figure-src",
  "data-figure-title",
  "data-source-cluster",
  "href",
  "loading",
  "open",
  "rel",
  "role",
  "src",
  "start",
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
  const normalized = compactText(question, "New conversation").replace(/\s+/g, " ");
  return normalized.length > 18 ? `${normalized.slice(0, 18)}...` : normalized;
}

function userFriendlyErrorMessage(error) {
  const message = String(error?.message || "").trim();
  if (message.includes("authentication required") || message.includes("HTTP 401")) {
    return authRequiredMessage();
  }
  if (message.includes("Request timed out") || message.includes("timeout") || error?.name === "AbortError") {
    return "Request timed out. Please retry after checking the model or retrieval service.";
  }
  if (message.includes("chat model provider") || message.includes("provider")) {
    return "Model service is temporarily unavailable. Please check local configuration and retry.";
  }
  if (message.includes("HTTP 503")) {
    return "Backend service is temporarily unavailable. Please retry later.";
  }
  if (message.includes("Failed to fetch") || message.includes("NetworkError")) {
    return "Network connection failed. Please confirm the backend service is running.";
  }
  return "Request failed. Please retry later or check service logs.";
}

function sourceForCitation(sources, citation, sourceCitation = citation) {
  const index = Number(sourceCitation) - 1;
  if (!Number.isInteger(index) || index < 0) {
    return null;
  }
  return sources?.[index] || null;
}

function sourceTitle(source) {
  return compactText(source?.title || source?.document_title, "Unknown source");
}

function sourceSummary(source) {
  return compactText(source?.content || source?.snippet, "No summary available").slice(0, 120);
}

function registerCitationSet(result = {}) {
  const citationSetId = `citation-set-${state.nextCitationSetId}`;
  state.nextCitationSetId += 1;
  state.citationSets[citationSetId] = {
    sources: result.sources || [],
    citations: result.citations || [],
    invalidCitations: result.invalid_citations || [],
    citationSourceMap: result.citation_source_map || {},
  };
  return citationSetId;
}

function citationReferenceHtml(citation, sources, isInvalid = false, sourceCitation = citation, citationSetId = "") {
  const source = sourceForCitation(sources, citation, sourceCitation);
  const label = `[${escapeHtml(citation)}]`;
  if (!source) {
    return `<span class="citation-ref citation-ref--missing ${isInvalid ? "citation-ref--invalid" : ""}">${label}</span>`;
  }
  const title = sourceTitle(source);
  const sourceType = compactText(source.source_type, "unknown");
  const summary = sourceSummary(source);
  const setAttr = citationSetId ? ` data-citation-set="${escapeHtml(citationSetId)}"` : "";
  return `<button class="citation-ref ${isInvalid ? "citation-ref--invalid" : ""}" type="button" data-citation-ref="${escapeHtml(citation)}" data-citation-source="${escapeHtml(sourceCitation)}"${setAttr} aria-label="View source ${escapeHtml(citation)}: ${escapeHtml(title)}">${label}<span class="citation-popover" role="tooltip"><strong>${escapeHtml(title)}</strong><small>${escapeHtml(sourceType)}</small><span>${escapeHtml(summary)}</span></span></button>`;
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

function renderAnswerWithCitationLinks(answer, sources = [], invalidCitations = [], citationSourceMap = {}, citationSetId = "") {
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
        citationSetId,
      );
    })
    .join("");
  return sanitizeRenderedHtml(rendered);
}

function isMarkdownTableRow(line) {
  const trimmed = String(line || "").trim();
  return trimmed.startsWith("|") && trimmed.endsWith("|") && trimmed.slice(1, -1).includes("|");
}

function splitMarkdownTableRow(line) {
  return String(line || "")
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function isMarkdownTableSeparator(line) {
  if (!isMarkdownTableRow(line)) {
    return false;
  }
  return splitMarkdownTableRow(line).every((cell) => /^:?-{3,}:?$/.test(cell));
}

function markdownTableHtml(tableLines, inline) {
  const rows = tableLines
    .filter((line) => !isMarkdownTableSeparator(line))
    .map(splitMarkdownTableRow)
    .filter((cells) => cells.length > 1);
  if (!rows.length) {
    return "";
  }
  const columnCount = Math.max(...rows.map((row) => row.length));
  const normalizedRows = rows.map((row) => {
    const cells = [...row];
    while (cells.length < columnCount) {
      cells.push("");
    }
    return cells;
  });
  const [header, ...bodyRows] = normalizedRows;
  const headerHtml = `<thead><tr>${header.map((cell) => `<th>${inline(cell)}</th>`).join("")}</tr></thead>`;
  const bodyHtml = bodyRows.length
    ? `<tbody>${bodyRows.map((row) => `<tr>${row.map((cell) => `<td>${inline(cell)}</td>`).join("")}</tr>`).join("")}</tbody>`
    : "";
  return `<div class="markdown-table-wrap"><table class="markdown-table">${headerHtml}${bodyHtml}</table></div>`;
}

function renderMarkdownBlocks(answer, sources = [], invalidCitations = [], citationSourceMap = {}, citationSetId = "") {
  const lines = String(answer || "").replace(/\r\n/g, "\n").split("\n");
  const blocks = [];
  let paragraphLines = [];
  let listItems = [];
  let listStart = 1;
  let nextListStart = 1;
  let tableLines = [];

  const inline = (text) =>
    renderAnswerWithCitationLinks(text, sources, invalidCitations, citationSourceMap, citationSetId);

  const flushParagraph = () => {
    if (!paragraphLines.length) {
      return;
    }
    const html = paragraphLines.map((line) => inline(line)).join("<br>");
    blocks.push(`<p>${html}</p>`);
    paragraphLines = [];
  };

  const flushList = () => {
    if (!listItems.length) {
      return;
    }
    const startAttr = listStart > 1 ? ` start="${listStart}"` : "";
    blocks.push(`<ol${startAttr}>${listItems.map((item) => `<li>${inline(item)}</li>`).join("")}</ol>`);
    nextListStart = listStart + listItems.length;
    listItems = [];
    listStart = nextListStart;
  };

  const flushTable = () => {
    if (!tableLines.length) {
      return;
    }
    const table = markdownTableHtml(tableLines, inline);
    if (table) {
      blocks.push(table);
    } else {
      paragraphLines.push(...tableLines.map((line) => line.trim()));
    }
    tableLines = [];
  };

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      flushParagraph();
      flushList();
      flushTable();
      continue;
    }
    if (isMarkdownTableRow(trimmed)) {
      flushParagraph();
      flushList();
      tableLines.push(trimmed);
      continue;
    }
    const bullet = trimmed.match(/^[-*]\s+(.+)$/);
    const numbered = trimmed.match(/^(\d+)[.)]\s+(.+)$/);
    if (bullet || numbered) {
      flushParagraph();
      flushTable();
      if (!listItems.length) {
        listStart = numbered ? Number(numbered[1]) || nextListStart : nextListStart;
      }
      listItems.push(bullet ? bullet[1] : numbered[2]);
      continue;
    }
    flushList();
    flushTable();
    paragraphLines.push(trimmed);
  }

  flushParagraph();
  flushList();
  flushTable();
  return sanitizeRenderedHtml(blocks.join(""));
}

function splitLongTextSegment(segment, maxChars = ANSWER_SEGMENT_MAX_CHARS) {
  const chunks = [];
  let remaining = String(segment || "").trim();
  while (remaining.length > maxChars) {
    const searchWindow = remaining.slice(0, maxChars);
    const breakAt = Math.max(
      searchWindow.lastIndexOf("\n"),
      searchWindow.lastIndexOf("."),
      searchWindow.lastIndexOf(". "),
      searchWindow.lastIndexOf("; "),
      searchWindow.lastIndexOf(";"),
      searchWindow.lastIndexOf(" "),
    );
    const cut = breakAt > Math.floor(maxChars * 0.45) ? breakAt + 1 : maxChars;
    chunks.push(remaining.slice(0, cut).trim());
    remaining = remaining.slice(cut).trim();
  }
  if (remaining) {
    chunks.push(remaining);
  }
  return chunks;
}

function answerRenderSegments(answer, maxChars = ANSWER_SEGMENT_MAX_CHARS) {
  const normalized = String(answer || "").replace(/\r\n/g, "\n").trim();
  if (!normalized) {
    return [""];
  }
  const paragraphSegments = normalized
    .split(/\n{2,}/)
    .map((segment) => segment.trim())
    .filter(Boolean);
  const seedSegments = paragraphSegments.length ? paragraphSegments : [normalized];
  return seedSegments.flatMap((segment) => splitLongTextSegment(segment, maxChars));
}

function renderAnswerSegmentsHtml(result = {}, citationSetId = "") {
  const segments = answerRenderSegments(result.answer || "");
  return segments
    .map((segment) => {
      const html = renderAnswerWithCitationLinks(
        segment,
        result.sources || [],
        result.invalid_citations || [],
        result.citation_source_map || {},
        citationSetId,
      );
      const blockHtml = renderMarkdownBlocks(
        segment,
        result.sources || [],
        result.invalid_citations || [],
        result.citation_source_map || {},
        citationSetId,
      );
      return `<div class="answer-segment">${blockHtml || html}</div>`;
    })
    .join("");
}

function renderSegmentedAnswerInto(answerText, result = {}) {
  if (!answerText) {
    return;
  }
  answerText.classList.add("answer-text--segmented");
  answerText.textContent = "";
  const citationSetId = registerCitationSet(result);
  const fragment = document.createDocumentFragment();
  const template = document.createElement("template");
  template.innerHTML = sanitizeRenderedHtml(renderAnswerSegmentsHtml(result, citationSetId));
  fragment.append(...Array.from(template.content.childNodes));
  answerText.appendChild(fragment);
  answerText.dataset.citationSet = citationSetId;
  return citationSetId;
}

function sourceClusterHtml(result = {}, citationSetId = "") {
  if (result.refused) {
    return "";
  }
  const citations = (result.citations || []).map((citation) => String(citation));
  if (!citations.length || !citationSetId) {
    return '<span class="source-cluster source-cluster--empty">No sources</span>';
  }
  const preview = citations
    .slice(0, 3)
    .map((citation) => `<span class="source-chip">[${escapeHtml(citation)}]</span>`)
    .join("");
  const more = citations.length > 3 ? `<span class="source-more">+${citations.length - 3}</span>` : "";
  return `<button class="source-cluster" type="button" data-source-cluster data-citation-set="${escapeHtml(citationSetId)}" aria-label="View ${escapeHtml(String(citations.length))} sources">${preview}${more}<span class="source-label">Sources</span></button>`;
}

function imageEvidenceSources(result = {}) {
  const sources = result.sources || [];
  const citations = (result.citations || []).map((citation) => String(citation));
  const citedSources = citations
    .map((citation) => {
      const sourceCitation = result.citation_source_map?.[citation] || citation;
      const source = sourceForCitation(sources, citation, sourceCitation);
      return source ? { source, citation } : null;
    })
    .filter(Boolean);
  const fallbackSources = sources.map((source, index) => ({ source, citation: String(index + 1) }));
  const candidates = [...citedSources, ...fallbackSources];
  const seen = new Set();
  const figures = [];
  for (const candidate of candidates) {
    const imageUrl = candidate.source?.image_url;
    if (!imageUrl || candidate.source?.chunk_type !== "image_description") {
      continue;
    }
    if (seen.has(imageUrl)) {
      continue;
    }
    seen.add(imageUrl);
    figures.push({ ...candidate, imageUrl });
    if (figures.length >= 4) {
      break;
    }
  }
  return figures;
}

function figureOriginalLabel(source = {}) {
  const imagePath = String(source.source_image_path || source.image_url || "");
  const pageMatch = imagePath.match(/page(\d+)_img(\d+)/i);
  if (!pageMatch) {
    return "原文图";
  }
  return `第 ${pageMatch[1]} 页 / 原文图 ${pageMatch[2]}`;
}

function figureSourceLine(source = {}, figureNumber = 1) {
  const title = sourceTitle(source);
  const pageNumber = Number(source.page_number);
  const pagePart = Number.isFinite(pageNumber) && pageNumber > 0
    ? `\u7b2c ${pageNumber} \u9875`
    : figureOriginalLabel(source);
  return `\u56fe ${figureNumber} \u2014 ${pagePart} \u2014 \u300a${title}\u300b`;
}

function figureEvidenceHtml(result = {}) {
  if (result.refused) {
    return "";
  }
  const figures = imageEvidenceSources(result);
  if (!figures.length) {
    return "";
  }
  const cards = figures
    .map(({ source, imageUrl }, index) => {
      const title = compactText(source.caption, sourceTitle(source));
      const summary = source.caption ? "" : sourceSummary(source);
      const summaryHtml = summary ? `<p>${escapeHtml(summary)}</p>` : "";
      const figureNumber = index + 1;
      const figureLabel = `Figure ${figureNumber}`;
      const sourceLine = figureSourceLine(source, figureNumber);
      const articleTitle = sourceTitle(source);
      const pageNumber = Number(source.page_number);
      const pageLabel = Number.isFinite(pageNumber) && pageNumber > 0
        ? `第 ${pageNumber} 页`
        : figureOriginalLabel(source);
      return `
        <article class="figure-card">
          <button class="figure-thumb" type="button" data-figure-open data-figure-src="${escapeHtml(imageUrl)}" data-figure-title="${escapeHtml(title)}" data-figure-meta="${escapeHtml(sourceLine)}" data-figure-rotation="0" aria-label="放大查看 ${escapeHtml(title)}">
            <img class="figure-image" src="${escapeHtml(imageUrl)}" alt="${escapeHtml(title)}" loading="lazy">
          </button>
          <div class="figure-body">
            <div class="figure-kicker">${escapeHtml(figureLabel)}</div>
            <strong>${escapeHtml(title)}</strong>
            <span class="figure-source-title">来源文章：《${escapeHtml(articleTitle)}》</span>
            <span class="figure-source-meta">${escapeHtml(pageLabel)} / ${escapeHtml(figureOriginalLabel(source))}</span>
            ${summaryHtml}
          </div>
        </article>
      `;
    })
    .join("");
  return `<section class="figure-evidence" aria-label="Related paper figures">${cards}</section>`;
}

function tableEvidenceSources(result = {}) {
  const sources = result.sources || [];
  const seen = new Set();
  return sources
    .filter((source) => source?.chunk_type === "table" || source?.table_content)
    .filter((source) => {
      const key = source.source_id || source.chunk_id || source.content;
      if (seen.has(key)) {
        return false;
      }
      seen.add(key);
      return true;
    })
    .slice(0, 3);
}

function tableEvidenceHtml(result = {}) {
  if (result.refused) {
    return "";
  }
  const tables = tableEvidenceSources(result);
  if (!tables.length) {
    return "";
  }
  const cards = tables
    .map((source, index) => {
      const tableText = source.table_content || source.content || "";
      const tableHtml = renderMarkdownBlocks(tableText);
      return `
        <article class="table-evidence-card">
          <div class="evidence-card-head">
            <span>Table ${index + 1}</span>
            ${citationLocationButtonHtml(source)}
          </div>
          <strong>${escapeHtml(sourceTitle(source))}</strong>
          <div class="table-evidence-content">${tableHtml || `<pre>${escapeHtml(tableText)}</pre>`}</div>
        </article>
      `;
    })
    .join("");
  return `<section class="table-evidence" aria-label="Table evidence">${cards}</section>`;
}

function imageAnalysisHtml(result = {}) {
  const analysis = result.image_analysis;
  if (!analysis || result.refused) {
    return "";
  }
  const description = analysis.is_test_vision
    ? "当前为测试模式视觉描述，不代表真实图片理解。请配置真实视觉模型后再分析上传图片。"
    : (analysis.image_description || analysis.fused_context || "");
  const status = result.refused
    ? "图片已处理，但最终拒答"
    : analysis.is_test_vision
      ? "测试模式视觉描述"
      : "Uploaded image analysis";
  const provider = analysis.vision_provider ? ` / ${analysis.vision_provider}` : "";
  const relevance = analysis.domain_relevance ? ` / ${analysis.domain_relevance}` : "";
  return `
    <section class="image-analysis-card" aria-label="Uploaded image analysis">
      <div class="evidence-card-head">
        <span>${escapeHtml(status)}</span>
        <small>${escapeHtml(String(analysis.related_text_count || 0))} text / ${escapeHtml(String(analysis.similar_figure_count || 0))} figures${escapeHtml(provider)}${escapeHtml(relevance)}</small>
      </div>
      <p>${escapeHtml(description)}</p>
    </section>
  `;
}

function citationLocationButtonHtml(source = {}) {
  const location = source.content_bbox;
  if (!location?.pdf_url && !location?.page_number) {
    return "";
  }
  const label = location.page_number ? `Page ${location.page_number}` : "Open source";
  const href = location.pdf_url || "#";
  return `<a class="location-link" href="${escapeHtml(href)}" target="_blank" rel="noopener" data-citation-location>${escapeHtml(label)}</a>`;
}

async function submitFeedback(result = {}, rating) {
  const payload = {
    question: result.question || "",
    answer: result.answer || "",
    rating,
  };
  if (rating === "negative") {
    payload.reason = "other";
  }
  await fetchJson(apiEndpoints.feedback, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  setApiStatus("Feedback saved");
}

function feedbackControlsHtml(result = {}) {
  if (result.refused) {
    return "";
  }
  if (!result.answer || !result.question) {
    return "";
  }
  const encoded = encodeURIComponent(JSON.stringify({
    question: result.question,
    answer: result.answer,
  }));
  return `
    <div class="feedback-controls" data-feedback-payload="${escapeHtml(encoded)}">
      <button type="button" class="feedback-button" data-feedback-rating="positive" title="Helpful">👍</button>
      <button type="button" class="feedback-button" data-feedback-rating="negative" title="Needs work">👎</button>
    </div>
  `;
}

function formatRefusalCategory(category) {
  const labels = {
    responsibility_gate_triggered: "Responsibility gate",
    evidence_insufficient: "Insufficient evidence",
    off_topic: "Off topic",
    service_error: "Retrieval service error",
  };
  return labels[category] || compactText(category, "Uncategorized");
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
    body.innerHTML = '<tr><td colspan="7" class="empty-cell">No sources match the current filters.</td></tr>';
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
    body.innerHTML = '<tr><td colspan="6" class="empty-cell">No documents have been indexed yet.</td></tr>';
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
    list.innerHTML = '<div class="empty-state">No matching chunks found.</div>';
    return;
  }
  list.innerHTML = results
    .map(
      (result) => `
        <article class="result-item">
          <h3>${escapeHtml(result.document_title)}</h3>
          <p>${escapeHtml(result.source_type)} - chunk ${escapeHtml(result.chunk_index)} - score ${Number(result.score || 0).toFixed(3)}</p>
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
    list.innerHTML = '<div class="empty-state">No chunks available.</div>';
    return;
  }
  list.innerHTML = chunks
    .map(
      (chunk) => `
        <article class="chunk-item">
          <h3>${escapeHtml(payload.title)} - chunk ${escapeHtml(chunk.chunk_index)}</h3>
          <p>${escapeHtml(compactText(chunk.heading_path))} - ${escapeHtml(chunk.char_count)} chars</p>
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
    setApiStatus("Please enter a search query");
    return;
  }
  setApiStatus("Searching...");
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
  setApiStatus("Search completed");
}

async function viewDocumentChunks(documentId) {
  setApiStatus("Loading chunks...");
  const payload = await fetchJson(apiEndpoints.documentChunks(documentId));
  renderChunks(payload);
  setApiStatus("Chunks loaded");
}

async function syncSources() {
  setApiStatus("Syncing sources...");
  const payload = await fetchJson(apiEndpoints.sourceSync, {
    method: "POST",
    body: JSON.stringify({ include_defaults: true }),
  });
  await loadWorkspaceData();
  setApiStatus(
    `Sources synced: total ${payload.total}, created ${payload.created}, updated ${payload.updated}, duplicates ${payload.duplicates}`,
  );
}

async function reindexSource(sourceId) {
  setApiStatus(`reindex ${sourceId}`);
  const payload = await fetchJson(apiEndpoints.sourceReindex(sourceId), {
    method: "POST",
    body: JSON.stringify({}),
  });
  await loadWorkspaceData();
  setApiStatus(`Reindex completed: document ${payload.document_id}`);
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
    ? '<div class="refusal"><strong>Refused</strong><p>' + escapeHtml(result.refusal_reason || "Insufficient evidence") + '</p></div>'
    : "";
  answerBox.innerHTML = `
    ${refused}
    <div class="answer-text">${renderAnswerWithCitationLinks(result.answer, result.sources || [], [], result.citation_source_map || {})}</div>
    <div class="answer-meta">
      ${citationBadges || '<span class="pill neutral">No citations</span>'}
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
    list.innerHTML = '<div class="empty-state">No citations available for this answer.</div>';
    return;
  }
  list.innerHTML = sources
    .map(
      (source) => `
        <article class="citation-item">
          <h3>[${escapeHtml(source.source_id)}] ${escapeHtml(source.document_title)}</h3>
          <p>${escapeHtml(source.source_type)} - chunk ${escapeHtml(source.chunk_index)} - score ${Number(source.score || 0).toFixed(3)}</p>
          <p class="meta-line">${escapeHtml(compactText(source.source_path))}</p>
          <div class="citation-snippet">${escapeHtml(source.content)}</div>
        </article>
      `,
    )
    .join("");
}

function citationDrawerItemHtml(displayCitation, source, isInvalid = false) {
  if (!source) {
    return `
      <article class="citation-drawer-item citation-drawer-item--missing" data-citation-drawer-item="${escapeHtml(displayCitation)}">
        <h3>[${escapeHtml(displayCitation)}] Source not found</h3>
        <p>This citation does not match a displayable source.</p>
      </article>
    `;
  }
  const title = sourceTitle(source);
  const sourceType = compactText(source.source_type, "unknown");
  const chunkInfo = source.chunk_index !== undefined && source.chunk_index !== null
    ? `Chunk ${escapeHtml(source.chunk_index)}`
    : "Chunk unavailable";
  const score = source.score !== undefined && source.score !== null ? ` / score ${Number(source.score || 0).toFixed(3)}` : "";
  const summary = compactText(source.content || source.snippet, "No summary available");
  const sourceLine = figureSourceLine(source);
  return `
    <article class="citation-drawer-item${isInvalid ? " citation-drawer-item--invalid" : ""}" data-citation-drawer-item="${escapeHtml(displayCitation)}">
      <div class="citation-drawer-item-head">
        <span class="citation-drawer-chip">[${escapeHtml(displayCitation)}]</span>
        <strong>${escapeHtml(title)}</strong>
      </div>
      <p>${escapeHtml(sourceType)} / ${chunkInfo}${score}</p>
      ${source.image_url ? `<button class="citation-drawer-image-button" type="button" data-figure-open data-figure-src="${escapeHtml(source.image_url)}" data-figure-title="${escapeHtml(title)}" data-figure-meta="${escapeHtml(sourceLine)}" data-figure-rotation="0" aria-label="放大查看 ${escapeHtml(title)}"><img class="citation-drawer-image" src="${escapeHtml(source.image_url)}" alt="${escapeHtml(title)}" loading="lazy"></button>` : ""}
      ${citationLocationButtonHtml(source)}
      <div class="citation-drawer-snippet">${escapeHtml(summary)}</div>
    </article>
  `;
}

function openCitationDrawer(citationSetId, preferredCitation = "") {
  const drawer = document.querySelector("[data-citation-drawer]");
  const list = document.querySelector("[data-citation-drawer-list]");
  const count = document.querySelector("[data-citation-drawer-count]");
  const citationSet = state.citationSets[citationSetId];
  if (!drawer || !list || !citationSet) {
    return;
  }
  const invalidSet = new Set((citationSet.invalidCitations || []).map((citation) => String(citation)));
  const citations = (citationSet.citations || []).map((citation) => String(citation));
  if (count) {
    count.textContent = `${citations.length} citations`;
  }
  list.innerHTML = citations.length
    ? citations
        .map((citation) => {
          const sourceCitation = citationSet.citationSourceMap?.[String(citation)] || citation;
          const source = sourceForCitation(citationSet.sources || [], citation, sourceCitation);
          return citationDrawerItemHtml(citation, source, invalidSet.has(String(citation)));
        })
        .join("")
    : '<div class="empty-state">No sources</div>';
  drawer.hidden = false;
  drawer.classList.add("is-open");
  const activeCitation = preferredCitation || citations[0] || "";
  list.querySelectorAll(".citation-drawer-item.is-active").forEach((item) => {
    item.classList.remove("is-active");
  });
  if (activeCitation) {
    const activeItem = list.querySelector(`[data-citation-drawer-item="${CSS.escape(String(activeCitation))}"]`);
    activeItem?.classList.add("is-active");
    activeItem?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }
}

function closeCitationDrawer() {
  const drawer = document.querySelector("[data-citation-drawer]");
  if (!drawer) {
    return;
  }
  drawer.classList.remove("is-open");
  drawer.hidden = true;
}

function ensureFigureLightbox() {
  let lightbox = document.querySelector("[data-figure-lightbox]");
  if (lightbox) {
    return lightbox;
  }
  lightbox = document.createElement("div");
  lightbox.className = "figure-lightbox";
  lightbox.dataset.figureLightbox = "";
  lightbox.hidden = true;
  lightbox.innerHTML = `
    <button class="figure-lightbox-backdrop" type="button" data-close-figure-lightbox aria-label="关闭图片预览"></button>
    <div class="figure-lightbox-panel" role="dialog" aria-modal="true" aria-label="论文图片预览">
      <button class="figure-lightbox-close" type="button" data-close-figure-lightbox aria-label="关闭图片预览">×</button>
      <img data-figure-lightbox-image alt="">
      <button class="figure-lightbox-rotate" type="button" data-rotate-figure-lightbox title="旋转图片">旋转</button>
      <div class="figure-lightbox-caption">
        <strong data-figure-lightbox-title></strong>
        <small data-figure-lightbox-meta></small>
      </div>
    </div>
  `;
  document.body.appendChild(lightbox);
  return lightbox;
}

function applyFigureLightboxRotation(lightbox) {
  const image = lightbox?.querySelector("[data-figure-lightbox-image]");
  if (image) {
    image.style.transform = `rotate(${state.figureLightboxRotation}deg)`;
  }
}

function openFigureLightbox({ src = "", title = "", meta = "", rotation = 0 } = {}) {
  if (!src) {
    return;
  }
  const lightbox = ensureFigureLightbox();
  state.figureLightboxRotation = Number(rotation) || 0;
  const image = lightbox.querySelector("[data-figure-lightbox-image]");
  const titleNode = lightbox.querySelector("[data-figure-lightbox-title]");
  const metaNode = lightbox.querySelector("[data-figure-lightbox-meta]");
  if (image) {
    image.src = src;
    image.alt = title || "论文图片";
    image.style.transform = `rotate(${state.figureLightboxRotation}deg)`;
  }
  if (titleNode) {
    titleNode.textContent = title || "论文图片";
  }
  if (metaNode) {
    metaNode.textContent = meta || "";
  }
  lightbox.hidden = false;
  lightbox.classList.add("is-open");
  document.body.classList.add("has-figure-lightbox");
  lightbox.querySelector("[data-close-figure-lightbox]")?.focus();
}

function rotateFigureLightbox() {
  const lightbox = document.querySelector("[data-figure-lightbox]");
  if (!lightbox || lightbox.hidden) {
    return;
  }
  state.figureLightboxRotation = (state.figureLightboxRotation + 90) % 360;
  applyFigureLightboxRotation(lightbox);
}

function closeFigureLightbox() {
  const lightbox = document.querySelector("[data-figure-lightbox]");
  if (!lightbox) {
    return;
  }
  lightbox.classList.remove("is-open");
  lightbox.hidden = true;
  document.body.classList.remove("has-figure-lightbox");
  const image = lightbox.querySelector("[data-figure-lightbox-image]");
  if (image) {
    image.removeAttribute("src");
    image.style.transform = "";
  }
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
    list.innerHTML = '<div class="empty-state">No tool calls</div>';
    return;
  }
  list.innerHTML = toolCalls
    .map((call, index) => {
      const succeeded = call.succeeded !== false;
      const name = localizeAgentTool(call.tool_name || call.action || `Step ${index + 1}`);
      return `
        <article class="tool-call-item">
          <div class="tool-call-head">
            <strong>${escapeHtml(name)}</strong>
            <span class="pill ${succeeded ? "neutral" : "warning"}">${escapeHtml(succeeded ? "Done" : "Failed")}</span>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderAgentWorkflowSteps(steps) {
  const list = document.querySelector("[data-agent-tools-list]");
  const count = document.querySelector("[data-agent-tools-count]");
  if (!list) {
    return;
  }
  if (count) {
    count.textContent = String(steps.length);
  }
  if (!steps.length) {
    list.innerHTML = '<div class="empty-state">No workflow steps</div>';
    return;
  }
  list.innerHTML = steps
    .map((step, index) => {
      const skipped = isSkippedAgentStep(step);
      const succeeded = step.succeeded !== false || skipped;
      const action = localizeAgentAction(step.name || step.tool_name || step.action || `Step ${index + 1}`);
      const status = skipped ? "Skipped" : succeeded ? "Done" : "Handled";
      return `
        <article class="tool-call-item">
          <div class="tool-call-head">
            <strong>${index + 1}. ${escapeHtml(action)}</strong>
            <span class="pill ${succeeded ? "neutral" : "warning"}">${escapeHtml(status)}</span>
          </div>
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
  answerBox.innerHTML = '<div class="empty-state">Ask a question to start the conversation.</div>';
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
          <div class="chat-message-role">User</div>
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
          <div class="chat-message-role">Agent</div>
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
          <div class="agent-thinking-status" data-agent-thinking-status>
            <span class="agent-thinking-label" data-agent-thinking-label><span class="loading-spinner" aria-hidden="true"></span>正在思考...</span>
            <span class="agent-thinking-timer" data-agent-thinking-timer>思考0秒</span>
          </div>
          <div class="agent-live-steps" data-agent-live-steps hidden aria-label="Agent 实时步骤"></div>
          <div class="answer-text thinking-text"></div>
        </div>
      </article>
    `,
  );
  scrollAgentChatToBottom();
  const messageElement = answerBox.lastElementChild;
  startAgentThinkingTimer(messageElement);
  return messageElement;
}

function agentThinkingElapsedMs(messageElement) {
  const startedAt = Number(messageElement?.dataset.agentThinkingStartedAt || 0);
  if (!startedAt) {
    return 0;
  }
  return Math.max(0, Date.now() - startedAt);
}

function formatAgentThinkingDuration(ms) {
  return `${Math.max(0, Math.ceil(Number(ms || 0) / 1000))}秒`;
}

function setAgentThinkingStatusLabel(messageElement, label, { showSpinner = false } = {}) {
  const status = messageElement?.querySelector("[data-agent-thinking-status]");
  if (!status) {
    return;
  }
  const labelElement = status.querySelector("[data-agent-thinking-label]");
  if (!labelElement) {
    status.textContent = label;
    return;
  }
  labelElement.textContent = label;
  if (showSpinner) {
    labelElement.insertAdjacentHTML("afterbegin", '<span class="loading-spinner" aria-hidden="true"></span>');
  }
}

function updateAgentThinkingTimer(messageElement, { completed = false, elapsedMs = null } = {}) {
  const timer = messageElement?.querySelector("[data-agent-thinking-timer]");
  if (!timer) {
    return 0;
  }
  const durationMs = elapsedMs ?? agentThinkingElapsedMs(messageElement);
  timer.textContent = completed
    ? `已处理${formatAgentThinkingDuration(durationMs)}`
    : `思考${formatAgentThinkingDuration(durationMs)}`;
  timer.classList.toggle("agent-thinking-timer--done", completed);
  return durationMs;
}

function startAgentThinkingTimer(messageElement) {
  if (!messageElement) {
    return;
  }
  messageElement.dataset.agentThinkingStartedAt = String(Date.now());
  updateAgentThinkingTimer(messageElement);
  messageElement._agentThinkingTimerId = window.setInterval(
    () => updateAgentThinkingTimer(messageElement),
    AGENT_THINKING_TIMER_INTERVAL_MS,
  );
}

function stopAgentThinkingTimer(messageElement) {
  if (!messageElement) {
    return 0;
  }
  if (messageElement._agentThinkingTimerId) {
    window.clearInterval(messageElement._agentThinkingTimerId);
    messageElement._agentThinkingTimerId = null;
  }
  return updateAgentThinkingTimer(messageElement, { completed: true });
}

function liveAgentEventView(eventName, payload = {}) {
  const summary = userFacingAgentSummary(
    payload.step_summary || payload.observation_summary || payload.output_summary || "",
    payload,
  );
  if (eventName === "tool_call_start") {
    return {
      kind: "tool-call-start",
      title: "准备工具",
      summary: summary,
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
      title: "工具结果",
      summary: summary,
      meta: payload.tool_name || payload.action || "",
    };
  }
  return {
    kind: "agent-step",
    title: "Agent 步骤",
    summary: summary,
    meta: payload.action || payload.phase || "",
  };
}

function localizeAgentAction(action) {
  if (action === "search_progress") {
    return "检索进度";
  }
  if (action === "answer_progress") {
    return "回答进度";
  }
  const labels = {
    llm_with_tools: "分析问题并选择检索工具",
    search_knowledge: "检索知识库",
    hybrid_search_knowledge: "混合检索",
    search_figures: "检索示例图片",
    search_tables: "检索表格证据",
    analyze_user_image: "分析上传图片",
    rewrite_query: "改写查询",
    answer_with_citations: "生成带引用回答",
    retrieval_diagnostics: "检索诊断",
    refuse: "安全拒答",
    final_answer: "最终回答",
  };
  return labels[action] || action || "未知动作";
}

function localizeAgentTool(toolName) {
  const labels = {
    search_knowledge: "检索知识库",
    hybrid_search_knowledge: "混合检索",
    search_figures: "检索示例图片",
    search_tables: "检索表格证据",
    analyze_user_image: "分析上传图片",
    answer_with_citations: "引用式回答",
    retrieval_diagnostics: "检索诊断",
    rewrite_query: "改写查询",
    refuse: "安全拒答",
    final_answer: "最终回答",
  };
  return labels[toolName] || toolName || "未知工具";
}

function isSkippedAgentStep(step = {}) {
  const text = `${step.error || ""} ${step.output_summary || ""} ${step.observation_summary || ""}`.toLowerCase();
  return text.includes("skipped") || step.skipped === true;
}

function skippedToolSummary(toolName, reasonText = "") {
  const label = localizeAgentTool(toolName);
  const normalized = String(reasonText || "").toLowerCase();
  if (normalized.includes("near-duplicate")) {
    return `已跳过：${label}；原因：与已执行检索重复`;
  }
  if (normalized.includes("existing evidence available")) {
    return `已跳过：${label}；原因：已有可用证据`;
  }
  if (normalized.includes("per-iteration search tool budget reached")) {
    return `已跳过：${label}；原因：本轮只执行一个检索工具`;
  }
  return `已跳过：${label}`;
}

function userFacingAgentSummary(summary, context = {}) {
  const text = String(summary || "");
  const normalized = text.toLowerCase();
  if (!text) {
    return "";
  }
  if (normalized.includes("calling model with tool definitions") || normalized.includes("llm_with_tools")) {
    return "正在分析问题并选择检索工具";
  }
  if (normalized.includes("near-duplicate") || normalized.includes("existing evidence available")) {
    return skippedToolSummary(context.tool_name || context.name || context.action, text);
  }
  if (normalized.includes("per-iteration search tool budget reached")) {
    return skippedToolSummary(context.tool_name || context.name || context.action, text);
  }
  if (normalized.includes("model request failed") || normalized.includes("llm") || normalized.includes("provider")) {
    return "模型服务暂时不可用，已切换到错误处理";
  }
  return text;
}

function agentLiveStatusText(eventName, payload = {}) {
  const summary = userFacingAgentSummary(
    payload.step_summary || payload.observation_summary || payload.output_summary || "",
    payload,
  );
  if (summary) {
    return summary;
  }
  if (eventName === "tool_call_start") {
    return `正在调用：${localizeAgentTool(payload.tool_name || payload.action)}`;
  }
  if (eventName === "tool_call_result") {
    if (payload.skipped) {
      return skippedToolSummary(payload.tool_name || payload.action, payload.output_summary || payload.error || "");
    }
    return payload.succeeded === false
      ? `${localizeAgentTool(payload.tool_name || payload.action)}失败`
      : `${localizeAgentTool(payload.tool_name || payload.action)}完成`;
  }
  return `正在执行：${localizeAgentAction(payload.action)}`;
}

function appendAgentLiveStep(messageElement, eventName, payload = {}) {
  if (!messageElement) {
    return;
  }
  messageElement._agentThoughtEvents = messageElement._agentThoughtEvents || [];
  messageElement._agentThoughtEvents.push({ eventName, payload });
  setAgentThinkingStatusLabel(messageElement, agentLiveStatusText(eventName, payload));
  const list = messageElement.querySelector("[data-agent-live-steps]");
  if (!list) {
    return;
  }
  list.hidden = false;
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
  const action = localizeAgentAction(step.name || step.tool_name || step.action);
  const skipped = isSkippedAgentStep(step);
  const succeeded = step.succeeded !== false || skipped;
  const statusText = skipped ? "已跳过" : succeeded ? "已完成" : "已处理";
  const summary = userFacingAgentSummary(
    step.step_summary || step.observation_summary || step.output_summary || step.input_summary || "",
    step,
  );
  const summaryHtml = summary
    ? `<div class="agent-thought-line">${escapeHtml(summary)}</div>`
    : "";
  const error = step.error && !skipped
    ? `<div class="agent-thought-line agent-thought-line--error">提示：${escapeHtml(userFacingAgentSummary(step.error, step))}</div>`
    : "";
  return `
    <li class="agent-thought-step">
      <div class="agent-thought-step-title">
        <span>${index + 1}. ${escapeHtml(action)}</span>
        <span class="pill ${succeeded ? "neutral" : "warning"}">${escapeHtml(statusText)}</span>
      </div>
      ${summaryHtml}
      ${error}
    </li>
  `;
}

function retrievalTraceStepFromResult(result = {}) {
  const trace = result.latency_trace || {};
  const hasRetrievalTrace = Array.isArray(trace.retrieval_selected_chunk_ids)
    || Array.isArray(trace.retrieval_candidate_chunk_ids)
    || trace.semantic_cache_hit === true;
  if (!hasRetrievalTrace) {
    return null;
  }
  const parts = [];
  if (trace.semantic_cache_hit === true) {
    parts.push(`semantic_cache_hit=true`);
    if (trace.semantic_cache_similarity !== undefined && trace.semantic_cache_similarity !== null) {
      parts.push(`similarity=${trace.semantic_cache_similarity}`);
    }
  }
  if (trace.retrieval_query) {
    parts.push(`query=${trace.retrieval_query}`);
  }
  const cacheParts = [];
  if (trace.retrieval_cache_hit !== undefined) {
    cacheParts.push(`retrieval_cache_hit=${trace.retrieval_cache_hit}`);
  }
  if (trace.rerank_cache_hit !== undefined) {
    cacheParts.push(`rerank_cache_hit=${trace.rerank_cache_hit}`);
  }
  if (trace.tool_result_cache_hit !== undefined) {
    cacheParts.push(`tool_result_cache_hit=${trace.tool_result_cache_hit}`);
  }
  if (cacheParts.length) {
    parts.push(cacheParts.join(","));
  }
  if (trace.reranking_fallback !== undefined) {
    parts.push(`rerank_fallback=${trace.reranking_fallback}`);
  }
  if (trace.reranking_fallback_used !== undefined) {
    parts.push(`rerank_fallback_used=${trace.reranking_fallback_used}`);
  }
  if (trace.reranking_provider || trace.reranking_model) {
    parts.push(`reranker=${[trace.reranking_provider, trace.reranking_model].filter(Boolean).join("/")}`);
  }
  if (trace.retrieval_candidate_count !== undefined) {
    parts.push(`candidate_count=${trace.retrieval_candidate_count}`);
  }
  if (Array.isArray(trace.retrieval_candidate_chunk_ids)) {
    parts.push(`candidate_chunk_ids=${trace.retrieval_candidate_chunk_ids.slice(0, 20).join(",")}`);
  }
  if (trace.retrieval_selected_count !== undefined) {
    parts.push(`selected_count=${trace.retrieval_selected_count}`);
  }
  if (trace.retrieval_dynamic_top_k_enabled !== undefined) {
    parts.push(`dynamic_top_k=${trace.retrieval_dynamic_top_k_enabled}`);
  }
  if (trace.retrieval_selection_reason) {
    parts.push(`selection_reason=${trace.retrieval_selection_reason}`);
  }
  if (Array.isArray(trace.retrieval_selected_chunk_ids)) {
    parts.push(`selected_chunk_ids=${trace.retrieval_selected_chunk_ids.slice(0, 12).join(",")}`);
  }
  if (Array.isArray(trace.retrieval_selected_preview)) {
    const selectedSources = trace.retrieval_selected_preview
      .slice(0, 8)
      .map((item) => {
        if (!item || typeof item !== "object") {
          return "";
        }
        const chunkId = item.chunk_id ?? "";
        const sourceType = item.source_type || "";
        const title = String(item.title || "").slice(0, 48);
        return `${chunkId}:${sourceType}:${title}`;
      })
      .filter(Boolean);
    if (selectedSources.length) {
      parts.push(`selected_sources=${selectedSources.join(" | ")}`);
    }
  }
  return {
    action: "retrieval_diagnostics",
    name: "retrieval_diagnostics",
    input_summary: "",
    output_summary: parts.join("; "),
    succeeded: true,
  };
}

function agentThoughtHtml(result = {}) {
  const liveThoughtSteps = result._live_thought_steps || [];
  const workflowSteps = result.workflow_steps || [];
  const toolCalls = result.tool_calls || [];
  let baseSteps = workflowSteps.length
    ? workflowSteps
    : toolCalls.map((call) => ({
        action: call.tool_name,
        name: call.tool_name,
        input_summary: call.input_summary,
        output_summary: call.output_summary,
        succeeded: call.succeeded,
        error: call.error,
      }));
  const retrievalTraceStep = retrievalTraceStepFromResult(result);
  if (retrievalTraceStep) {
    baseSteps = [...baseSteps, retrievalTraceStep];
  }
  const steps = liveThoughtSteps.length ? liveThoughtSteps : baseSteps;
  if (!steps.length) {
    return "";
  }
  const durationMs = Number(
    result._client_elapsed_ms
      ?? result.latency_trace?.time_to_final_ms
      ?? result.latency_trace?.total_latency_ms
      ?? result.latency_trace?.answer_latency_ms
      ?? 0,
  );
  const durationLabel = durationMs > 0 ? `已处理${formatAgentThinkingDuration(durationMs)}` : "";
  return `
    <details class="agent-thought-panel">
      <summary><span>查看思考过程</span>${durationLabel ? `<span class="agent-thinking-timer agent-thinking-timer--done">${escapeHtml(durationLabel)}</span>` : ""}</summary>
      <ol class="agent-thought-list">
        ${steps.map((step, index) => agentThoughtStepHtml(step, index)).join("")}
      </ol>
    </details>
  `;
}

function liveThoughtStepsFromEvents(events = []) {
  return events.map(({ eventName, payload }, index) => {
    const action = payload.action || payload.tool_name || `live_step_${index + 1}`;
    return {
      action,
      name: action,
      tool_name: payload.tool_name || "",
      step_summary: payload.step_summary || payload.observation_summary || payload.output_summary || "",
      input_summary: payload.input_summary || "",
      output_summary: payload.output_summary || "",
      observation_summary: payload.observation_summary || "",
      succeeded: eventName === "tool_call_result" ? payload.succeeded !== false : true,
      skipped: payload.skipped === true,
      error: payload.error || "",
    };
  });
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
    setAgentThinkingStatusLabel(messageElement, "正在接收回答...", { showSpinner: true });
  }
  messageElement._streamedAnswerText = `${messageElement._streamedAnswerText || ""}${token}`;
  answerText.innerHTML = renderMarkdownBlocks(messageElement._streamedAnswerText);
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
  stopAgentThinkingTimer(messageElement);
  const answerText = messageElement.querySelector(".answer-text");
  if (answerText) {
    const wasThinkingText = answerText.classList.contains("thinking-text");
    answerText.classList.remove("thinking-text");
    if (wasThinkingText || !answerText.textContent.trim()) {
      answerText.textContent = "";
    }
  }
  setAgentThinkingStatusLabel(messageElement, "Generation stopped");
  const liveSteps = messageElement.querySelector("[data-agent-live-steps]");
  if (liveSteps && !liveSteps.children.length) {
    liveSteps.remove();
  }
  const bubble = messageElement.querySelector(".chat-message-bubble");
  if (bubble && !bubble.querySelector("[data-agent-abort-status]")) {
    bubble.insertAdjacentHTML(
      "beforeend",
      sanitizeRenderedHtml('<p class="agent-stream-status" data-agent-abort-status>Generation stopped.</p>'),
    );
  }
  scrollAgentChatToBottom();
}

function finalizeAgentStreamingMessage(messageElement, result) {
  const clientElapsedMs = stopAgentThinkingTimer(messageElement);
  result = normalizeCitationDisplay(result);
  if (clientElapsedMs > 0) {
    result = { ...result, _client_elapsed_ms: clientElapsedMs };
  }
  const liveThoughtSteps = liveThoughtStepsFromEvents(messageElement?._agentThoughtEvents || []);
  if (liveThoughtSteps.length) {
    result = { ...result, _live_thought_steps: liveThoughtSteps };
  }
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
  const streamedAnswer = String(messageElement._streamedAnswerText || answerText.textContent || "").trim();
  if (!answerText || !streamedAnswer) {
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
  const citationSetId = renderSegmentedAnswerInto(answerText, result);

  if (result.refused) {
    const refusalCategory = result.refusal_category
      ? `<p class="refusal-category">Category: ${escapeHtml(formatRefusalCategory(result.refusal_category))} / ${escapeHtml(result.refusal_category)}</p>`
      : "";
    answerText.insertAdjacentHTML(
      "beforebegin",
      `<div class="refusal"><strong>Refused</strong>${refusalCategory}<p>${escapeHtml(result.refusal_reason || "Insufficient evidence")}</p></div>`,
    );
  }

  const orphanInvalidBadges = (result.invalid_citations || [])
    .filter((c) => !(result.citations || []).map((i) => String(i)).includes(String(c)))
    .map((c) => `<span class="pill danger">[${escapeHtml(c)}] missing</span>`)
    .join("");
  answerText.insertAdjacentHTML(
    "afterend",
    `
    ${imageAnalysisHtml(result)}
    ${figureEvidenceHtml(result)}
    ${tableEvidenceHtml(result)}
    <div class="answer-meta">
      ${sourceClusterHtml(result, citationSetId)}
      ${orphanInvalidBadges}
      ${feedbackControlsHtml(result)}
    </div>
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
            <strong>Request failed</strong>
            <p>${escapeHtml(message || "Request failed. Please retry later or check service logs.")}</p>
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

function agentAnswerHtml(result) {
  result = normalizeCitationDisplay(result);
  const citationSetId = registerCitationSet(result);
  const orphanInvalidBadges = (result.invalid_citations || [])
    .filter((citation) => !(result.citations || []).map((item) => String(item)).includes(String(citation)))
    .map((citation) => `<span class="pill danger">[${escapeHtml(citation)}] invalid</span>`)
    .join("");
  const refusalCategory = result.refusal_category
    ? `<p class="refusal-category">Category: ${escapeHtml(formatRefusalCategory(result.refusal_category))} / ${escapeHtml(result.refusal_category)}</p>`
    : "";
  const refused = result.refused
    ? `<div class="refusal"><strong>Refused</strong>${refusalCategory}<p>${escapeHtml(result.refusal_reason || "Insufficient evidence")}</p></div>`
    : "";
  return sanitizeRenderedHtml(`
    ${agentThoughtHtml(result)}
    ${refused}
    <div class="answer-text answer-text--segmented" data-citation-set="${escapeHtml(citationSetId)}">${renderAnswerSegmentsHtml(result, citationSetId)}</div>
    ${imageAnalysisHtml(result)}
    ${figureEvidenceHtml(result)}
    ${tableEvidenceHtml(result)}
    <div class="answer-meta">
      ${sourceClusterHtml(result, citationSetId)}
      ${orphanInvalidBadges}
      ${feedbackControlsHtml(result)}
    </div>
  `);
}

function renderAgentAnswer(result) {
  const status = document.querySelector("[data-agent-status]");
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
  const list = document.querySelector("[data-conversation-list]");
  const titleInput = document.querySelector("[data-conversation-title]");
  if (!list) {
    return;
  }
  if (!state.conversations.length) {
    list.innerHTML = '<div class="empty-state">No conversations</div>';
    if (titleInput) {
      titleInput.value = "";
    }
    return;
  }
  list.innerHTML = state.conversations
    .map((conversation) => {
      const selected = String(conversation.id) === String(state.currentConversationId);
      return `
        <button
          class="conversation-list-item${selected ? " is-active" : ""}"
          type="button"
          data-conversation-item="${escapeHtml(conversation.id)}"
          role="option"
          aria-selected="${selected ? "true" : "false"}"
        >
          <span>${escapeHtml(conversation.title)}</span>
        </button>
      `;
    })
    .join("");
  if (titleInput) {
    const current = state.conversations.find(
      (conversation) => String(conversation.id) === String(state.currentConversationId),
    );
    titleInput.value = current?.title || "";
  }
}

function setConversationListPlaceholder(message) {
  const list = document.querySelector("[data-conversation-list]");
  if (list) {
    list.innerHTML = `<div class="empty-state">${escapeHtml(message)}</div>`;
  }
}

function hideConversationMenu() {
  const menu = document.querySelector("[data-conversation-menu]");
  if (!menu) {
    return;
  }
  menu.hidden = true;
  state.contextMenuConversationId = null;
}

function showConversationMenu(conversationId, clientX, clientY) {
  const menu = document.querySelector("[data-conversation-menu]");
  if (!menu) {
    return;
  }
  state.contextMenuConversationId = conversationId;
  menu.hidden = false;
  const offset = 6;
  const maxLeft = Math.max(8, window.innerWidth - menu.offsetWidth - 8);
  const maxTop = Math.max(8, window.innerHeight - menu.offsetHeight - 8);
  menu.style.left = `${Math.min(clientX + offset, maxLeft)}px`;
  menu.style.top = `${Math.min(clientY + offset, maxTop)}px`;
}

function targetConversationId() {
  return state.contextMenuConversationId || state.currentConversationId;
}

async function refreshConversationList() {
  if (!ensureAuthenticated()) {
    return;
  }
  try {
    const payload = await fetchJson(apiEndpoints.conversations);
    state.conversations = payload.conversations || [];
    renderConversationList();
  } catch (error) {
    state.conversations = [];
    state.currentConversationId = null;
    setConversationListPlaceholder("Failed to load conversations");
    throw error;
  }
}

async function createAgentConversation(title = "New conversation") {
  if (!ensureAuthenticated()) {
    throw new Error("authentication required");
  }
  const conversation = await fetchJson(apiEndpoints.conversations, {
    method: "POST",
    body: JSON.stringify({ title }),
  });
  state.currentConversationId = conversation.id;
  await refreshConversationList();
  clearAgentChat();
  return conversation;
}

function startDraftConversation() {
  state.currentConversationId = null;
  state.contextMenuConversationId = null;
  hideConversationMenu();
  clearAgentChat();
  renderConversationList();
  setAgentPanelStatus("draft");
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
}

async function loadAgentConversations() {
  if (!ensureAuthenticated()) {
    return;
  }
  await refreshConversationList();
  if (state.conversations.length) {
    await loadConversationMessages(state.conversations[0].id);
  } else {
    startDraftConversation();
  }
}

async function deleteCurrentConversation() {
  if (!ensureAuthenticated()) {
    return;
  }
  const conversationId = targetConversationId();
  if (!conversationId) {
    return;
  }
  hideConversationMenu();
  await fetchJson(apiEndpoints.conversation(conversationId), {
    method: "DELETE",
  });
  if (String(state.currentConversationId) === String(conversationId)) {
    state.currentConversationId = null;
  }
  await refreshConversationList();
  if (state.conversations.length) {
    await loadConversationMessages(state.conversations[0].id);
  } else {
    startDraftConversation();
  }
}

async function renameCurrentConversation() {
  if (!ensureAuthenticated()) {
    return;
  }
  const conversationId = targetConversationId();
  if (!conversationId) {
    return;
  }
  const current = state.conversations.find((conversationItem) => String(conversationItem.id) === String(conversationId));
  const title = window.prompt("重命名会话", current?.title || "New conversation");
  hideConversationMenu();
  if (title === null) {
    return;
  }
  const conversation = await fetchJson(apiEndpoints.conversation(conversationId), {
    method: "PATCH",
    body: JSON.stringify({ title: title.trim() || "New conversation" }),
  });
  state.currentConversationId = conversation.id;
  await refreshConversationList();
  setAgentPanelStatus("conversation_renamed");
}

async function submitChat() {
  const question = document.querySelector("[data-chat-question]")?.value.trim();
  const topK = Number(document.querySelector("[data-chat-top-k]")?.value || 5);
  const retrievalMode = document.querySelector("[data-chat-retrieval-mode]")?.value || "auto";
  const minScore = Number(document.querySelector("[data-chat-min-score]")?.value || 0);
  if (!question) {
    setApiStatus("Please enter a question");
    return;
  }
  setApiStatus("Answering...");
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
  setApiStatus(result.refused ? "Refused" : "Answered");
}

function setUploadStatus(text, hidden = false) {
  const status = document.querySelector("[data-agent-upload-status]");
  if (!status) {
    return;
  }
  status.textContent = text || "";
  status.hidden = hidden || !text;
}

function clearPendingAgentImage() {
  state.pendingUploadedImage = null;
  const input = document.querySelector("[data-agent-image-input]");
  if (input) {
    input.value = "";
  }
  setUploadStatus("", true);
}

function selectedAgentImageFile() {
  return state.pendingUploadedImage?.file || document.querySelector("[data-agent-image-input]")?.files?.[0] || null;
}

function setPendingAgentImage(file) {
  if (!file) {
    clearPendingAgentImage();
    return;
  }
  if (!String(file.type || "").startsWith("image/")) {
    setApiStatus("请拖入或选择图片文件");
    return;
  }
  state.pendingUploadedImage = { file };
  setUploadStatus(`已添加图片：${file.name || "未命名图片"}`);
}

async function uploadSelectedAgentImage() {
  const input = document.querySelector("[data-agent-image-input]");
  if (state.pendingUploadedImage?.path && !state.pendingUploadedImage.file) {
    return state.pendingUploadedImage;
  }
  const file = selectedAgentImageFile();
  if (!file) {
    return null;
  }
  setUploadStatus("正在上传图片...");
  const formData = new FormData();
  formData.append("file", file);
  const uploaded = await fetchMultipartJson(apiEndpoints.imageUpload, formData);
  state.pendingUploadedImage = uploaded;
  setUploadStatus(`已上传：${uploaded.filename || "图片"}`);
  if (input) {
    input.value = "";
  }
  return uploaded;
}

async function submitAgent() {
  if (state.agentRequestInFlight) {
    abortAgentStream();
    return;
  }
  if (!ensureAuthenticated()) {
    appendAgentErrorMessage(authRequiredMessage());
    return;
  }
  const questionInput = document.querySelector("[data-agent-question]");
  const question = questionInput?.value.trim();
  if (!question) {
    setApiStatus("Please enter an Agent task");
    return;
  }
  let pendingUserMessage = null;
  let pendingThinkingMessage = null;
  setAgentBusy(true);
  try {
    setApiStatus("Agent running...");
    setAgentPanelStatus("running");
    let imageWasSubmitted = false;
    const body = {
      question,
      top_k: 8,
      max_tool_calls: 5,
      mode: "tool_calling_agent",
    };
    const uploadedImage = await uploadSelectedAgentImage();
    if (uploadedImage?.path) {
      body.image_path = uploadedImage.path;
      body.mode = "react_agent";
      body.max_tool_calls = 5;
      imageWasSubmitted = true;
    }
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
          headers: authHeaders(),
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
    setApiStatus(result?.aborted ? "Agent stopped" : result?.refused ? "Agent refused" : "Agent completed");
    setAgentPanelStatus(result?.aborted ? "aborted" : result?.refused ? "refused" : "answered");
    if (imageWasSubmitted && !result?.aborted) {
      clearPendingAgentImage();
    }
    await refreshConversationList();
  } catch (error) {
    pendingThinkingMessage?.remove();
    setAgentPanelStatus("error");
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
        ...authHeaders(),
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
    const error = new Error(Array.isArray(detail) ? detail.map((item) => item.msg).join("; ") : detail);
    error.status = response.status;
    error.url = apiEndpoints.agentStream;
    throw error;
  }
  if (!response.body || !response.body.getReader) {
    throw new Error("This browser does not support streaming reads; switched to synchronous request.");
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
    throw new Error("Stream ended without metadata.");
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
      throw new Error(event.data.detail || "Stream returned an error event.");
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
  setApiStatus("Loading...");
  const [sourcesPayload, documentsPayload] = await Promise.all([
    fetchJson(apiEndpoints.sources),
    fetchJson(apiEndpoints.documents),
  ]);
  state.sources = sourcesPayload.sources || [];
  state.documents = documentsPayload.documents || [];
  renderAll();
  setApiStatus("Loaded");
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
  document.querySelector("[data-auth-login-form]")?.addEventListener("submit", (event) => {
    event.preventDefault();
    submitAuthLogin().catch((error) => {
      setApiStatus(`登录失败：${error.message}`);
    });
  });
  document.querySelector("[data-auth-register-form]")?.addEventListener("submit", (event) => {
    event.preventDefault();
    submitAuthRegister().catch((error) => {
      setApiStatus(`注册失败：${error.message}`);
    });
  });
  document.querySelectorAll("[data-auth-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      setAuthMode(button.dataset.authMode);
    });
  });
  document.querySelector("[data-auth-logout]")?.addEventListener("click", () => {
    clearAuthSession();
    setAuthMode("login");
    setApiStatus("已退出登录");
  });
  document.querySelector("[data-refresh-all]")?.addEventListener("click", () => {
    loadWorkspaceData().catch((error) => {
      setApiStatus(`Load failed: ${error.message}`);
    });
  });
  document.querySelector("[data-chat-form]")?.addEventListener("submit", (event) => {
    event.preventDefault();
    submitChat().catch((error) => {
      setApiStatus(`Question failed: ${error.message}`);
    });
  });
  document.querySelector("[data-search-form]")?.addEventListener("submit", (event) => {
    event.preventDefault();
    submitSearch().catch((error) => {
      setApiStatus(`Search failed: ${error.message}`);
    });
  });
  document.querySelector("[data-agent-form]")?.addEventListener("submit", (event) => {
    event.preventDefault();
    submitAgent().catch((error) => {
      setApiStatus(`Agent failed: ${error.message}`);
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
    startDraftConversation();
  });
  document.querySelector("[data-refresh-conversations]")?.addEventListener("click", () => {
    loadAgentConversations().catch((error) => {
      setApiStatus(`Refresh conversations failed: ${error.message}`);
    });
  });
  document.querySelector("[data-delete-conversation]")?.addEventListener("click", () => {
    deleteCurrentConversation().catch((error) => {
      setApiStatus(`Delete conversation failed: ${error.message}`);
    });
  });
  document.querySelector("[data-rename-conversation]")?.addEventListener("click", () => {
    renameCurrentConversation().catch((error) => {
      setApiStatus(`Rename failed: ${error.message}`);
    });
  });
  document.querySelector("[data-close-citation-drawer]")?.addEventListener("click", () => {
    closeCitationDrawer();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeFigureLightbox();
    }
  });
  bindEnterToSubmit();
  document.querySelector("[data-conversation-list]")?.addEventListener("click", (event) => {
    const conversationButton = event.target.closest("[data-conversation-item]");
    if (!conversationButton) {
      return;
    }
    hideConversationMenu();
    loadConversationMessages(conversationButton.dataset.conversationItem).catch((error) => {
      setApiStatus(`Switch conversation failed: ${error.message}`);
    });
  });
  document.querySelector("[data-conversation-list]")?.addEventListener("contextmenu", (event) => {
    const conversationButton = event.target.closest("[data-conversation-item]");
    if (!conversationButton) {
      return;
    }
    event.preventDefault();
    showConversationMenu(conversationButton.dataset.conversationItem, event.clientX, event.clientY);
  });
  document.querySelector("[data-sync-sources]")?.addEventListener("click", () => {
    syncSources().catch((error) => {
      setApiStatus(`Sync failed: ${error.message}`);
    });
  });
  document.addEventListener("click", (event) => {
    const menu = document.querySelector("[data-conversation-menu]");
    if (menu && !menu.hidden && !event.target.closest("[data-conversation-menu]")) {
      hideConversationMenu();
    }
    const figureTrigger = event.target.closest("[data-figure-open]");
    if (figureTrigger) {
      event.preventDefault();
      openFigureLightbox({
        src: figureTrigger.dataset.figureSrc || "",
        title: figureTrigger.dataset.figureTitle || "",
        meta: figureTrigger.dataset.figureMeta || "",
        rotation: Number(figureTrigger.dataset.figureRotation || 0),
      });
      return;
    }
    if (event.target.closest("[data-rotate-figure-lightbox]")) {
      event.preventDefault();
      rotateFigureLightbox();
      return;
    }
    if (event.target.closest("[data-close-figure-lightbox]")) {
      event.preventDefault();
      closeFigureLightbox();
      return;
    }
    const sourceTrigger = event.target.closest("[data-source-cluster], [data-citation-ref]");
    if (sourceTrigger) {
      const citationSetId = sourceTrigger.dataset.citationSet;
      if (citationSetId) {
        openCitationDrawer(citationSetId, sourceTrigger.dataset.citationRef || "");
      }
      return;
    }
    const feedbackButton = event.target.closest("[data-feedback-rating]");
    if (feedbackButton) {
      const wrapper = feedbackButton.closest("[data-feedback-payload]");
      const encodedPayload = wrapper?.dataset.feedbackPayload || "";
      try {
        const payload = JSON.parse(decodeURIComponent(encodedPayload));
        submitFeedback(payload, feedbackButton.dataset.feedbackRating).catch((error) => {
          setApiStatus(`Feedback failed: ${error.message}`);
        });
        wrapper?.querySelectorAll("[data-feedback-rating]").forEach((button) => {
          button.disabled = true;
        });
        feedbackButton.classList.add("is-selected");
      } catch (error) {
        setApiStatus("Feedback payload is invalid");
      }
      return;
    }
    const chunkButton = event.target.closest("[data-view-chunks]");
    if (chunkButton) {
      viewDocumentChunks(chunkButton.dataset.viewChunks).catch((error) => {
        setApiStatus(`Load chunks failed: ${error.message}`);
      });
      return;
    }
    const reindexButton = event.target.closest("[data-reindex-source]");
    if (reindexButton) {
      reindexSource(reindexButton.dataset.reindexSource).catch((error) => {
        setApiStatus(`Reindex failed: ${error.message}`);
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

function setAppMode(isAppMode) {
  document.querySelector("[data-app-shell]")?.classList.toggle("is-app-mode", isAppMode);
}

function enterApp(viewName, hashValue) {
  setAppMode(true);
  switchView(viewName);
  window.history.replaceState(null, "", hashValue || (viewName === "library" ? "#library-view" : "#ask-view"));
  window.requestAnimationFrame(() => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
}

function showLanding() {
  switchView("ask");
  setAppMode(false);
  window.history.replaceState(null, "", window.location.pathname || "/");
  window.requestAnimationFrame(() => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
}

function bindViewNavigation() {
  document.querySelectorAll("[data-view-target]").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      enterApp(link.dataset.viewTarget, link.getAttribute("href") || "#ask-view");
    });
  });
  document.querySelector("[data-home-link]")?.addEventListener("click", (event) => {
    event.preventDefault();
    showLanding();
  });
  if (window.location.hash === "#library-view" || window.location.hash === "#library-panel") {
    enterApp("library", "#library-view");
  } else if (window.location.hash === "#ask-view" || window.location.hash === "#agent-panel") {
    enterApp("ask", "#ask-view");
  } else {
    switchView("ask");
    setAppMode(false);
  }
}

function bindAgentImageInput() {
  const imageInput = document.querySelector("[data-agent-image-input]");
  const imageButton = document.querySelector("[data-agent-image-button]");
  const dropTargets = [
    document.querySelector("[data-agent-form]"),
    document.querySelector("[data-agent-question]"),
    document.querySelector("[data-agent-chat-list]"),
  ].filter(Boolean);

  imageButton?.addEventListener("click", () => {
    imageInput?.click();
  });
  imageInput?.addEventListener("change", () => {
    setPendingAgentImage(imageInput.files?.[0] || null);
  });

  for (const target of dropTargets) {
    target.addEventListener("dragover", (event) => {
      if (!Array.from(event.dataTransfer?.items || []).some((item) => item.type.startsWith("image/"))) {
        return;
      }
      event.preventDefault();
      target.classList.add("is-image-drop-target");
      setUploadStatus("松开即可添加图片");
    });
    target.addEventListener("dragleave", () => {
      target.classList.remove("is-image-drop-target");
      if (!selectedAgentImageFile()) {
        setUploadStatus("", true);
      }
    });
    target.addEventListener("drop", (event) => {
      const file = Array.from(event.dataTransfer?.files || []).find((item) => item.type.startsWith("image/"));
      if (!file) {
        return;
      }
      event.preventDefault();
      target.classList.remove("is-image-drop-target");
      setPendingAgentImage(file);
    });
  }
}

async function initializeShell() {
  bindViewNavigation();
  bindSourceFilters();
  bindCommands();
  bindAgentImageInput();
  setAuthMode("login");
  renderAuthState();
  try {
    await fetchJson("/health");
    await loadCurrentUserFromToken();
    await loadWorkspaceData();
    if (state.authToken) {
      if (!window.location.hash || window.location.hash === "#home") {
        enterApp("ask", "#ask-view");
      }
      await loadAgentConversations();
    } else {
      setConversationListPlaceholder("登录后加载会话");
    }
  } catch (error) {
    setApiStatus(`Connection error: ${error.message}`);
  }
}

window.rfcRagFrontend = {
  apiEndpoints,
  abortAgentStream,
  authHeaders,
  fetchJson,
  submitAuthLogin,
  submitAuthRegister,
  isAgentAbortError,
  markAgentStreamingAborted,
  sanitizeRenderedHtml,
  setApiStatus,
};

initializeShell();
