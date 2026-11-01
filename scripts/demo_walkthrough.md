# SentinelAI: Live Demo Walkthrough

A practical, step-by-step walkthrough for running and demonstrating the SentinelAI prototype end-to-end.

---

## 1. Setup & Starting Services

Run each component in a separate terminal from `d:\SentinalAi` with your environment active:

### Terminal 1: SentinelAI Backend (Port 8000)
```powershell
uvicorn backend.app.main:app --reload --port 8000
```
* **Health Endpoint:** [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
* **Interactive API Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Terminal 2: Demo Shop / Victim App (Port 8001)
```powershell
uvicorn victim_app.main:app --reload --port 8001
```
* **Shop Health:** [http://127.0.0.1:8001/health](http://127.0.0.1:8001/health)

### Terminal 3: Vite Console (Port 5173)
```powershell
cd frontend
npm run dev
```
* **Dashboard URL:** [http://localhost:5173](http://localhost:5173)

---

## 2. Interactive Walkthrough (~3–5 Minutes)

### Step 1: Health & Console Overview
1. Open [http://localhost:5173](http://localhost:5173).
2. The landing page shows the core architecture guarantees: **Sandbox pytest**, **HTTP replay**, and **Human sign-off**.
3. Click **Open Console** (or scroll to `#console`).
4. Verify the status chip in the top right reads **"Backend live · mock · db ready"**.

---

### Step 2: Track 1 — Infrastructure Outage & Mitigation (No Code Change)
1. In the sidebar under **Demo shop**, click the **`Outage`** button.
2. An incident titled `Break checkout: payments_outage` immediately appears in the queue.
3. Review the **Triage** card:
   * **Category:** `dependency outage` (Confidence ~84%).
   * **Recommended Track:** `mitigation · fallback`.
   * **Evidence:** Cites payment gateway timeouts and circuit breaker status from telemetry.
4. Review the **Mitigation (simulated)** card:
   * SentinelAI proposes switching the checkout service to cash-on-delivery fallback.
   * Probes the live shop baseline error rate (`1.0`).
5. Click the green **`Approve`** button at the bottom.
6. The status changes to **`MITIGATED`**.
   * Detail confirms: `Probe error rate 1.0 → 0.0. Recovered=True`.
   * **Key Point:** Resolved entirely without touching or rewriting any source code.

---

### Step 3: Track 2 — Application Code Bug, Hardened Sandbox & HTTP Replay
1. In the sidebar under **Demo shop**, click **`Code bug`**.
2. An incident titled `Break checkout: code_bug` is ingested.
3. Click **`Triage`**:
   * Evaluates the real exception traceback (`TypeError: 'NoneType' object is not subscriptable` in `_line_total`).
   * Verdict: `code bug` → Recommended Track: `code fix` (`patch`).
4. Click **`Diagnose`** (or select the **Root cause** tab):
   * Hypothesis pinpoints `shop.py` -> `_line_total` indexing a null line item without a guard.
5. Click **`Patch`** (or select the **Patch** tab):
   * Displays a clean unified diff generated from the current source:
     ```diff
     +    if item is None:
     +        return 0
          return int(item["price"]) * int(item["qty"])
     ```
6. Click **`Tests`** (or select the **Checks** tab):
   * Applies the patch in a **disposable sandbox copy** and runs `pytest` and `ruff`.
   * **Sandbox Security:** Host environment secrets (`GEMINI_API_KEY`, cloud credentials) are scrubbed via `_ALLOWED_ENV`, outbound networking is blocked via loopback proxy null-routes, and CPU/memory limits are enforced.
   * All checks pass. The original file `victim_app/shop.py` remains completely untouched on disk.
7. Click **`Replay`**:
   * Review the Replay card: `Before failed (HTTP 500) → after passed (HTTP 200)`.
   * SentinelAI spins up an unpatched instance and a patched sandbox instance, sending the actual captured checkout HTTP request to verify the fix works under real traffic.
8. The **`Approve`** button unlocks. Click **`Approve`** to record the sign-off.

---

### Step 4: Post-Mortem & Audit Trail
1. Click **`Report`** at the bottom.
2. The **Post-mortem** card generates an executive summary, root cause statement, and timeline.
3. Scroll down and expand the **Timeline** accordion:
   * View the complete, immutable state-machine audit log:
     `INGESTED` → `TRIAGED` → `PATCH_GENERATED` → `VALIDATED` → `PATCH_VERIFIED` → `APPROVED`.

---

### Step 5: Benchmark Evaluation Suite
To demonstrate that triage is general and not circular:
1. In any terminal, execute the evaluation endpoint:
   ```powershell
   curl -X POST http://127.0.0.1:8000/api/eval/run
   ```
2. The harness tests **10 realistic incident scenarios**, including paraphrased alerts, messy log messages, and ambiguous brownouts where the confidence gate correctly triggers human escalation.
3. Expected output: `10 out of 10 passed`.

---

## 3. Alternative Ingestion Methods

### Direct Failure Injection via CLI
You can simulate external alerts by breaking the shop directly via HTTP:
```powershell
# 1. Inject an outage into the shop
curl -X POST http://127.0.0.1:8001/control/inject -H "Content-Type: application/json" -d "{\"mode\":\"payments_outage\"}"

# 2. Trigger a checkout attempt (shop SDK catches the error and reports it to SentinelAI)
curl -X POST http://127.0.0.1:8001/checkout

# Available failure modes:
# none | code_bug | expired_key | payments_outage | bad_deploy | memory_leak | crash
```

### Manual Incident Intake
1. In the console, click **New incident**.
2. Click **Load Sample Scenario** to load the `sample_app` arithmetic bug (`add()` returns subtraction instead of addition).
3. Click **Synthesize Diff & Validate** to run the diagnosis, diff generation, and test suite on a custom codebase.

---

## 4. Key Architecture & Defensibility Highlights

* **No Answer-Key Cheating:** Triage strips injector labels (`failure_mode`) and purges injector logs before analyzing telemetry. Verdicts rely strictly on HTTP status codes, tracebacks, health metrics, and deploy diffs.
* **True Request Replay:** Replay uses `replay_worker.py` and `FastAPI.testclient.TestClient` to dispatch the actual captured HTTP request against unpatched vs patched environments.
* **Strict Sandbox Isolation:** Subprocess workspaces are wiped after validation. Environment variables are scrubbed of all host secrets and credentials.
* **Human-in-the-Loop Gate:** The system never automatically merges, pushes, or deploys to Git. Approval records an auditable decision on the incident timeline.
