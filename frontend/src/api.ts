import type { HealthResponse, Incident, IncidentCreate } from './types'

const envBase = (import.meta.env.VITE_API_URL as string | undefined)?.trim()

function bases(): string[] {
  if (envBase) return [envBase.replace(/\/$/, '')]
  // Hit uvicorn on the machine that opened the browser first. The Vite proxy
  // often 502s when the UI runs in WSL and the API runs on Windows.
  return ['http://127.0.0.1:8000', 'http://localhost:8000', '']
}

class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let lastError: ApiError | undefined
  const extra = { headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) }, ...init }

  for (const base of bases()) {
    let response: Response
    try {
      response = await fetch(`${base}${path}`, extra)
    } catch {
      lastError = new ApiError(
        'Cannot reach the SentinelAI backend. Start uvicorn on port 8000, then refresh.',
        0,
      )
      continue
    }

    if (!response.ok) {
      if (response.status >= 500 && !envBase) {
        lastError = new ApiError('Cannot reach uvicorn on this address; trying the next.', response.status)
        continue
      }
      let detail = response.statusText
      try {
        const body = (await response.json()) as { detail?: string }
        if (body.detail) detail = body.detail
      } catch {
        detail = await response.text()
      }
      throw new ApiError(detail || 'Request failed', response.status)
    }

    if (response.status === 204) return undefined as T
    return (await response.json()) as T
  }

  throw (
    lastError ??
    new ApiError('Cannot reach the SentinelAI backend. Start uvicorn on port 8000, then refresh.', 0)
  )
}

export const api = {
  health: () => request<HealthResponse>('/health'),
  listIncidents: () => request<Incident[]>('/api/incidents'),
  getIncident: (id: string) => request<Incident>(`/api/incidents/${id}`),
  createIncident: (payload: IncidentCreate) =>
    request<Incident>('/api/incidents', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  analyze: (id: string) =>
    request<Incident>(`/api/incidents/${id}/analyze`, { method: 'POST' }),
  generatePatch: (id: string) =>
    request<Incident>(`/api/incidents/${id}/generate-patch`, { method: 'POST' }),
  validate: (id: string) =>
    request<Incident>(`/api/incidents/${id}/validate`, { method: 'POST' }),
  approve: (id: string) =>
    request<Incident>(`/api/incidents/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ actor: 'frontend-user' }),
    }),
  reject: (id: string, reason: string) =>
    request<Incident>(`/api/incidents/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason, actor: 'frontend-user' }),
    }),
}
