from __future__ import annotations

import threading
import time
from signal_desk.triage import process_one


class JobWorker:
    def __init__(self, poll_seconds: float = 0.2):
        self.poll_seconds = poll_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="signal-desk-worker", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 3.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                did_work = process_one()
            except Exception as exc:
                # Keep the worker alive without logging a payload or user data.
                print(f"Signal Desk worker iteration failed: {type(exc).__name__}")
                did_work = False
            if not did_work:
                self._stop.wait(self.poll_seconds)
