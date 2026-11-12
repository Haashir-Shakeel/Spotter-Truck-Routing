/** Mirrors the backend error contract: {"error": {"code", "message", "details"}}. */
export interface ApiErrorBody {
  error: {
    code: string
    message: string
    details: Record<string, unknown>
  }
}

export interface HealthResponse {
  status: 'ok'
  time: string
}
