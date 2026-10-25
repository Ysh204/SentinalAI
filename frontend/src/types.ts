export type IncidentStatus =
  | 'RECEIVED'
  | 'TRIAGING'
  | 'TRIAGED'
  | 'ANALYZING'
  | 'ANALYZED'
  | 'PATCH_GENERATED'
  | 'VALIDATING'
  | 'VALIDATED'
  | 'VALIDATION_FAILED'
  | 'REPLAYING'
  | 'PATCH_VERIFIED'
  | 'MITIGATION_PROPOSED'
  | 'MITIGATING'
  | 'MITIGATED'
  | 'APPROVED'
  | 'REJECTED'
  | 'FAILED'
  | 'RESOLVED'

export type HealthResponse = {
  status: string
  app: string
  team: string
  version: string
  ai_provider: string
  gemini_configured: boolean
  database_ready: boolean
  victim_app_url?: string | null
}

export type HistoryEvent = {
  timestamp: string
  from_status: IncidentStatus | null
  to_status: IncidentStatus
  event: string
  detail: string
}

export type AnalysisResult = {
  hypothesis: string
  suspected_file: string | null
  suspected_function: string | null
  confidence: string
  recommended_next_steps: string[]
  disclaimer: string
  provider: string
  source_files_considered: string[]
}

export type ValidationCheck = {
  name: string
  status: string
  detail: string
  exit_code: number | null
  stdout: string
  stderr: string
}

export type ValidationResults = {
  overall_passed: boolean
  checks: ValidationCheck[]
  applied_files: string[]
  workspace: string | null
  disclaimer: string
}

export type ApprovalRecord = {
  decision: string
  reason: string | null
  decided_at: string
  actor: string
}

export type Verdict = {
  category: string
  confidence: number
  evidence: string[]
  recommended_track: string
  escalate_to_human: boolean
  recommended_action: string | null
  provider: string
  disclaimer: string
}

export type ReplayResult = {
  before_status: number | null
  after_status: number | null
  before_ok: boolean
  after_ok: boolean
  request_path: string
  detail: string
  sandbox: string | null
}

export type MitigationRecord = {
  action: string
  simulated: boolean
  status: string
  executed_at: string | null
  actor: string | null
  error_rate_before: number | null
  error_rate_after: number | null
  recovered: boolean | null
  detail: string
}

export type Postmortem = {
  summary: string
  root_cause: string
  action_items: string[]
  provider: string
  generated_at: string | null
}

export type MetricsResponse = {
  incidents_total: number
  by_status: Record<string, number>
  by_category: Record<string, number>
  mean_time_to_resolution_seconds: number | null
  open_count: number
}

export type Incident = {
  id: string
  title: string
  error_message: string
  stack_trace: string
  repository_path: string | null
  status: IncidentStatus
  source?: string
  fingerprint?: string | null
  occurrence_count?: number
  captured_request?: Record<string, unknown> | null
  logs?: string[]
  verdict?: Verdict | null
  root_cause_analysis: AnalysisResult | null
  proposed_patch: string | null
  validation_results: ValidationResults | null
  replay?: ReplayResult | null
  mitigation?: MitigationRecord | null
  postmortem?: Postmortem | null
  approval: ApprovalRecord | null
  history: HistoryEvent[]
  created_at: string
  updated_at: string
}

export type IncidentCreate = {
  title: string
  error_message: string
  stack_trace: string
  repository_path: string | null
}
