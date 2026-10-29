"""Ping the demo shop /health. If it stays down, open an incident."""

from __future__ import annotations

import logging
import threading

import httpx

from backend.app.models.schemas import AlertCreate

LOGGER = logging.getLogger("sentinelai.health")


class HealthWatcher:
    def __init__(self, container) -> None:
        self.container = container
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._fails = 0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, name="health-watcher", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        settings = self.container.settings
        while not self._stop.wait(settings.health_check_interval):
            try:
                self.container.orchestrator.recover_stuck_incidents(settings.stuck_timeout_seconds)
            except Exception:
                LOGGER.exception("Stuck-incident sweep failed")
            url = settings.victim_app_url.rstrip("/")
            if url == "inline":
                continue
            try:
                response = httpx.get(f"{url}/health", timeout=2.0)
                ok = response.status_code == 200
            except httpx.HTTPError:
                ok = False
            if ok:
                self._fails = 0
                continue
            self._fails += 1
            if self._fails < settings.health_fail_threshold:
                continue
            LOGGER.warning("Shop health failed %s times; opening incident", self._fails)
            try:
                self.container.incidents.ingest_alert(
                    AlertCreate(
                        source="health_check",
                        service="checkout",
                        title="Shop health checks failing",
                        error_message="Shop /health did not respond successfully several times in a row",
                        stack_trace="",
                        endpoint="/health",
                        status_code=503,
                        logs=["health checker: consecutive failures"],
                        fingerprint="health:checkout:down",
                    )
                )
            except Exception:
                LOGGER.exception("Failed to ingest health incident")
            self._fails = 0
