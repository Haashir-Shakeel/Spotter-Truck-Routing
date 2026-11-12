import type { ApiErrorBody } from '../types/api'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: Record<string, unknown>

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

function isApiErrorBody(value: unknown): value is ApiErrorBody {
  return typeof value === 'object' && value !== null && 'error' in value
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init.headers },
  })

  const body: unknown = await response.json().catch(() => null)

  if (!response.ok) {
    if (isApiErrorBody(body)) {
      const { code, message, details } = body.error
      throw new ApiError(response.status, code, message, details)
    }
    throw new ApiError(response.status, 'HTTP_ERROR', `Request failed with status ${response.status}`)
  }

  return body as T
}
