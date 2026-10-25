import type { HealthResponse, Incident, IncidentCreate } from './types'

const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? ''

class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, {
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
      ...init,
    })
  } catch {
    throw new ApiError(
      'Cannot reach the SentinelAI backend. Start uvicorn on port 8000, then refresh.',
      0,
    )
  }

  if (!response.ok) {
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
