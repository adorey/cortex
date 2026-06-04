"""Async execution — the job queue boundary (ADR-005 §2.2, §3.4).

`POST /run` accepts (202) and **enqueues**; a worker executes the run off the request thread.
This module is the queue + worker, behind a small interface so the backend is swappable (the
SecretProvider / StateStore discipline): an **in-process** backend for a single node now, a
**broker** (RabbitMQ) backend for multi-node later (ADR-005 §2.2).

A job is a **plain dict** (serializable) and the queue is built with a ``handler(job)`` — so
the same contract maps onto a broker: in-process the handler runs in a worker thread; with a
broker it runs in a worker process consuming the same payloads. Threads (not asyncio) because
a run is blocking (CLI subprocess / model call) — the cap bounds how many block at once.

It carries three ADR-005 resilience guards:
  • **concurrency cap** — at most ``max_workers`` runs execute at once (§3.3);
  • **backpressure** — a bounded pending queue; a full queue raises :class:`QueueFull` → 429 (§3.3);
  • **graceful shutdown** — :meth:`shutdown` drains in-flight work on SIGTERM (§2.5).
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Any, Callable, Dict, Protocol

logger = logging.getLogger("cortex_runtime.job_queue")

Job = Dict[str, Any]
JobHandler = Callable[[Job], None]

_SENTINEL = object()   # tells a worker thread to exit


class QueueFull(Exception):
    """Raised by :meth:`JobQueue.submit` when the pending queue is at capacity (backpressure)."""


class JobQueue(Protocol):
    def start(self) -> None: ...
    def submit(self, job: Job) -> None: ...        # raises QueueFull under backpressure
    def shutdown(self, *, drain: bool = True, timeout: float = 30.0) -> None: ...
    def healthy(self) -> bool: ...
    def stats(self) -> Dict[str, int]: ...


class InProcessJobQueue:
    """Single-node backend: a bounded queue drained by a fixed pool of daemon worker threads.

    ``max_workers`` is the concurrency cap; ``max_pending`` bounds the waiting queue (0 ⇒
    unbounded). A handler exception is logged and counted but never kills its worker."""

    def __init__(self, handler: JobHandler, *, max_workers: int = 4, max_pending: int = 100):
        self._handler = handler
        self._max_workers = max(1, max_workers)
        self._q: "queue.Queue" = queue.Queue(maxsize=max_pending)
        self._threads: list[threading.Thread] = []
        self._started = False
        self._lock = threading.Lock()
        self._active = 0
        self._processed = 0
        self._failed = 0

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        for i in range(self._max_workers):
            t = threading.Thread(target=self._worker, name=f"cortex-worker-{i}", daemon=True)
            t.start()
            self._threads.append(t)

    def submit(self, job: Job) -> None:
        if not self._started:
            raise RuntimeError("job queue not started")
        try:
            self._q.put_nowait(job)
        except queue.Full:
            raise QueueFull("job queue at capacity")

    def shutdown(self, *, drain: bool = True, timeout: float = 30.0) -> None:
        if not self._started:
            return
        if drain:
            self._q.join()                 # wait until every queued job is processed
        for _ in self._threads:
            self._q.put(_SENTINEL)         # one poison pill per worker
        for t in self._threads:
            t.join(timeout=timeout)
        self._threads.clear()
        self._started = False

    def healthy(self) -> bool:
        return self._started and all(t.is_alive() for t in self._threads)

    def stats(self) -> Dict[str, int]:
        with self._lock:
            return {"pending": self._q.qsize(), "active": self._active,
                    "processed": self._processed, "failed": self._failed,
                    "workers": len(self._threads)}

    # — worker loop ————————————————————————————————————————————————————————————————————
    def _worker(self) -> None:
        while True:
            job = self._q.get()
            if job is _SENTINEL:
                self._q.task_done()
                return
            with self._lock:
                self._active += 1
            try:
                self._handler(job)
                with self._lock:
                    self._processed += 1
            except Exception:               # a bad job must not kill the worker
                with self._lock:
                    self._failed += 1
                logger.exception("job handler failed for job=%s", job.get("run_id"))
            finally:
                with self._lock:
                    self._active -= 1
                self._q.task_done()
