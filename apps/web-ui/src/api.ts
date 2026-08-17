import type {
  AlarmView,
  CycleDetail,
  CycleSummary,
  Disposition,
  SopDefinition,
  StationSnapshot,
  VisionModel,
  VisionRecipe,
  VisionRecipeDraft,
  VisionTestResult,
} from './types'

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
  visionModels: () => request<VisionModel[]>('/api/v1/vision/models'),
  visionRecipes: () => request<VisionRecipe[]>('/api/v1/vision/recipes'),
  createVisionRecipe: (recipe: VisionRecipeDraft) => request<VisionRecipe>('/api/v1/vision/recipes', {
    method: 'POST', body: JSON.stringify(recipe),
  }),
  updateVisionRecipe: (templateId: string, recipe: VisionRecipeDraft) => request<VisionRecipe>(`/api/v1/vision/recipes/${encodeURIComponent(templateId)}`, {
    method: 'PUT', body: JSON.stringify(recipe),
  }),
  createVisionDraft: (templateId: string) => request<VisionRecipe>(`/api/v1/vision/recipes/${encodeURIComponent(templateId)}/draft`, { method: 'POST' }),
  publishVisionRecipe: (templateId: string) => request<VisionRecipe>(`/api/v1/vision/recipes/${encodeURIComponent(templateId)}/publish`, { method: 'POST' }),
  calibrateVisionRecipe: (templateId: string, version?: number) => request<{ calibration: { status: string; detail: string | null } }>(
    `/api/v1/vision/recipes/${encodeURIComponent(templateId)}/calibration${version ? `?version=${version}` : ''}`, { method: 'POST' },
  ),
  testVisionRecipe: (templateId: string, version?: number) => request<{ result: VisionTestResult }>(
    `/api/v1/vision/recipes/${encodeURIComponent(templateId)}/test${version ? `?version=${version}` : ''}`, { method: 'POST' },
  ),
}

export function stationSocketUrl(id = 'ST01'): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/ws/v1/stations/${id}`
}
