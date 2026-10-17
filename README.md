# SentinelAI

AI-assisted software incident response and code repair. Built by **Team TriNova**.

This repository is the **initial runnable MVP**: ingest an incident, produce an AI hypothesis, generate a proposed patch, validate that patch in a disposable workspace with real tests, then wait for a human to approve or reject. It does **not** merge, push, deploy, or change the original repository.

This local prototype is **not production-hardened**.

## Architecture

```
incident  →  analyzer  →  patcher  →  validator  →  human approval
                │             │            │
            AI provider   unified diff   pytest/ruff in a temp copy
```

- **FastAPI** serves the workflow (`backend/app`).
- **SQLite** stores incident state (`data/sentinelai.db` by default).
- **Streamlit** is a thin dashboard over the HTTP API.
- **AI providers** sit behind `AIProvider`. `mock` works offline; `gemini` is optional.
- **Orchestrator** owns state transitions. A later LangGraph graph can call the same services without rewriting routes.
- **GitPython** initializes a local baseline in the disposable workspace only. No remotes, commits of patches, or pushes.

### Workflow states

`RECEIVED → ANALYZING → ANALYZED → PATCH_GENERATED → VALIDATING → VALIDATED → APPROVED`

Failure and human-stop states: `FAILED`, `VALIDATION_FAILED`, `REJECTED`.

## Requirements

- Python 3.11+
- Windows PowerShell, macOS, or Linux
- Optional: a Google Gemini API key if you switch `AI_PROVIDER=gemini`

## Setup

```powershell
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

macOS / Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Leave `AI_PROVIDER=mock` for the offline demo. Do not put real keys in git.

## Run the backend

From the project root:

```powershell
uvicorn backend.app.main:app --reload
```

Health check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## Run the dashboard

In a second terminal, with the same virtualenv activated:

```powershell
streamlit run dashboard/app.py
```

The dashboard calls `BACKEND_URL` (default `http://127.0.0.1:8000`). It never receives API keys.

## Demo walkthrough

1. Start backend and dashboard as above.
2. In the dashboard, submit the prefilled sample incident (`sample_app`, `add()` returning `-1`).
3. Click **Analyze**. You should see an AI-generated **hypothesis** (not a verified fact) pointing at `buggy_app.py` / `add`.
4. Click **Generate patch**. A unified diff should change subtraction to addition.
5. Click **Validate**. SentinelAI copies `sample_app` into a temp workspace, applies the patch there, runs pytest (and ruff if installed), then deletes the workspace.
6. After status `VALIDATED`, **Approve** becomes available. **Approve** records the decision only.
7. Confirm `sample_app/buggy_app.py` still contains the original bug.

To try rejection instead, enter a reason and click **Reject** after analysis (or later). Approval stays disabled if validation failed.

## Tests and lint

```powershell
pytest
ruff check .
```

Tests use temporary directories and the mock provider. They do not need internet access or an API key.

## Gemini (optional)

In `.env`:

```
AI_PROVIDER=gemini
GEMINI_API_KEY=your-key
GEMINI_MODEL=gemini-2.0-flash
```

Restart the backend. If the key is missing while `AI_PROVIDER=gemini`, the process fails closed rather than silently pretending to succeed.

## Security notes (prototype)

- Credentials live in `.env`, which is gitignored. `.env.example` has placeholders only.
- Patch application is restricted to a disposable workspace. Path traversal and writes outside that workspace are rejected.
- Tests run with subprocess argument lists (`shell=False`), timeouts, and captured output.
- The model cannot choose arbitrary shell commands.
- Nothing is committed, pushed, merged, or deployed automatically.
- Incident text and repository files are treated as untrusted input.
- The dashboard cannot approve a patch that failed validation.

## Known limitations and next steps

- No GitHub pull-request integration yet (approval is a recorded decision).
- LangGraph is not included; the orchestrator is the insertion point.
- Mock provider only has a precise diagnosis/patch for the sample `add()` bug.
- Gemini JSON parsing is best-effort; malformed replies fail the step instead of storing fake success.
- Single-process SQLite is enough for a local demo, not for multi-instance production.
- No authentication on the API.
- Validation passing is **not** a proof that a fix is correct.

Reasonable next steps: GitHub PR service after approval, LangGraph workflow graph, auth, richer context gathering, and sandboxing beyond a temp directory.

## HTTP surface

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Liveness and provider name |
| POST | `/api/incidents` | Ingest an incident |
| GET | `/api/incidents` | List incidents |
| GET | `/api/incidents/{id}` | Fetch one incident |
| POST | `/api/incidents/{id}/analyze` | Root-cause hypothesis |
| POST | `/api/incidents/{id}/generate-patch` | Store a proposed diff |
| POST | `/api/incidents/{id}/validate` | Test the diff in a temp copy |
| POST | `/api/incidents/{id}/approve` | Human approve (no merge) |
| POST | `/api/incidents/{id}/reject` | Human reject with a reason |
