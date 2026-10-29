# SentinelAI

AI-assisted incident response for **web services**. Built by **Team TriNova**.

SentinelAI is a **web app** (FastAPI backend + browser dashboard). It sits beside the apps it watches. It is not a desktop agent, and it does not silently rewrite your repo.

This local prototype is a **demo environment**. Mitigation adapters talk to a fake shop control API, not Kubernetes or LaunchDarkly. Say that openly in any pitch.

## Two processes

| Process | What it is | Default port |
| --- | --- | --- |
| **SentinelAI** | Ingestion, triage, patch sandbox, approval, timeline | `8000` |
| **Demo shop** (`victim_app`) | Deliberately breakable checkout | `8001` |

Errors in the shop become incidents in SentinelAI through:

1. **SDK middleware** in the shop (catches exceptions and POSTs `/api/alerts`)
2. **Health checks** (SentinelAI pings shop `/health`)
3. **Logs / context** pulled at triage time
4. **Webhooks** (same `POST /api/alerts` — Sentry/Datadog would use this)

Duplicate alerts with the same fingerprint are grouped into one incident.

```
Shop / webhook / health  →  POST /api/alerts  →  incident store
                                              →  triage verdict
                         Track 1 mitigation (human approves simulated action)
                         Track 2 code fix (patch → tests → replay → human approves)
                                              →  timeline + post-mortem
```

## Requirements

- Python 3.11+
- Node 20+ only if you use the Vite console (`frontend/`)
- Optional: `GEMINI_API_KEY` if `AI_PROVIDER=gemini`

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

macOS / Linux:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Leave `AI_PROVIDER=mock` for an offline demo.

## Run (three terminals)

From the **project root**, with the venv activated.

**1. SentinelAI backend**

```powershell
uvicorn backend.app.main:app --reload --port 8000
```

Health: http://127.0.0.1:8000/health  
API docs: http://127.0.0.1:8000/docs

**2. Demo shop (the app you break)**

```powershell
uvicorn victim_app.main:app --reload --port 8001
```

Shop health: http://127.0.0.1:8001/health

**3. Dashboard** (pick one)

Vite console:

```powershell
cd frontend
npm install
npm run dev
```

Streamlit:

```powershell
streamlit run dashboard/app.py
```

If the backend is down, the Vite console falls back to an offline simulation. Start port `8000` to talk to the real API.

## How to test it (manual demo, ~3 minutes)

1. Start backend + shop + dashboard as above.
2. In the console, click **Break checkout (outage)**. An incident should appear with verdict `dependency_outage` and a **simulated** fallback proposal.
3. Click **Approve**. Error rate on the shop should drop (fallback, no code change).
4. Click **Break checkout (code bug)**. Verdict should be `code_bug`.
5. **Synthesize Patch** → **Run Test Suite** → **Replay request**. You should see before fail / after pass. Original `victim_app/shop.py` stays buggy until a human later chooses to apply a patch outside this tool.
6. **Generate post-mortem**.
7. Optional: `POST http://127.0.0.1:8000/api/eval/run` — expect about **8–10 / 10** classified correctly on the recorded demo set.

### Inject failures yourself

```powershell
curl -X POST http://127.0.0.1:8001/control/inject -H "Content-Type: application/json" -d "{\"mode\":\"payments_outage\"}"
curl -X POST http://127.0.0.1:8001/checkout
```

Modes: `code_bug`, `expired_key`, `payments_outage`, `bad_deploy`, `memory_leak`, `crash`, `none`.

Or from SentinelAI:

```powershell
curl -X POST http://127.0.0.1:8000/api/demo/break -H "Content-Type: application/json" -d "{\"mode\":\"code_bug\"}"
curl -X POST http://127.0.0.1:8000/api/demo/simulate
```

### Advanced: old sample_app loop

Manual form still works for `sample_app` (`add()` returns `-1`):

Analyze → Generate patch → Validate → Approve. `sample_app/buggy_app.py` is never modified by approval.

## Automated tests

