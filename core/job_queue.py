import threading
import queue
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Any


class JobStatus(Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    DONE      = "done"
    ERROR     = "error"
    CANCELLED = "cancelled"


@dataclass
class Job:
    id: str
    name: str
    fn: Callable
    args: tuple
    kwargs: dict
    status: JobStatus = JobStatus.PENDING
    progress: float = 0.0
    result: Any = None
    error: str = ""
    on_done: Callable = None


class JobQueue:
    def __init__(self, max_workers: int = 2):
        self._q: queue.Queue = queue.Queue()
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._update_callbacks: list[Callable] = []
        self._running = True
        for _ in range(max_workers):
            t = threading.Thread(target=self._worker, daemon=True)
            t.start()

    def submit(self, name: str, fn: Callable, *args, on_done: Callable = None, **kwargs) -> str:
        job = Job(
            id=str(uuid.uuid4())[:8],
            name=name,
            fn=fn,
            args=args,
            kwargs=kwargs,
            on_done=on_done,
        )
        with self._lock:
            self._jobs[job.id] = job
        self._q.put(job)
        self._notify()
        return job.id

    def get_jobs(self) -> list:
        with self._lock:
            return list(self._jobs.values())

    def get_job(self, job_id: str):
        with self._lock:
            return self._jobs.get(job_id)

    def clear_finished(self):
        with self._lock:
            finished = {JobStatus.DONE, JobStatus.ERROR, JobStatus.CANCELLED}
            self._jobs = {k: v for k, v in self._jobs.items()
                         if v.status not in finished}
        self._notify()

    def on_update(self, callback: Callable):
        self._update_callbacks.append(callback)

    def _notify(self):
        for cb in self._update_callbacks:
            try:
                cb()
            except Exception:
                pass

    def _worker(self):
        while self._running:
            try:
                job: Job = self._q.get(timeout=1)
            except queue.Empty:
                continue
            job.status = JobStatus.RUNNING
            self._notify()

            def progress_cb(value: float, job=job):
                job.progress = max(0.0, min(1.0, value))
                self._notify()

            try:
                job.result = job.fn(*job.args, progress_cb=progress_cb, **job.kwargs)
                job.status = JobStatus.DONE
                job.progress = 1.0
            except Exception as exc:
                job.status = JobStatus.ERROR
                job.error = str(exc)

            if job.on_done:
                try:
                    job.on_done(job)
                except Exception:
                    pass

            self._notify()
            self._q.task_done()
