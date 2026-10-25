# SentinelAI demo cheat sheet

You need **two servers**: SentinelAI on `:8000` and the demo shop on `:8001`.

```powershell
# terminal 1
uvicorn backend.app.main:app --reload --port 8000

# terminal 2
uvicorn victim_app.main:app --reload --port 8001

# terminal 3
cd frontend
npm run dev
```

## 3-minute script

1. Open the Vite console. Confirm **Backend Operational** (not simulation mode).
2. Click **Break checkout (outage)**. Watch the incident appear with `dependency_outage` and a simulated fallback.
3. Click **Approve & Promote**. Shop checkout should succeed via fallback (no code change).
4. Click **Break checkout (code bug)**.
5. **Synthesize Patch** → **Run Test Suite** → **Replay request**. Expect fail before, pass after. `victim_app/shop.py` on disk stays buggy.
6. **Generate post-mortem**.
7. Optional accuracy check:

```powershell
curl -X POST http://127.0.0.1:8000/api/eval/run
```

## Old sample_app path

Use **New Incident** / Load Sample → Analyze → patch → validate → approve. `sample_app/buggy_app.py` must still contain `left - right`.

## Automated

```powershell
pytest
```
