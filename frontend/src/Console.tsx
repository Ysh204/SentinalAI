import { type FormEvent, type ReactNode, useCallback, useEffect, useMemo, useState } from 'react'
import { api } from './api'
import { sampleIncident, workflow } from './data'
import type { HealthResponse, Incident } from './types'

type WorkspaceTab = 'flow' | 'analysis' | 'patch' | 'checks'

const MOCK_SAMPLE_DIFF = `--- a/buggy_app.py
+++ b/buggy_app.py
@@ -4,3 +4,3 @@
 def add(left: int, right: int) -> int:
     """Return the sum of two integers."""
-    return left - right  # BUG: should add
+    return left + right`

function statusClass(status: string) {
  if (status === 'APPROVED' || status === 'VALIDATED') return 'good'
  if (status === 'REJECTED' || status === 'FAILED' || status === 'VALIDATION_FAILED')
    return 'bad'
  if (status === 'ANALYZING' || status === 'VALIDATING') return 'busy'
  return 'idle'
}

function statusLabel(status: string) {
  return status.replaceAll('_', ' ').toLowerCase()
}

function stepIndex(status: string) {
  if (status === 'APPROVED') return 4
  if (status === 'REJECTED') return -1
  if (status === 'VALIDATED' || status === 'VALIDATION_FAILED') return 3
  if (status === 'PATCH_GENERATED') return 2
  if (status === 'ANALYZED' || status === 'ANALYZING') return 1
  return 0
}

function formatWhen(iso?: string) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function Icon({ name }: { name: string }) {
  const common = {
    width: 16,
    height: 16,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.8,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    'aria-hidden': true,
  }
  if (name === 'plus')
    return (
      <svg {...common}>
        <path d="M12 5v14M5 12h14" />
      </svg>
    )
  if (name === 'home')
    return (
      <svg {...common}>
        <path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z" />
      </svg>
    )
  if (name === 'console')
    return (
      <svg {...common}>
        <rect x="3" y="4" width="18" height="16" rx="3" />
        <path d="m8 9 3 3-3 3M13 15h3" />
      </svg>
    )
  if (name === 'folder')
    return (
      <svg {...common}>
        <path d="M4 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z" />
      </svg>
    )
  if (name === 'send')
    return (
      <svg {...common}>
        <path d="M5 12h13M12 5l7 7-7 7" />
      </svg>
    )
  if (name === 'shield')
    return (
      <svg {...common}>
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      </svg>
    )
  if (name === 'check')
    return (
      <svg {...common}>
        <polyline points="20 6 9 17 4 12" />
      </svg>
    )
  if (name === 'sparkles')
    return (
      <svg {...common}>
        <path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z" />
      </svg>
    )
  if (name === 'info')
    return (
      <svg {...common}>
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="16" x2="12" y2="12" />
        <line x1="12" y1="8" x2="12.01" y2="8" />
      </svg>
    )
  if (name === 'refresh')
    return (
      <svg {...common}>
        <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
        <path d="M3 3v5h5" />
        <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
        <path d="M21 21v-5h-5" />
      </svg>
    )
  if (name === 'arrow-left')
    return (
      <svg {...common}>
        <line x1="19" y1="12" x2="5" y2="12" />
        <polyline points="12 19 5 12 12 5" />
      </svg>
    )
  return (
    <svg {...common}>
      <circle cx="12" cy="12" r="8" />
    </svg>
  )
}

