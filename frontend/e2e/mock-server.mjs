import http from 'node:http'
import { readFile, stat } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const directory = path.dirname(fileURLToPath(import.meta.url))
const distRoot = path.resolve(directory, '../dist')
const port = 4173

let nextConversationId = 1
let nextMessageId = 1
let createCount = 0
let streamCount = 0
let conversations = []
let messagesByConversation = new Map()

function resetState() {
  nextConversationId = 1
  nextMessageId = 1
  createCount = 0
  streamCount = 0
  conversations = []
  messagesByConversation = new Map()
}

function json(response, status, payload) {
  response.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8' })
  response.end(JSON.stringify(payload))
}

async function requestBody(request) {
  const chunks = []
  for await (const chunk of request) chunks.push(chunk)
  if (!chunks.length) return {}
  return JSON.parse(Buffer.concat(chunks).toString('utf8'))
}

function user() {
  return { id: 42, username: 'mock-user', email: 'mock@example.test', is_active: true, created_at: '2026-01-01T00:00:00Z' }
}

function resultFor(question) {
  const withoutSources = question.includes('no sources')
  const ordinal = question.includes('second') ? 'second answer' : question.includes('judge failure') ? 'judge failure answer' : 'first answer'
  const sources = withoutSources ? [] : [{
    source_id: `${ordinal}-source`,
    title: `${ordinal} source`,
    source_type: 'mock_document',
    document_id: 1,
    chunk_id: ordinal === 'second answer' ? 202 : 101,
    chunk_index: 0,
    content: 'Short sanitized browser-test evidence.',
    score: 0.93,
  }]
  return {
    question,
    answer: withoutSources ? `${ordinal} has no returned sources.` : `${ordinal} cites browser-test evidence [1].`,
    sources,
    citations: withoutSources ? [] : [1],
    refused: false,
    refusal_reason: null,
    mode: 'tool_calling_agent',
    workflow_steps: [
      { name: 'search_knowledge', input_summary: 'Search mock corpus', output_summary: `Returned ${sources.length} real mock sources`, succeeded: true },
      { name: 'final_answer', step_summary: 'Compose final answer from returned sources', succeeded: true },
    ],
    tool_calls: [{ name: 'search_knowledge', tool_name: 'search_knowledge', succeeded: true }],
    latency_trace: { time_to_final_ms: 180, retrieval_selected_chunk_ids: sources.length ? [sources[0].chunk_id] : [] },
    chat_provider: 'mock',
    chat_model: 'mock-model',
  }
}

function persistExchange(conversationId, question, result) {
  const records = messagesByConversation.get(conversationId) || []
  records.push({ id: nextMessageId++, conversation_id: conversationId, role: 'user', content: question, created_at: new Date().toISOString() })
  records.push({
    id: nextMessageId++, conversation_id: conversationId, role: 'assistant', content: result.answer,
    mode: result.mode, metadata: result, created_at: new Date().toISOString(),
  })
  messagesByConversation.set(conversationId, records)
}

const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds))

