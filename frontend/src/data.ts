export const navLinks = [
  { href: '#about', label: 'About' },
  { href: '#solution', label: 'Solution' },
  { href: '#case-study', label: 'Case Study' },
  { href: '#blog', label: 'Blog' },
]

export const logos = ['FastAPI', 'SQLite', 'pytest', 'Gemini optional', 'React', 'Streamlit']

export const benefits = [
  {
    tag: '(ingest)',
    num: '01',
    title: 'Incident Intake',
    body: 'Drop in an error, stack trace, and repo path. SentinelAI records the incident and starts a controlled repair workflow — nothing is written to your original code yet.',
  },
  {
    tag: '(analysis)',
    num: '02',
    title: 'Hypothesis & Patch',
    body: 'The analyzer produces a root-cause hypothesis, then the patcher proposes a unified diff. Every claim is labeled as AI output, not verified fact.',
  },
  {
    tag: '(guardrail)',
    num: '03',
    title: 'Validate, Then Decide',
    body: 'Patches run in a disposable workspace with real tests. Approve records a human decision. Reject stops the workflow. The source repo is never merged or pushed.',
  },
]

export const services = [
  { title: 'Incident Ingest', tags: ['API', 'SQLite'] },
  { title: 'AI Analysis', tags: ['Mock', 'Gemini'] },
  { title: 'Safe Validation', tags: ['pytest', 'ruff'] },
]

export const testimonials = [
  {
    quote:
      'Triage classifies from logs, stack traces, and shop telemetry. It does not read the demo injector’s failure_mode label.',
    name: 'Observable triage',
    role: 'No answer-key shortcuts',
    img: '',
  },
  {
    quote:
      'Replay dispatches the captured checkout HTTP payload against an unpatched copy, then against a patched sandbox, and compares status codes.',
    name: 'Captured-request replay',
    role: 'Before vs after, real HTTP',
    img: '',
  },
  {
    quote:
      'Approve is a recorded decision, not a merge. Patches run in a scrubbed subprocess. The original repository is never written.',
    name: 'Human gate',
    role: 'Sandbox + sign-off',
    img: '',
  },
]

export const processSteps = [
  {
    id: '01',
    label: 'Ingest',
    kicker: 'Receive · Record',
    body: 'Submit a title, error message, stack trace, and optional repository path. The incident is stored as RECEIVED. No files are modified.',
  },
  {
    id: '02',
    label: 'Analyze',
    kicker: 'Hypothesis · Context',
    body: 'The analyzer reads nearby source and asks the AI provider for a root-cause hypothesis, suspected file, and next steps. Output is labeled as unverified.',
  },
  {
    id: '03',
    label: 'Patch',
    kicker: 'Diff · Proposal',
    body: 'The patcher returns a unified diff. It is stored on the incident only. The original tree stays untouched until a human later chooses what to do with it.',
  },
  {
    id: '04',
    label: 'Validate',
    kicker: 'Sandbox · Tests',
    body: 'A disposable copy of the repo receives the patch. pytest (and ruff if present) run with timeouts. The workspace is deleted. Then a human may approve or reject.',
  },
]

export const posts = [
  {
    date: 'October 2026',
    tag: 'Workflow',
    title: 'From incident to human gate',
    body: 'Ingest, analyze, generate a patch, validate in a temp workspace, then wait. SentinelAI stops before merge, push, or deploy.',
  },
  {
    date: 'October 2026',
    tag: 'Safety',
    title: 'Why the original repo never changes',
    body: 'Path traversal is rejected, tests run with argument lists, and approval is a decision record — not an automatic git write.',
  },
]

export const monthlyPlans = [
  {
    name: 'Starter Plan',
    desc: 'Local MVP with the mock provider',
    price: 0,
    features: [
      'Incident ingest API',
      'Mock AI diagnosis for sample_app',
      'Unified diff proposals',
      'pytest in a temp workspace',
      'Human approve / reject',
      'SQLite incident store',
      'No merge or push',
      'Offline demo path',
    ],
  },
  {
    name: 'Growth Plan',
    desc: 'Same workflow, Gemini when configured',
    price: 0,
    featured: true,
    features: [
      'All Starter workflow steps',
      'Optional Gemini provider',
      'Source-context gathering',
      'Validation disclaimers',
      'Status history trail',
      'CORS for this console',
      'Streamlit dashboard still works',
      'Keys stay in .env',
    ],
  },
]

export const faqs = [
  {
    q: 'Does SentinelAI change my repository?',
    a: 'No. Patches are applied only inside a disposable workspace that is deleted after tests. Approve records a human decision. Nothing is committed, pushed, merged, or deployed.',
  },
  {
    q: 'How do I run the backend this UI talks to?',
    a: 'From the project root: uvicorn backend.app.main:app --reload. This Vite app proxies /api and /health to http://127.0.0.1:8000.',
  },
  {
    q: 'What is the sample incident for?',
    a: 'sample_app has a buggy add() that returns -1. The mock provider diagnoses that case and proposes changing subtraction to addition so you can walk the full loop offline.',
  },
  {
    q: 'When can I approve a patch?',
    a: 'Approve is enabled only after status is VALIDATED and the validation run passed. Failed validation keeps approval locked. You can still reject with a reason.',
  },
  {
    q: 'Is passing validation proof the fix is correct?',
    a: 'No. A green test run does not guarantee the change is complete, safe, or correct. A human still has to read the hypothesis and the diff.',
  },
]

export const sampleIncident = {
  title: 'Sample: add() returns the wrong result',
  error_message: 'AssertionError: assert add(2, 3) == 5  (got -1)',
  stack_trace: 'File "test_buggy_app.py", line 5, in test_add\n    assert add(2, 3) == 5',
  repository_path: 'sample_app',
}

export const workflow = [
  'Detected',
  'Triaged',
  'Action ready',
  'Verified',
  'Approved',
] as const