export default function Console() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [incident, setIncident] = useState<Incident | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')
  const [reason, setReason] = useState('')
  const [form, setForm] = useState({ ...sampleIncident })
  const [composing, setComposing] = useState(false)
  const [tab, setTab] = useState<WorkspaceTab>('flow')

  const loadList = useCallback(async () => {
    try {
      const list = await api.listIncidents()
      setIncidents(list)
      return list
    } catch {
      return []
    }
  }, [])

  const loadHealth = useCallback(async () => {
    try {
      const h = await api.health()
      setHealth(h)
    } catch {
      setHealth(null)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    Promise.all([loadHealth(), loadList()])
      .then(([, list]) => {
        if (!cancelled && list[0]) setSelectedId((id) => id ?? list[0].id)
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message)
      })
    return () => {
      cancelled = true
    }
  }, [loadHealth, loadList])

  useEffect(() => {
    if (!selectedId) {
      setIncident(null)
      return
    }
    // Check in local state first
    const local = incidents.find((i) => i.id === selectedId)
    if (local && !health) {
      setIncident(local)
      setTab('flow')
      return
    }
    api
      .getIncident(selectedId)
      .then((item) => {
        setIncident(item)
        setTab('flow')
      })
      .catch(() => {
        if (local) {
          setIncident(local)
          setTab('flow')
        }
      })
  }, [selectedId, incidents, health])

  async function run(label: string, fn: () => Promise<Incident>) {
    setBusy(label)
    setError('')
    try {
      const next = await fn()
      setIncident(next)
      setSelectedId(next.id)
      setComposing(false)
      await loadList()
    } catch (err) {
      // If backend is offline, support graceful simulation step
      if (!health && incident) {
        handleLocalSimulation(label)
      } else {
        setError(err instanceof Error ? err.message : 'Request failed')
      }
    } finally {
      setBusy('')
    }
  }

  function handleLocalSimulation(action: string) {
    if (!incident) return
    const now = new Date().toISOString()
    let updated: Incident = { ...incident }

    if (action === 'analyze') {
      updated = {
        ...updated,
        status: 'ANALYZED',
        root_cause_analysis: {
          hypothesis:
            'The failing assertion is consistent with `add()` returning a difference instead of a sum. In the sample repository, `add(left, right)` uses subtraction (`left - right`). That causes `add(2, 3)` to return `-1` instead of `5`.',
          suspected_file: 'buggy_app.py',
          suspected_function: 'add',
          confidence: 'high',
          disclaimer: 'Generated by SentinelAI offline analysis engine. Verify before committing.',
          source_files_considered: ['buggy_app.py', 'test_buggy_app.py'],
          recommended_next_steps: [
            'Synthesize a unified diff changing subtraction to addition in `add()`.',
            'Apply candidate patch in a disposable test sandbox only.',
            'Run full test verification suite before recording human approval.',
          ],
          provider: 'offline-sandbox',
        },
        history: [
          ...updated.history,
          {
            timestamp: now,
            event: 'ANALYSIS_COMPLETED',
            from_status: updated.status,
            to_status: 'ANALYZED',
            detail: 'Root cause analysis finished with candidate file identified.',
          },
        ],
      }
    } else if (action === 'patch') {
      updated = {
        ...updated,
        status: 'PATCH_GENERATED',
        proposed_patch: MOCK_SAMPLE_DIFF,
        history: [
          ...updated.history,
          {
            timestamp: now,
            event: 'PATCH_GENERATED',
            from_status: updated.status,
            to_status: 'PATCH_GENERATED',
            detail: 'Unified diff patch synthesized against sample repository.',
          },
        ],
      }
    } else if (action === 'validate') {
      updated = {
        ...updated,
        status: 'VALIDATED',
        validation_results: {
          overall_passed: true,
          applied_files: ['buggy_app.py'],
          workspace: null,
          disclaimer: 'Sandbox verification suite executed with isolated temporary workspace.',
          checks: [
            {
              name: 'pytest::test_add',
              status: 'PASSED',
              detail: 'test_buggy_app.py:5 assert add(2, 3) == 5 [PASSED in 0.04s]',
              exit_code: 0,
              stdout: '1 passed in 0.04s',
              stderr: '',
            },
            {
              name: 'syntax::ruff',
              status: 'PASSED',
              detail: 'All linters and format checks passed cleanly.',
              exit_code: 0,
              stdout: 'All checks passed',
              stderr: '',
            },
            {
              name: 'security::boundary',
              status: 'PASSED',
              detail: 'Zero path traversal, sandbox workspace disposed.',
              exit_code: 0,
              stdout: 'Security perimeter intact',
              stderr: '',
            },
          ],
        },
        history: [
          ...updated.history,
          {
            timestamp: now,
            event: 'VALIDATION_PASSED',
            from_status: updated.status,
            to_status: 'VALIDATED',
            detail: 'Automated test suite and sandbox verification succeeded.',
          },
        ],
      }
    } else if (action === 'approve') {
      updated = {
        ...updated,
        status: 'APPROVED',
        approval: {
          decision: 'APPROVED',
          actor: 'human-operator',
          decided_at: now,
          reason: 'Verified arithmetic fix against sample test suite.',
        },
        history: [
          ...updated.history,
          {
            timestamp: now,
            event: 'APPROVED_BY_HUMAN',
            from_status: updated.status,
            to_status: 'APPROVED',
            detail: 'Human operator signed off on patch application.',
          },
        ],
      }
    } else if (action === 'reject') {
      updated = {
        ...updated,
        status: 'REJECTED',
        approval: {
          decision: 'REJECTED',
          actor: 'human-operator',
          decided_at: now,
          reason: reason || 'Operator requested revisions.',
        },
        history: [
          ...updated.history,
          {
            timestamp: now,
            event: 'REJECTED_BY_HUMAN',
            from_status: updated.status,
            to_status: 'REJECTED',
            detail: reason || 'Operator rejected candidate patch.',
          },
        ],
      }
      setReason('')
    }

    setIncident(updated)
    setIncidents((prev) => prev.map((item) => (item.id === updated.id ? updated : item)))
  }

  async function onCreate(e: FormEvent) {
    e.preventDefault()
    if (!health) {
      // In simulation mode, create local demo incident
      const now = new Date().toISOString()
      const newInc: Incident = {
        id: 'inc-' + Math.random().toString(36).substring(2, 8),
        title: form.title,
        error_message: form.error_message,
        stack_trace: form.stack_trace,
        repository_path: form.repository_path || 'sample_app',
        status: 'RECEIVED',
        created_at: now,
        updated_at: now,
        root_cause_analysis: null,
        proposed_patch: null,
        validation_results: null,
        approval: null,
        history: [{
          timestamp: now,
          event: 'INGESTED',
          from_status: null,
          to_status: 'RECEIVED',
          detail: 'Incident registered in Sentinel console.',
        }],
      }
      setIncidents((prev) => [newInc, ...prev])
      setIncident(newInc)
      setSelectedId(newInc.id)
      setComposing(false)
      return
    }

    await run('create', () =>
      api.createIncident({
        title: form.title,
        error_message: form.error_message,
        stack_trace: form.stack_trace,
        repository_path: form.repository_path || null,
      }),
    )
  }

  const canApprove =
    incident?.status === 'VALIDATED' && Boolean(incident.validation_results?.overall_passed)
  const active = incident ? stepIndex(incident.status) : 0
  const counts = incidents.reduce<Record<string, number>>((acc, item) => {
    acc[item.status] = (acc[item.status] ?? 0) + 1
    return acc
  }, {})

  const files = useMemo(() => {
    if (!incident) return []
    const set = new Set<string>()
    if (incident.repository_path) set.add(incident.repository_path)
    incident.root_cause_analysis?.suspected_file &&
      set.add(incident.root_cause_analysis.suspected_file)
    incident.root_cause_analysis?.source_files_considered.forEach((f) => set.add(f))
    incident.validation_results?.applied_files.forEach((f) => set.add(f))
    return [...set]
  }, [incident])

  return (
    <LuxuryConsole>
      <aside className="cs-sidebar">
        <a className="cs-brand" href="#top">
          <span className="cs-bloom-flower" aria-hidden="true">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
              <circle cx="12" cy="6" r="3.2" fill="#a43b4f" opacity="0.85" />
              <circle cx="17" cy="10" r="3.2" fill="#8e2b3e" />
              <circle cx="15.5" cy="16.5" r="3.2" fill="#782333" />
              <circle cx="8.5" cy="16.5" r="3.2" fill="#8e2b3e" />
              <circle cx="7" cy="10" r="3.2" fill="#a43b4f" opacity="0.85" />
              <circle cx="12" cy="12" r="2.2" fill="#ffffff" />
            </svg>
          </span>
          <span className="cs-brand-text">
            <span className="cs-brand-slash">/</span>sentinel
          </span>
          <span className="cs-brand-badge">gated</span>
        </a>

        <button
          type="button"
          className="cs-new"
          onClick={() => {
            setComposing(true)
            setForm({ ...sampleIncident })
          }}
        >
          <Icon name="plus" />
          <span>New Incident</span>
        </button>

        <nav className="cs-nav" aria-label="Console">
          <a href="#top">
            <Icon name="home" />
            <span>Overview</span>
          </a>
          <a href="#console" className="active">
            <Icon name="console" />
            <span>Incident Console</span>
          </a>
        </nav>

        <div className="cs-section-label">Incident Queue</div>
        <ul className="cs-threads">
          {incidents.length === 0 ? (
            <li className="cs-empty">
              No incidents in queue. Load the demo scenario to walk the full diagnosis and validation cycle.
            </li>
          ) : null}
          {incidents.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                className={item.id === selectedId && !composing ? 'active' : ''}
                onClick={() => {
                  setComposing(false)
                  setSelectedId(item.id)
                }}
              >
                <em className={`cs-dot ${statusClass(item.status)}`} />
                <strong>{item.title}</strong>
                <span>
                  {statusLabel(item.status)} · {item.id.slice(0, 8)}
                </span>
              </button>
            </li>
          ))}
        </ul>

        <div className="cs-plan">
          <div className="cs-plan-badge">
            <span className="cs-mono-tag">// SAFETY PROTOCOL</span>
          </div>
          <strong>Human-Gated Remediation</strong>
          <small>
            Candidate diffs run solely inside ephemeral sandboxes with real tests. Source repos are never modified without explicit human sign-off.
          </small>
        </div>
      </aside>

      <section className="cs-center">
        <header className="cs-topbar">
          <div>
            <p className="cs-kicker">
              {composing
                ? 'Incident Dispatch // Sandbox Triage'
                : incident
                  ? 'Runtime Diagnostic // Execution Trace'
                  : 'Incident Runtime // Governance Engine'}
            </p>
            <h1 className="cs-editorial-heading">
              {composing ? (
                <>Submit failure telemetry for <em>sandboxed triage</em></>
              ) : incident ? (
                <>Runtime incident <em>{incident.title}</em></>
              ) : (
                <>Connect runtime failures to <em>verified patches</em></>
              )}
            </h1>
            <p className="cs-editorial-sub">
              SentinelAI isolates root causes, synthesizes candidate diffs in disposable workspaces, and awaits human verification — without giving agents autonomous write access to your repository.
            </p>
          </div>
          <div className={`cs-health ${health ? 'up' : 'down'}`}>
            <span className="cs-portal-dot" />
            <div>
              <strong>{health ? 'Backend Operational' : 'Interactive Sandbox'}</strong>
              <small>
                {health
                  ? `${health.ai_provider} · database ready`
                  : 'Simulation active — full loop enabled'}
              </small>
            </div>
          </div>
        </header>

        {!health ? (
          <p className="cs-banner warn">
            <Icon name="info" />
            <span>
              Backend service on port 8000 is offline. Running in standalone interactive simulation mode — submit incidents and explore the full automated loop.
            </span>
          </p>
        ) : error ? (
          <p className="cs-banner bad">
            <Icon name="info" />
            <span>{error}</span>
          </p>
        ) : null}

        <div className="cs-scroll">
          {composing || !incident ? (
            <div className="cs-compose-wrap">
              {/* Bloom-styled Command Prompt Box */}
              <div className="cs-prompt-banner">
                <div className="cs-prompt-label">TELL SENTINEL AI:</div>
                <div className="cs-prompt-box">
                  <span className="cs-prompt-text">
                    &gt; Read runtime trace, isolate suspected file, and propose unified diff.
                  </span>
                  <button
                    type="button"
                    className="cs-prompt-copy-btn"
                    onClick={() => setForm({ ...sampleIncident })}
                  >
                    LOAD DEMO
                  </button>
                </div>
                <div className="cs-prompt-compat">
                  <span>TEST SUITES SUPPORTED:</span>
                  <div className="cs-compat-pills">
                    <code>pytest</code>
                    <code>ruff</code>
                    <code>unittest</code>
                    <code>disposable sandbox</code>
                    <code>human gate</code>
                  </div>
                </div>
              </div>

              <form className="cs-form-card" onSubmit={onCreate}>
                <div className="cs-form-head">
                  <span className="cs-form-kicker">INCIDENT SPECIFICATION</span>
                  <h3>Diagnostic Inputs</h3>
                </div>

                <div className="cs-field-group">
                  <label>
                    <span className="cs-field-label">01 // Incident Title</span>
                    <input
                      value={form.title}
                      onChange={(e) => setForm({ ...form, title: e.target.value })}
                      required
                      placeholder="e.g. Arithmetic regression in payment calculation"
                    />
                  </label>
                </div>

                <div className="cs-field-group">
                  <label>
                    <span className="cs-field-label">02 // Failure Diagnostic / Error Payload</span>
                    <textarea
                      value={form.error_message}
                      onChange={(e) => setForm({ ...form, error_message: e.target.value })}
                      required
                      rows={3}
                      placeholder="Paste runtime exception, assertion failure, or HTTP 500 error headline…"
                    />
                  </label>
                </div>

                <div className="cs-field-group">
                  <label>
                    <span className="cs-field-label">03 // Call Stack / Execution Frames</span>
                    <textarea
                      value={form.stack_trace}
                      onChange={(e) => setForm({ ...form, stack_trace: e.target.value })}
                      rows={4}
                      placeholder="Paste full call stack frames, traceback output, or relevant log lines…"
                    />
                  </label>
                </div>

                <div className="cs-field-group">
                  <label>
                    <span className="cs-field-label">04 // Target Repository Scope</span>
                    <input
                      value={form.repository_path}
                      onChange={(e) => setForm({ ...form, repository_path: e.target.value })}
                      placeholder="sample_app"
                    />
                  </label>
                </div>

                <div className="cs-form-actions">
                  <button
                    type="button"
                    className="cs-btn ghost"
                    onClick={() => setForm({ ...sampleIncident })}
                  >
                    <Icon name="refresh" />
                    <span>Load Sample Scenario</span>
                  </button>
                  {incident ? (
                    <button
                      type="button"
                      className="cs-btn ghost"
                      onClick={() => setComposing(false)}
                    >
                      Cancel
                    </button>
                  ) : null}
                  <button
                    className="cs-btn primary"
                    type="submit"
                    disabled={Boolean(busy)}
                  >
                    <span>{busy === 'create' ? 'Dispatching…' : 'Synthesize Diff & Validate'}</span>
                    <Icon name="send" />
                  </button>
                </div>
              </form>
            </div>
          ) : (
            <>
              {/* Monospace Minimal Stepper */}
              <ol className="cs-pipeline">
                {workflow.map((label, i) => (
                  <li
                    key={label}
                    className={
                      incident.status === 'REJECTED'
                        ? 'bad'
                        : i < active
                          ? 'done'
                          : i === active
                            ? 'now'
                            : ''
                    }
                  >
                    <span>{String(i + 1).padStart(2, '0')}</span>
                    <div className="cs-step-name">{label.replace('_', ' ').toLowerCase()}</div>
                  </li>
                ))}
              </ol>

              {/* Capsule Toggle Switcher (like [FOR USERS] [FOR BUILDERS] in Bloom) */}
              <div className="cs-tabs" role="tablist">
                {(
                  [
                    ['flow', 'Overview & Trace'],
                    ['analysis', 'Root Cause'],
                    ['patch', 'Candidate Diff'],
                    ['checks', 'Validation Suite'],
                  ] as const
                ).map(([id, label]) => (
                  <button
                    key={id}
                    type="button"
                    role="tab"
                    aria-selected={tab === id}
                    className={tab === id ? 'on' : ''}
                    onClick={() => setTab(id)}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {tab === 'flow' || tab === 'analysis' ? (
                <>
                  <article className="cs-bubble user">
                    <header>
                      <span className="cs-mono-header">REPORTED DIAGNOSTIC PAYLOAD</span>
                      <time>{formatWhen(incident.created_at)}</time>
                    </header>
                    <p>{incident.error_message}</p>
                    <em className={`cs-pill ${statusClass(incident.status)}`}>
                      {statusLabel(incident.status)}
                    </em>
                  </article>

                  {incident.root_cause_analysis ? (
                    <article className="cs-bubble ai">
                      <header>
                        <span className="cs-mono-header">AUTOMATED ROOT-CAUSE DIAGNOSIS</span>
                        <span>
                          {incident.root_cause_analysis.provider} ·{' '}
                          {incident.root_cause_analysis.confidence} confidence
                        </span>
                      </header>
                      <p>{incident.root_cause_analysis.hypothesis}</p>
                      <p className="cs-meta">
                        Suspected Target: <code>{incident.root_cause_analysis.suspected_file ?? '—'}</code>
                        {incident.root_cause_analysis.suspected_function ? (
                          <> / <code>{incident.root_cause_analysis.suspected_function}</code></>
                        ) : null}
                      </p>
                      <p className="cs-hint">{incident.root_cause_analysis.disclaimer}</p>
                      {incident.root_cause_analysis.recommended_next_steps.length > 0 && (
                        <div className="cs-steps-box">
                          <span className="cs-steps-title">Recommended Remediation Steps:</span>
                          <ul>
                            {incident.root_cause_analysis.recommended_next_steps.map((s) => (
                              <li key={s}>{s}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </article>
                  ) : tab === 'analysis' ? (
                    <p className="cs-hint">No diagnostic analysis run yet. Select "Diagnose Root Cause" below.</p>
                  ) : null}
                </>
              ) : null}

              {tab === 'flow' || tab === 'patch' ? (
                incident.proposed_patch ? (
                  <article className="cs-code-card">
                    <header>
                      <div className="cs-code-title">
                        <Icon name="console" />
                        <strong>Candidate Sandbox Patch</strong>
                      </div>
                      <span>Unified diff · Isolated environment (origin untouched)</span>
                    </header>
                    <pre>{incident.proposed_patch}</pre>
                  </article>
                ) : tab === 'patch' ? (
                  <p className="cs-hint">
                    No patch synthesized yet. Select "Synthesize Patch" from the action dock below.
                  </p>
                ) : null
              ) : null}

              {tab === 'flow' || tab === 'checks' ? (
                incident.validation_results ? (
                  <article className="cs-bubble ai">
                    <header>
                      <span className="cs-mono-header">AUTOMATED TEST SUITE VERIFICATION</span>
                      <em
                        className={`cs-pill ${incident.validation_results.overall_passed ? 'good' : 'bad'}`}
                      >
                        {incident.validation_results.overall_passed ? 'all checks passed' : 'checks failed'}
                      </em>
                    </header>
                    <p className="cs-hint">{incident.validation_results.disclaimer}</p>
                    <ul className="cs-checks">
                      {incident.validation_results.checks.map((c) => (
                        <li key={c.name}>
                          <div className="cs-check-head">
                            <code>{c.name}</code>
                            <span className={`cs-check-badge ${c.status.toLowerCase()}`}>{c.status}</span>
                          </div>
                          <small>{c.detail}</small>
                        </li>
                      ))}
                    </ul>
                  </article>
                ) : tab === 'checks' ? (
                  <p className="cs-hint">No verification results recorded yet. Click "Run Test Suite" to validate.</p>
                ) : null
              ) : null}

              {incident.approval ? (
                <p className="cs-thanks">
                  Decision Recorded: {incident.approval.decision} by {incident.approval.actor}.{' '}
                  {incident.approval.reason ?? ''}
                </p>
              ) : null}

              {tab === 'flow' ? (
                <details className="cs-history">
                  <summary>Audit Trail & Call Stack</summary>
                  <pre>{incident.stack_trace || '(empty stack trace)'}</pre>
                  <ul>
                    {incident.history.map((h, i) => (
                      <li key={`${h.timestamp}-${i}`}>
                        {formatWhen(h.timestamp)} · {h.event} · {h.from_status ?? 'initial'} →{' '}
                        {h.to_status}
                      </li>
                    ))}
                  </ul>
                </details>
              ) : null}
            </>
          )}
        </div>

        {!composing && incident ? (
          <footer className="cs-composer">
            <div className="cs-tools">
              <button
                type="button"
                className="cs-btn dark"
                disabled={Boolean(busy)}
                onClick={() => run('analyze', () => api.analyze(incident.id))}
              >
                <Icon name="sparkles" />
                <span>{busy === 'analyze' ? 'Diagnosing…' : 'Diagnose Root Cause'}</span>
              </button>
              <button
                type="button"
                className="cs-btn ghost"
                disabled={Boolean(busy)}
                onClick={() => run('patch', () => api.generatePatch(incident.id))}
              >
                <Icon name="console" />
                <span>{busy === 'patch' ? 'Synthesizing…' : 'Synthesize Patch'}</span>
              </button>
              <button
                type="button"
                className="cs-btn ghost"
                disabled={Boolean(busy)}
                onClick={() => run('validate', () => api.validate(incident.id))}
              >
                <Icon name="check" />
                <span>{busy === 'validate' ? 'Running Suite…' : 'Run Test Suite'}</span>
              </button>
              <button
                type="button"
                className="cs-btn primary"
                disabled={Boolean(busy) || !canApprove}
                onClick={() => run('approve', () => api.approve(incident.id))}
              >
                <Icon name="shield" />
                <span>{busy === 'approve' ? 'Authorizing…' : 'Approve & Promote'}</span>
              </button>
            </div>
            {!canApprove ? (
              <p className="cs-hint">
                <Icon name="info" />
                <span>Human Gate: Patch promotion is locked until automated test suites pass.</span>
              </p>
            ) : null}
            <div className="cs-reject">
              <input
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Specify feedback or rationale to reject candidate patch…"
              />
              <button
                type="button"
                className="cs-send"
                disabled={Boolean(busy) || !reason.trim()}
                onClick={() => run('reject', () => api.reject(incident.id, reason.trim()))}
                aria-label="Reject candidate patch"
              >
                {busy === 'reject' ? '…' : <Icon name="send" />}
              </button>
            </div>
          </footer>
        ) : null}
      </section>

      <aside className="cs-rail">
        <div className="cs-rail-head">
          <div>
            <strong>Telemetry Ops</strong>
            <p className="cs-mono-meta">// ACTIVE QUEUE</p>
          </div>
          <span className="cs-rail-chip">Online</span>
        </div>
        <div className="cs-stats">
          <article>
            <small>TOTAL</small>
            <b>{incidents.length}</b>
          </article>
          <article>
            <small>QUEUED</small>
            <b>{counts.RECEIVED ?? 0}</b>
          </article>
          <article>
            <small>VALIDATED</small>
            <b>{counts.VALIDATED ?? 0}</b>
          </article>
          <article>
            <small>APPROVED</small>
            <b>{counts.APPROVED ?? 0}</b>
          </article>
        </div>

        <div className="cs-files">
          <div className="cs-section-label">Analyzed Artifacts</div>
          {files.length === 0 ? (
            <p className="cs-empty">
              Target repository files and localized modules will be indexed here after fault analysis.
            </p>
          ) : (
            <ul>
              {files.map((f) => (
                <li key={f}>
                  <Icon name="folder" />
                  <span>{f}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <a className="cs-back" href="#top">
          <Icon name="arrow-left" />
          <span>Return to Overview</span>
        </a>
      </aside>
    </LuxuryConsole>
  )
}

function LuxuryConsole({ children }: { children: ReactNode }) {
  return (
    <div className="page console-page">
      {/* Opalescent celestial portal glow in the background */}
      <div className="cs-portal-glow" aria-hidden="true" />
      {/* Delicate botanical branches inspired by /bloom */}
      <div className="cs-bloom-framing-left" aria-hidden="true" />
      <div className="cs-bloom-framing-right" aria-hidden="true" />
      <div className="stage">{children}</div>
    </div>
  )
}
