"""The in-process job queue (ADR-005 §3.3–3.4) — concurrency cap, backpressure, graceful
drain, health. Synchronised with threading.Event so the assertions are deterministic, not timed."""

from __future__ import annotations

import threading

import pytest

from cortex_runtime.job_queue import InProcessJobQueue, QueueFull


def test_jobs_are_processed():
    seen, done = [], threading.Event()
    lock = threading.Lock()

    def handler(job):
        with lock:
            seen.append(job["n"])
        if len(seen) == 3:
            done.set()

    q = InProcessJobQueue(handler, max_workers=2)
    q.start()
    for n in range(3):
        q.submit({"n": n})
    assert done.wait(timeout=5)
    q.shutdown()
    assert sorted(seen) == [0, 1, 2]
    assert q.stats()["processed"] == 3


def test_concurrency_cap_is_enforced():
    # 2 workers, 4 jobs that all block on the same gate → at most 2 run at once.
    gate = threading.Event()
    started = threading.Semaphore(0)
    peak = {"v": 0, "cur": 0}
    lock = threading.Lock()

    def handler(job):
        with lock:
            peak["cur"] += 1
            peak["v"] = max(peak["v"], peak["cur"])
        started.release()
        gate.wait(timeout=5)
        with lock:
            peak["cur"] -= 1

    q = InProcessJobQueue(handler, max_workers=2, max_pending=10)
    q.start()
    for n in range(4):
        q.submit({"n": n})
    started.acquire(timeout=5)         # wait until the first two are running
    started.acquire(timeout=5)
    assert q.stats()["active"] == 2    # exactly the cap, never more
    gate.set()
    q.shutdown()
    assert peak["v"] == 2              # peak concurrency never exceeded the worker count


def test_backpressure_raises_queue_full():
    picked_up, release = threading.Event(), threading.Event()

    def handler(job):
        picked_up.set()
        release.wait(timeout=5)

    q = InProcessJobQueue(handler, max_workers=1, max_pending=1)
    q.start()
    q.submit({"n": 1})                 # taken by the single worker
    assert picked_up.wait(timeout=5)
    q.submit({"n": 2})                 # fills the 1-slot pending queue
    with pytest.raises(QueueFull):
        q.submit({"n": 3})             # no room → backpressure
    release.set()
    q.shutdown()


def test_handler_exception_does_not_kill_worker():
    ran = []

    def handler(job):
        if job["n"] == 0:
            raise RuntimeError("boom")
        ran.append(job["n"])

    q = InProcessJobQueue(handler, max_workers=1)
    q.start()
    q.submit({"n": 0})                 # raises inside the worker
    q.submit({"n": 1})                 # must still be processed by the same (surviving) worker
    q.shutdown()
    assert ran == [1]
    assert q.stats() == {**q.stats(), "failed": 1, "processed": 1}


def test_health_and_lifecycle():
    q = InProcessJobQueue(lambda job: None, max_workers=1)
    assert q.healthy() is False        # not started
    q.start()
    assert q.healthy() is True
    q.shutdown()
    assert q.healthy() is False        # drained + stopped

    with pytest.raises(RuntimeError):
        q.submit({"n": 1})             # submit after shutdown