async function streamAgent(request, response, payload) {
  const result = resultFor(String(payload.question || ''))
  response.writeHead(200, {
    'Content-Type': 'text/event-stream; charset=utf-8',
    'Cache-Control': 'no-cache',
    Connection: 'keep-alive',
  })
  const send = async (event, data, wait = 25) => {
    await delay(wait)
    if (!response.destroyed) response.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`)
  }
  await send('heartbeat', { at: Date.now() }, 20)
  await send('agent_step', { action: 'llm_with_tools', step_summary: 'Real backend planning event' })
  await send('tool_call_start', { tool_name: 'search_knowledge', input_summary: 'Search mock corpus' })
  await send('tool_call_result', { tool_name: 'search_knowledge', output_summary: `Returned ${result.sources.length} real mock sources`, succeeded: true })
  const midpoint = Math.max(1, Math.floor(result.answer.length / 2))
  await send('token', { text: result.answer.slice(0, midpoint) })
  await send('token', { text: result.answer.slice(midpoint) })
  await send('metadata', result)
  await send('done', {})
  if (!response.destroyed) response.end()
  persistExchange(Number(payload.conversation_id), payload.question, result)
  const conversation = conversations.find((item) => item.id === Number(payload.conversation_id))
  if (conversation) conversation.updated_at = new Date().toISOString()
  request.resume()
}

async function serveDist(response, relativePath) {
  const resolved = path.resolve(distRoot, relativePath)
  if (!resolved.startsWith(`${distRoot}${path.sep}`) && resolved !== distRoot) return false
  try {
    const info = await stat(resolved)
    if (!info.isFile()) return false
    const extension = path.extname(resolved)
    const contentTypes = {
      '.html': 'text/html; charset=utf-8',
      '.js': 'text/javascript; charset=utf-8',
      '.css': 'text/css; charset=utf-8',
      '.svg': 'image/svg+xml',
      '.png': 'image/png',
    }
    response.writeHead(200, { 'Content-Type': contentTypes[extension] || 'application/octet-stream' })
    response.end(await readFile(resolved))
    return true
  } catch {
    return false
  }
}

const server = http.createServer(async (request, response) => {
  const url = new URL(request.url || '/', `http://${request.headers.host}`)
  const pathname = decodeURIComponent(url.pathname)

  if (pathname === '/__test/health') return json(response, 200, { ok: true })
  if (pathname === '/__test/reset' && request.method === 'POST') {
    resetState()
    return json(response, 200, { ok: true })
  }
  if (pathname === '/__test/state') return json(response, 200, { createCount, streamCount, conversationCount: conversations.length })
  if (pathname === '/favicon.ico') { response.writeHead(204); return response.end() }

  if (pathname === '/auth/login' && request.method === 'POST') {
    return json(response, 200, { access_token: 'fake-e2e-token', token_type: 'bearer', expires_in: 3600, user: user() })
  }
  if (pathname === '/auth/me') return json(response, 200, user())
  if (pathname === '/auth/logout' && request.method === 'POST') return json(response, 200, { status: 'ok' })
  if (pathname === '/auth/register' && request.method === 'POST') return json(response, 200, user())

  if (pathname === '/conversations' && request.method === 'GET') {
    await delay(120)
    return json(response, 200, conversations.map((conversation) => ({ ...conversation })))
  }
  if (pathname === '/conversations' && request.method === 'POST') {
    const payload = await requestBody(request)
    await delay(80)
    if (String(payload.title || '').includes('create failure')) return json(response, 503, { detail: 'Mock conversation create failure' })
    const conversation = { id: nextConversationId++, title: payload.title || 'New chat', created_at: new Date().toISOString() }
    conversations.unshift(conversation)
    messagesByConversation.set(conversation.id, [])
    createCount += 1
    return json(response, 200, conversation)
  }
  const messageMatch = pathname.match(/^\/conversations\/(\d+)\/messages$/)
  if (messageMatch && request.method === 'GET') {
    const conversationId = Number(messageMatch[1])
    const conversation = conversations.find((item) => item.id === conversationId)
    return conversation
      ? json(response, 200, { conversation, messages: messagesByConversation.get(conversationId) || [] })
      : json(response, 404, { detail: 'Conversation not found' })
  }
  const conversationMatch = pathname.match(/^\/conversations\/(\d+)$/)
  if (conversationMatch && request.method === 'PATCH') {
    const payload = await requestBody(request)
    const conversation = conversations.find((item) => item.id === Number(conversationMatch[1]))
    if (!conversation) return json(response, 404, { detail: 'Conversation not found' })
    conversation.title = payload.title
    return json(response, 200, conversation)
  }
  if (conversationMatch && request.method === 'DELETE') {
    const id = Number(conversationMatch[1])
    conversations = conversations.filter((item) => item.id !== id)
    messagesByConversation.delete(id)
    return json(response, 200, { conversation_id: id, deleted: true })
  }

  if (pathname === '/agent/query/stream' && request.method === 'POST') {
    streamCount += 1
    const payload = await requestBody(request)
    return streamAgent(request, response, payload)
  }
  if (pathname === '/agent/query' && request.method === 'POST') {
    const payload = await requestBody(request)
    return json(response, 200, resultFor(String(payload.question || '')))
  }
  if (pathname === '/agent/judge' && request.method === 'POST') {
    const payload = await requestBody(request)
    if (String(payload.question || '').includes('judge failure')) return json(response, 503, { detail: 'Mock Judge unavailable' })
    return json(response, 200, {
      judge_scores: { faithfulness: 0.91, citation_support: 0.88, answer_coverage: 0.86, safety_leak_check: 1 },
      judge_reasons: { faithfulness: 'Mock evidence supports answer', citation_support: 'Citation mapping is valid', answer_coverage: 'Covers test question', safety_leak_check: 'No leak found' },
      judge_provider: 'mock', judge_model: 'mock-judge', judge_status: 'completed',
    })
  }

  if (pathname === '/documents' && request.method === 'GET') return json(response, 200, [{
    id: 1, document_id: 1, title: 'Mock RFC document', source_type: 'local_file', file_name: 'mock-rfc.pdf',
    open_url: '/documents/1/open', status: 'imported', chunk_count: 12,
  }])
  if (pathname === '/documents/1/open') {
    response.writeHead(200, { 'Content-Type': 'text/plain; charset=utf-8' })
    return response.end('Mock document')
  }

  if (pathname.startsWith('/assets/')) {
    if (await serveDist(response, pathname.slice(1))) return
    return json(response, 404, { detail: 'Asset not found' })
  }
  if (pathname === '/favicon.svg') {
    if (await serveDist(response, 'favicon.svg')) return
    return json(response, 404, { detail: 'Not found' })
  }
  if (pathname === '/old' || pathname === '/old/') {
    response.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' })
    return response.end('<!doctype html><main data-workspace-band><script src="/static/app.js"></script></main>')
  }
  if (pathname === '/legacy' || pathname === '/legacy/') {
    response.writeHead(307, { Location: '/old' })
    return response.end()
  }
  if (pathname === '/app-v2' || pathname === '/app-v2/') {
    response.writeHead(307, { Location: '/' })
    return response.end()
  }
  if (pathname.startsWith('/app-v2/')) {
    response.writeHead(307, { Location: `/${pathname.slice('/app-v2/'.length)}` })
    return response.end()
  }
  if (pathname === '/' || ['/ask', '/library', '/evidence', '/trace', '/quality'].includes(pathname)) {
    if (await serveDist(response, 'index.html')) return
  }
  response.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' })
  response.end('Not found')
})

server.listen(port, '127.0.0.1', () => process.stdout.write(`Mock frontend server listening on ${port}\n`))
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => server.close(() => process.exit(0)))
