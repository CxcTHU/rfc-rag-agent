type JsonOptions = RequestInit & { token?: string | null }

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export function isAuthApiError(error: unknown) {
  return error instanceof ApiError && (error.status === 401 || error.status === 403)
}

export function shouldRetryApiQuery(failureCount: number, error: unknown) {
  if (failureCount >= 1) return false
  return !(error instanceof ApiError) || error.status >= 500
}

export async function apiJson<T>(path: string, options: JsonOptions = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (!headers.has('Content-Type') && options.body) headers.set('Content-Type', 'application/json')
  if (options.token) headers.set('Authorization', `Bearer ${options.token}`)
  const response = await fetch(path, { credentials: 'same-origin', ...options, headers })
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`
    try {
      const payload = await response.json() as { detail?: unknown }
      message = safeApiErrorMessage(payload.detail) || message
    } catch {
      // Keep the status-only message; never expose a raw response body.
    }
    throw new ApiError(message, response.status)
  }
  return response.json() as Promise<T>
}

function safeApiErrorMessage(detail: unknown): string {
  if (!detail) return ''
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((item) => {
      if (typeof item === 'string') return item
      if (!item || typeof item !== 'object') return ''
      const record = item as Record<string, unknown>
      const location = Array.isArray(record.loc) ? record.loc.join('.') : ''
      const message = typeof record.msg === 'string' ? record.msg : ''
      return [location, message].filter(Boolean).join(': ')
    }).filter(Boolean).join('; ')
  }
  if (typeof detail === 'object') {
    const message = (detail as Record<string, unknown>).message
    return typeof message === 'string' ? message : '请求失败，请稍后重试。'
  }
  return String(detail)
}
