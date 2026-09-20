"""Job scheduling for Buster OS.

A lightweight scheduler running on a single worker thread. Jobs may be
one-shot ``run_at`` tasks or periodic ``every`` tasks, with priority
ordering and cancellation support.
"""

import heapq
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

JobFunc = Callable[["Job"], None]


class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class Job:
    name: str
    func: JobFunc
    run_at: float
    interval: Optional[float] = None
    priority: int = 0
    status: JobStatus = JobStatus.PENDING
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    result: object = None
    error: Optional[BaseException] = None

    @property
    def periodic(self) -> bool:
        return self.interval is not None and self.interval > 0


class Scheduler:
    """Priority-ordered, single-threaded background scheduler."""

    def __init__(self):
        self._heap: list = []
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._running = False
        self._wake = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.logger = logging.getLogger("buster.kernel.scheduler")

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop, name="scheduler", daemon=True
        )
        self._thread.start()
        self.logger.info("Scheduler started.")

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self.logger.info("Scheduler stopped.")

    def _push(self, job: Job) -> None:
        with self._lock:
            heapq.heappush(self._heap, (job.run_at, job.priority, job.id, job))
            self._jobs[job.id] = job
        self._wake.set()

    def schedule(self, name: str, func: JobFunc, delay: float = 0.0,
                 every: Optional[float] = None, priority: int = 0) -> Job:
        job = Job(
            name=name,
            func=func,
            run_at=time.monotonic() + max(0.0, delay),
            interval=every,
            priority=priority,
        )
        self._push(job)
        return job

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.status is not JobStatus.PENDING:
                return False
            job.status = JobStatus.CANCELLED
        self._wake.set()
        return True

    def remove(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.pop(job_id, None)

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self, status: Optional[JobStatus] = None) -> list[Job]:
        with self._lock:
            jobs = list(self._jobs.values())
        if status is not None:
            jobs = [j for j in jobs if j.status is status]
        jobs.sort(key=lambda j: j.run_at)
        return jobs

    @property
    def running(self) -> bool:
        return self._running

    def _run_loop(self) -> None:
        while self._running:
            with self._lock:
                while self._heap and self._heap[0][3].status is not JobStatus.PENDING:
                    _, _, _, expired = heapq.heappop(self._heap)
                    self._jobs.pop(expired.id, None)
                due = self._heap[0][0] - time.monotonic() if self._heap else None

            if due is None:
                self._wake.wait(timeout=0.5)
            elif due > 0:
                self._wake.wait(timeout=min(due, 0.5))
            else:
                self._execute()

    def _execute(self) -> None:
        with self._lock:
            if not self._heap:
                return
            _, _, _, job = heapq.heappop(self._heap)
        if job.status is not JobStatus.PENDING:
            return

        job.status = JobStatus.RUNNING
        self.logger.debug("Running job '%s'", job.name)
        try:
            job.func(job)
            job.status = JobStatus.COMPLETED
        except Exception as exc:  # noqa: BLE001
            job.error = exc
            job.status = JobStatus.FAILED
            self.logger.exception("Job '%s' failed", job.name)

        if job.periodic and job.status is not JobStatus.CANCELLED:
            job.run_at = time.monotonic() + job.interval
            job.status = JobStatus.PENDING
            job.error = None
            with self._lock:
                heapq.heappush(self._heap, (job.run_at, job.priority, job.id, job))
                self._jobs[job.id] = job