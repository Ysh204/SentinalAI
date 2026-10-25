export type IncidentStatus =
  | 'RECEIVED'
  | 'ANALYZING'
  | 'ANALYZED'
  | 'PATCH_GENERATED'
  | 'VALIDATING'
  | 'VALIDATED'
  | 'VALIDATION_FAILED'
  | 'APPROVED'
  | 'REJECTED'
  | 'FAILED'

export type HealthResponse = {
  status: string
  app: string
  team: string
  version: string
  ai_provider: string
  gemini_configured: boolean
  database_ready: boolean
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

export type Incident = {
  id: string
  title: string
  error_message: string
  stack_trace: string
  repository_path: string | null
  status: IncidentStatus
  root_cause_analysis: AnalysisResult | null
  proposed_patch: string | null
  validation_results: ValidationResults | null
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
