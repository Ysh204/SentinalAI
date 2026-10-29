import type { HealthResponse, Incident, IncidentCreate, MetricsResponse } from './types'

const envBase = (import.meta.env.VITE_API_URL as string | undefined)?.trim()
const envApiKey = (import.meta.env.VITE_API_KEY as string | undefined)?.trim()
const KEY_STORAGE = 'sentinel_api_key'

// Anything in VITE_* is public in the built bundle. Prefer a key the operator types in at runtime;
// it lives in sessionStorage only, so it is never shipped to other visitors.
export function storedKey(): string | undefined {
  try {
    return window.sessionStorage.getItem(KEY_STORAGE) ?? envApiKey
  } catch {
    return envApiKey
  }
}

export function setApiKey(key: string): void {
  try {
    window.sessionStorage.setItem(KEY_STORAGE, key)
  } catch {
    /* storage unavailable: the next request will prompt again */
  }
}

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

async function request<T>(path: string, init?: RequestInit, retried = false): Promise<T> {
  let lastError: ApiError | undefined
  const key = storedKey()
  const authHeaders: Record<string, string> = key ? { Authorization: `Bearer ${key}` } : {}
  const extra: RequestInit = {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders,
      ...((init?.headers as Record<string, string>) ?? {}),
    },
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
      if (response.status === 401 && !retried && typeof window !== 'undefined') {
        const entered = window.prompt('This SentinelAI server requires an API key:')
        if (entered?.trim()) {
          setApiKey(entered.trim())
          return request<T>(path, init, true)
        }
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
  audit: (incidentId?: string) =>
    request<Array<Record<string, unknown>>>(
      incidentId ? `/api/incidents/${incidentId}/audit` : '/api/incidents/audit'
    ),
}

export function eventsUrl(): string {
  const base = envBase ? envBase.replace(/\/$/, '') : (bases()[0] || '')
  const key = storedKey()
  const query = key ? `?access_token=${encodeURIComponent(key)}` : ''
  return `${base}/api/events${query}`
}

