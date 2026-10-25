import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { api } from './api'
import { sampleIncident, workflow } from './data'
import type { HealthResponse, Incident } from './types'
import { Cta, LuxuryStage, SectionRail } from './ui'

function statusClass(status: string) {
  if (status === 'APPROVED' || status === 'VALIDATED') return 'good'
  if (status === 'REJECTED' || status === 'FAILED' || status === 'VALIDATION_FAILED')
    return 'bad'
  if (status === 'ANALYZING' || status === 'VALIDATING') return 'busy'
  return 'idle'
}

function stepIndex(status: string) {
  if (status === 'APPROVED') return 4
  if (status === 'REJECTED') return -1
  if (status === 'VALIDATED' || status === 'VALIDATION_FAILED') return 3
  if (status === 'PATCH_GENERATED') return 2
  if (status === 'ANALYZED' || status === 'ANALYZING') return 1
  return 0
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

  const loadList = useCallback(async () => {
    const list = await api.listIncidents()
    setIncidents(list)
    return list
  }, [])

  const loadHealth = useCallback(async () => {
    const h = await api.health()
    setHealth(h)
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
    api
      .getIncident(selectedId)
      .then(setIncident)
      .catch((err: Error) => setError(err.message))
  }, [selectedId])

  async function run(label: string, fn: () => Promise<Incident>) {
    setBusy(label)
    setError('')
    try {
      const next = await fn()
      setIncident(next)
      setSelectedId(next.id)
      await loadList()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed')
    } finally {
      setBusy('')
    }
  }

  async function onCreate(e: FormEvent) {
    e.preventDefault()
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

  return (
    <LuxuryStage className="console-page">
      <header className="site-header">
        <a className="logo" href="#top">
          SENTINEL
          <sup>AI</sup>
        </a>
        <nav>
          <a href="#top">Home</a>
          <a href="#console">Console</a>
        </nav>
        <Cta href="#top" variant="ghost">
          Back to site
        </Cta>
      </header>

      <main className="console">
        <div className="frame">
          <SectionRail label="Operations" num="011" />
          <div className="console-hero">
            <div>
              <p className="kicker">Incident console</p>
              <h1>Analyze, patch, validate — then wait for a human.</h1>
            </div>
            <div className={`health-card ${health ? 'up' : 'down'}`}>
              <span>{health ? 'Backend live' : 'Preview mode'}</span>
              <strong>{health?.app ?? 'SentinelAI'}</strong>
              <small>
                {health
                  ? `provider ${health.ai_provider} · db ${health.database_ready ? 'ready' : 'missing'} · v${health.version}`
                  : 'API offline. You can still explore the console layout.'}
              </small>
            </div>
          </div>

          <div className="metrics">
            <article>
              <small>Total</small>
              <b>{incidents.length}</b>
            </article>
            <article>
              <small>Received</small>
              <b>{counts.RECEIVED ?? 0}</b>
            </article>
            <article>
              <small>Validated</small>
              <b>{counts.VALIDATED ?? 0}</b>
            </article>
            <article>
              <small>Approved</small>
              <b>{counts.APPROVED ?? 0}</b>
            </article>
          </div>

          {!health ? (
            <p className="banner-offline">
              Backend is not running yet. Start uvicorn on port 8000, then refresh to submit
              incidents.
            </p>
          ) : error ? (
            <p className="banner-error">{error}</p>
          ) : null}

          <div className="console-grid">
            <section className="panel">
              <h2>Submit incident</h2>
              <form onSubmit={onCreate}>
                <label>
                  Title
                  <input
                    value={form.title}
                    onChange={(e) => setForm({ ...form, title: e.target.value })}
                    required
                  />
                </label>
                <label>
                  Error message
                  <textarea
                    value={form.error_message}
                    onChange={(e) => setForm({ ...form, error_message: e.target.value })}
                    required
                    rows={3}
                  />
                </label>
                <label>
                  Stack trace
                  <textarea
                    value={form.stack_trace}
                    onChange={(e) => setForm({ ...form, stack_trace: e.target.value })}
                    rows={4}
                  />
                </label>
                <label>
                  Repository path
                  <input
                    value={form.repository_path}
                    onChange={(e) => setForm({ ...form, repository_path: e.target.value })}
                  />
                </label>
                <div className="form-actions">
                  <button
                    type="button"
                    className="cta cta-ghost"
                    onClick={() => setForm({ ...sampleIncident })}
                  >
                    Load sample
                  </button>
                  <button
                    className="cta cta-gold"
                    type="submit"
                    disabled={Boolean(busy) || !health}
                  >
                    {busy === 'create' ? 'Submitting…' : 'Submit incident'}
                  </button>
                </div>
              </form>

              <h2>Incidents</h2>
              <ul className="incident-list">
                {incidents.length === 0 ? <li className="empty">No incidents yet.</li> : null}
                {incidents.map((item) => (
                  <li key={item.id}>
                    <button
                      type="button"
                      className={item.id === selectedId ? 'selected' : ''}
                      onClick={() => setSelectedId(item.id)}
                    >
                      <em className={`pill ${statusClass(item.status)}`}>{item.status}</em>
                      <strong>{item.title}</strong>
                      <span>{item.id.slice(0, 8)}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>

            <section className="panel detail">
              {!incident ? (
                <div className="empty-detail">
                  <p className="kicker">Workspace</p>
                  <h2>No incident selected</h2>
                  <p className="empty">
                    Submit the sample on the left, then Analyze → Generate patch → Validate.
                    Approval stays locked until tests pass.
                  </p>
                </div>
              ) : (
                <>
                  <div className="detail-head">
                    <em className={`pill ${statusClass(incident.status)}`}>{incident.status}</em>
                    <h2>{incident.title}</h2>
                    <p>{incident.error_message}</p>
                  </div>

                  <ol className="pipeline">
                    {workflow.map((label, i) => (
                      <li
                        key={label}
                        className={
                          incident.status === 'REJECTED'
                            ? 'bad'
                            : i <= active
                              ? 'done'
                              : ''
                        }
                      >
                        <span>{String(i + 1).padStart(2, '0')}</span>
                        {label.replace('_', ' ')}
                      </li>
                    ))}
                  </ol>

                  <div className="actions">
                    <button
                      type="button"
                      className="cta cta-dark"
                      disabled={Boolean(busy)}
                      onClick={() => run('analyze', () => api.analyze(incident.id))}
                    >
                      {busy === 'analyze' ? 'Analyzing…' : 'Analyze'}
                    </button>
                    <button
                      type="button"
                      className="cta cta-ghost"
                      disabled={Boolean(busy)}
                      onClick={() => run('patch', () => api.generatePatch(incident.id))}
                    >
                      {busy === 'patch' ? 'Patching…' : 'Generate patch'}
                    </button>
                    <button
                      type="button"
                      className="cta cta-ghost"
                      disabled={Boolean(busy)}
                      onClick={() => run('validate', () => api.validate(incident.id))}
                    >
                      {busy === 'validate' ? 'Validating…' : 'Validate'}
                    </button>
                    <button
                      type="button"
                      className="cta cta-gold"
                      disabled={Boolean(busy) || !canApprove}
                      onClick={() => run('approve', () => api.approve(incident.id))}
                    >
                      {busy === 'approve' ? 'Saving…' : 'Approve'}
                    </button>
                  </div>
                  {!canApprove ? (
                    <p className="hint">Approval stays disabled until validation passes.</p>
                  ) : null}

                  <label className="reject-row">
                    Rejection reason
                    <div className="field">
                      <input
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                        placeholder="Why this patch should stop here"
                      />
                      <button
                        type="button"
                        disabled={Boolean(busy) || !reason.trim()}
                        onClick={() =>
                          run('reject', () => api.reject(incident.id, reason.trim()))
                        }
                      >
                        {busy === 'reject' ? '…' : 'Reject'}
                      </button>
                    </div>
                  </label>

                  <details>
                    <summary>Stack trace</summary>
                    <pre>{incident.stack_trace || '(empty)'}</pre>
                  </details>

                  <h3>Root-cause analysis</h3>
                  {incident.root_cause_analysis ? (
                    <div className="analysis">
                      <p>{incident.root_cause_analysis.hypothesis}</p>
                      <p>
                        Suspected{' '}
                        <code>{incident.root_cause_analysis.suspected_file ?? '—'}</code> /{' '}
                        <code>{incident.root_cause_analysis.suspected_function ?? '—'}</code>
                        {' · '}
                        confidence {incident.root_cause_analysis.confidence}
                        {' · '}
                        {incident.root_cause_analysis.provider}
                      </p>
                      <p className="hint">{incident.root_cause_analysis.disclaimer}</p>
                      <ul>
                        {incident.root_cause_analysis.recommended_next_steps.map((s) => (
                          <li key={s}>{s}</li>
                        ))}
                      </ul>
                    </div>
                  ) : (
                    <p className="hint">No analysis yet.</p>
                  )}

                  <h3>Proposed patch</h3>
                  {incident.proposed_patch ? (
                    <pre className="diff">{incident.proposed_patch}</pre>
                  ) : (
                    <p className="hint">
                      No patch yet. The original repository is never modified automatically.
                    </p>
                  )}

                  <h3>Validation</h3>
                  {incident.validation_results ? (
                    <div>
                      <p>
                        Overall:{' '}
                        <strong>
                          {incident.validation_results.overall_passed ? 'passed' : 'failed'}
                        </strong>
                      </p>
                      <p className="hint">{incident.validation_results.disclaimer}</p>
                      <ul className="checks">
                        {incident.validation_results.checks.map((c) => (
                          <li key={c.name}>
                            <code>{c.name}</code> · {c.status} — {c.detail}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : (
                    <p className="hint">No validation results yet.</p>
                  )}

                  {incident.approval ? (
                    <p className="thanks">
                      Decision: {incident.approval.decision} by {incident.approval.actor}.{' '}
                      {incident.approval.reason ?? ''}
                    </p>
                  ) : null}

                  <details>
                    <summary>History</summary>
                    <ul className="history">
                      {incident.history.map((h, i) => (
                        <li key={`${h.timestamp}-${i}`}>
                          {h.timestamp} · {h.event} · {h.from_status ?? '∅'} → {h.to_status}
                        </li>
                      ))}
                    </ul>
                  </details>
                </>
              )}
            </section>
          </div>
        </div>
      </main>
    </LuxuryStage>
  )
}
