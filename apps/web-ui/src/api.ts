import type { AlarmView, CycleDetail, CycleSummary, Disposition, SopDefinition, StationSnapshot } from './types'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(body.detail ?? `请求失败 (${response.status})`)
  }
  return response.json() as Promise<T>
}

export const api = {
  station: (id = 'ST01') => request<StationSnapshot>(`/api/v1/stations/${id}/snapshot`),
  scenario: (name: string) => request<StationSnapshot>(`/api/v1/simulation/scenarios/${name}`, { method: 'POST' }),
  reset: () => request<StationSnapshot>('/api/v1/simulation/reset', {
    method: 'POST', body: JSON.stringify({ actor_id: 'web-operator' }),
  }),
  alarms: (domain?: string) => request<AlarmView[]>(`/api/v1/alarms${domain ? `?domain=${domain}` : ''}`),
  acknowledge: (id: string, reason: string) => request<AlarmView>(`/api/v1/alarms/${encodeURIComponent(id)}/acknowledge`, {
    method: 'POST',
    body: JSON.stringify({ actor_id: 'quality-web', client_id: 'web-ui', reason }),
  }),
  cycles: (serial?: string) => request<CycleSummary[]>(`/api/v1/cycles${serial ? `?serial_number=${encodeURIComponent(serial)}` : ''}`),
  cycle: (id: string) => request<CycleDetail>(`/api/v1/cycles/${encodeURIComponent(id)}`),
  disposition: (cycleId: string, disposition: Disposition, reason: string) =>
    request<CycleDetail>(`/api/v1/cycles/${encodeURIComponent(cycleId)}/dispositions`, {
      method: 'POST',
      body: JSON.stringify({ disposition, actor_id: 'quality-web', client_id: 'web-ui', reason, evidence_ids: [] }),
    }),
  sop: () => request<SopDefinition>('/api/v1/sops/SOP_001/versions/1.1'),
}

export function stationSocketUrl(id = 'ST01'): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/ws/v1/stations/${id}`
}
