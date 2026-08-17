export type Lifecycle = 'IDLE' | 'ARMED' | 'RUNNING' | 'ON_HOLD' | 'AWAITING_DISPOSITION' | 'CLOSED'
export type Conformance = 'UNKNOWN' | 'CONFORMING' | 'NONCONFORMING' | 'ABORTED'
export type Disposition = 'NONE' | 'REWORK' | 'SCRAP' | 'AUTHORIZED_RELEASE'
export type AlarmDomain = 'PROCESS' | 'SYSTEM'

export interface StationSnapshot {
  station: {
    station_id: string
    name: string
    online: boolean
    mode: 'SIMULATION' | 'SHADOW' | 'ADVISORY'
    runtime_bundle_id: string
  }
  runtime_bundle: RuntimeBundleView
  cycle: CycleSummary
  steps: StepView[]
  evidence: EvidenceView[]
  alarms: AlarmView[]
  evidence_assets: EvidenceAsset[]
  health: Record<string, string>
  video: {
    kind: string
    status: string
    stream_url: string | null
    snapshot_url: string | null
  }
  updated_at: string
}

export interface RuntimeBundleView {
  bundle_id: string
  revision: string
  sop_version: string
  configuration: Record<string, string>
}

export interface SopStepDefinition {
  id: string
  name: string
  timeout_seconds: number
  completion: Array<{ key: string; kind: string; required: boolean }>
}

export interface SopDefinition {
  sop_id: string
  version: string
  steps: SopStepDefinition[]
}

export interface CycleSummary {
  cycle_id: string | null
  serial_number: string | null
  lifecycle: Lifecycle
  conformance: Conformance
  disposition: Disposition
  current_step_id: string | null
  completed_step_ids: string[]
  runtime_bundle_id: string | null
  rework_attempt: number
  progress_percent: number
  scenario: string | null
}

export interface StepView {
  id: string
  sequence: number
  name: string
  status: 'COMPLETED' | 'RUNNING' | 'ON_HOLD' | 'WAITING'
  timeout_seconds: number
}

export interface EvidenceView {
  step_id: string
  key: string
  kind: 'HARD' | 'STATE' | 'SOFT'
  required: boolean
  expected: unknown
  value: unknown
  quality: 'VALID' | 'STALE' | 'INVALID' | 'CONFLICTED' | 'MISSING'
  source: string
  evidence_id: string | null
}

export interface AlarmView {
  alarm_id: string
  cycle_id: string | null
  domain: AlarmDomain
  code: string
  message: string
  occurred_at: string
  acknowledged: boolean
  acknowledged_by: string | null
}

export interface EvidenceAsset {
  asset_id: string
  cycle_id: string
  asset_type: string
  sha256: string
  byte_size: number
  created_at: string
  retained: boolean
}

export interface CycleDetail {
  cycle: CycleSummary
  steps: StepView[]
  evidence: EvidenceView[]
  alarms: AlarmView[]
  evidence_assets: EvidenceAsset[]
  wal_path: string
}
