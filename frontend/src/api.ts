import type { HealthResponse, Incident, IncidentCreate, MetricsResponse } from './types'

const envBase = (import.meta.env.VITE_API_URL as string | undefined)?.trim()
const envApiKey = (import.meta.env.VITE_API_KEY as string | undefined)?.trim()

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
  const authHeaders: Record<string, string> = envApiKey ? { Authorization: `Bearer ${envApiKey}` } : {}
  const extra = {
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders,
      ...(init?.headers ?? {}),
    },
    ...init,
  }

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
      if ((response.status === 502 || response.status === 504) && !envBase) {
        lastError = new ApiError('Gateway error on this address; trying the next.', response.status)
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
  listIncidents: (limit = 100, offset = 0) =>
    request<Incident[]>(`/api/incidents?limit=${limit}&offset=${offset}`),
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
  triage: (id: string) => request<Incident>(`/api/incidents/${id}/triage`, { method: 'POST' }),
  replay: (id: string) => request<Incident>(`/api/incidents/${id}/replay`, { method: 'POST' }),
  mitigate: (id: string) => request<Incident>(`/api/incidents/${id}/mitigate`, { method: 'POST' }),
  postmortem: (id: string) =>
    request<Incident>(`/api/incidents/${id}/postmortem`, { method: 'POST' }),
  ingestAlert: (payload: Record<string, unknown>) =>
    request<Incident>('/api/alerts', { method: 'POST', body: JSON.stringify(payload) }),
  breakCheckout: (mode: string) =>
    request<Incident>('/api/demo/break', { method: 'POST', body: JSON.stringify({ mode }) }),
  simulateIncident: () => request<Incident>('/api/demo/simulate', { method: 'POST' }),
  metrics: () => request<MetricsResponse>('/api/metrics'),
}
