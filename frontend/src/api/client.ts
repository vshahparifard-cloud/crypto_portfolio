/**
 * Thin fetch wrapper. Two responsibilities: attach the in-memory access token,
 * and transparently rotate it once when the server says it expired.
 */
import type { ApiErrorBody } from './types'

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? '/api/v1'

export class ApiError extends Error {
  code: string
  details: Record<string, unknown>
  status: number

  constructor(status: number, body: ApiErrorBody) {
    super(body.message || 'خطای نامشخص')
    this.status = status
    this.code = body.code || 'unknown'
    this.details = body.details ?? {}
  }
}

let accessToken: string | null = null
let onUnauthorized: (() => void) | null = null

export function setAccessToken(token: string | null): void {
  accessToken = token
}

export function onSessionLost(handler: () => void): void {
  onUnauthorized = handler
}

async function parse(response: Response): Promise<unknown> {
  if (response.status === 204) return null
  const text = await response.text()
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return { code: 'bad_response', message: text.slice(0, 200) }
  }
}

async function refreshAccessToken(): Promise<boolean> {
  const response = await fetch(`${BASE}/auth/refresh`, {
    method: 'POST',
    credentials: 'include',
  })
  if (!response.ok) return false
  const body = (await response.json()) as { access_token: string }
  accessToken = body.access_token
  return true
}

async function send<T>(path: string, init: RequestInit, retry = true): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body) headers.set('Content-Type', 'application/json')
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)

  const response = await fetch(`${BASE}${path}`, { ...init, headers, credentials: 'include' })
  if (response.ok) return (await parse(response)) as T

  const body = (await parse(response)) as ApiErrorBody
  if (response.status === 401 && retry && !path.startsWith('/auth/')) {
    if (await refreshAccessToken()) return send<T>(path, init, false)
    accessToken = null
    onUnauthorized?.()
  }
  throw new ApiError(response.status, body ?? { code: 'unknown', message: 'خطای نامشخص' })
}

export const api = {
  get: <T>(path: string) => send<T>(path, { method: 'GET' }),
  post: <T>(path: string, body?: unknown) =>
    send<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body: unknown) =>
    send<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
  delete: <T>(path: string) => send<T>(path, { method: 'DELETE' }),
  streamUrl: () => `${BASE}/market/stream`,
}
