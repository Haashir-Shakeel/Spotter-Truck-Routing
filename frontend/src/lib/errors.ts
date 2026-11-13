import { ApiError } from '../api/client'

function firstMessages(details: unknown, path: string[] = []): string[] {
  if (typeof details === 'string') return [`${path.join(' ')}: ${details}`.replace(/^: /, '')]
  if (Array.isArray(details)) return details.flatMap((d) => firstMessages(d, path))
  if (details && typeof details === 'object') {
    return Object.entries(details).flatMap(([key, value]) =>
      firstMessages(value, key === 'non_field_errors' ? path : [...path, key.replaceAll('_', ' ')]),
    )
  }
  return []
}

/** One readable sentence for any failure, using the API's error contract when available. */
export function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === 'VALIDATION_ERROR') {
      const messages = firstMessages(error.details)
      return messages.length ? messages.join('; ') : error.message
    }
    return error.message
  }
  if (error instanceof TypeError) return 'Could not reach the server. Check your connection.'
  return 'Something went wrong. Please try again.'
}
