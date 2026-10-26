# SentinelAI console

Vite + React UI for SentinelAI.

```powershell
npm install
npm run dev
```

Set `VITE_API_URL` only if the API is not on `http://127.0.0.1:8000`.

Start the backend first (`uvicorn backend.app.main:app --port 8000`) or the console runs in offline simulation mode.

Demo buttons (backend up): **Simulate incident**, **Break checkout (outage)**, **Break checkout (code bug)**.

Full setup: see the repo root `README.md`.
