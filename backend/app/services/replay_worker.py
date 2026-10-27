"""Dispatch one captured HTTP request against the shop in cwd.

Run with cwd set to a sandbox copy of victim_app. Does not import the host backend.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    spec_path = Path(sys.argv[1])
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    cwd = str(Path.cwd())
    if cwd not in sys.path:
        sys.path.insert(0, cwd)
    try:
        from main import app
    except ImportError:
        from victim_app.main import app  # type: ignore[no-redef]

    from fastapi.testclient import TestClient

    client = TestClient(app)
    inject = spec.get("inject")
    if inject and inject != "none":
        client.post("/control/inject", json={"mode": inject})
    method = str(spec.get("method") or "POST").upper()
    path = str(spec.get("path") or "/checkout")
    payload = spec.get("json")
    response = client.request(method, path, json=payload)
    json.dump(
        {"status_code": int(response.status_code), "text": (response.text or "")[:4000]},
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