```powershell
pytest
ruff check backend victim_app
```

Tests use a temp SQLite file, `AI_PROVIDER=mock`, and `victim_app_url=inline` (no shop server required). They do not need internet or an API key.

Useful subsets:

```powershell
pytest backend/tests/test_ops.py -q
pytest backend/tests/test_workflow.py -q
```

## HTTP surface

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Liveness |
| GET | `/api/events` | SSE live incident feed |
| GET | `/api/metrics` | Counts, categories, time-to-resolution |
| POST | `/api/alerts` | Webhook / SDK ingest (auto-triage) |
| POST | `/api/demo/break` | Inject a shop failure and open an incident |
| POST | `/api/demo/simulate` | Synthetic payments-outage incident |
| POST | `/api/eval/run` | Score the 10 known scenarios |
| POST | `/api/incidents` | Manual ingest (no auto-triage) |
| GET | `/api/incidents` | List |
| GET | `/api/incidents/{id}` | Fetch |
| POST | `/api/incidents/{id}/triage` | Classify + propose track |
| POST | `/api/incidents/{id}/analyze` | Code-level hypothesis |
| POST | `/api/incidents/{id}/generate-patch` | Unified diff in memory only |
| POST | `/api/incidents/{id}/validate` | pytest/ruff in a disposable copy |
| POST | `/api/incidents/{id}/replay` | Captured request before/after in sandbox |
| POST | `/api/incidents/{id}/mitigate` | Propose simulated adapter |
| POST | `/api/incidents/{id}/approve` | Human gate (patch record **or** simulated mitigate) |
| POST | `/api/incidents/{id}/reject` | Human reject |
| POST | `/api/incidents/{id}/postmortem` | Timeline summary |

## Safety (built in)

- Sandbox copies are deleted after validate/replay. The original tree is not written.
- Approval does **not** merge, push, or deploy.
- Captured checkout bodies redact cards, emails, and secret-like keys.
- Every transition is stored on the incident timeline and in `audit_log`.
- Mitigation is **simulated** against the demo shop control API.

## Gemini (optional)

```
AI_PROVIDER=gemini
GEMINI_API_KEY=your-key
GEMINI_MODEL=gemini-2.0-flash
```

If JSON is malformed, triage falls back to the recorded demo rules instead of guessing.

## Honest limits

- Web backends first (APIs). Mobile/desktop would need different SDKs.
- Shop control actions are demo adapters. Real k8s/feature-flag tools would implement the same interface.
- A passing sandbox test is not proof the fix is correct.
- No auth on the local API.

## Security configuration

Local demo defaults are convenient, not safe. Before exposing SentinelAI to anyone else:

1. **Authentication.** Set `API_KEYS=alice=<token>,bob=<token>` in `.env`. Every endpoint except `GET /health` then
   requires `Authorization: Bearer <token>` (or `X-API-Key`). The approver recorded in the audit log is the identity
   attached to the key; names sent in request bodies are ignored. `AUTH_ENABLED=true` without keys refuses to start.
   The live event stream accepts `?access_token=` because browsers cannot set headers on `EventSource`: use a
   dedicated key for it, since query strings may appear in proxy logs.
2. **Isolation.** Validation runs the patched project's tests. With `SANDBOX_MODE=subprocess` that is plain code
   execution on your machine. Build the sandbox image and switch to Docker:

   ```bash
   docker build -f Dockerfile.sandbox -t sentinelai-sandbox:latest .
   # .env: SANDBOX_MODE=docker
   ```

   In Docker mode the code runs with no network, a read-only root filesystem, dropped capabilities and capped
   CPU/memory/processes. If Docker is unavailable SentinelAI refuses to validate rather than falling back to the host.
3. **Demo endpoints.** Set `DEMO_MODE=false` to disable `/api/demo/*` and `/api/eval/run`.
4. **Frontend key.** Never put a real key in `VITE_API_KEY`: it is public in the built bundle. The console asks for the
   key at runtime and keeps it in `sessionStorage`.
