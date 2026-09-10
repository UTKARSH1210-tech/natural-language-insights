from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from threading import Lock
from typing import Any, Callable
from uuid import uuid4


@dataclass
class Job:
    job_id: str
    status: str
    result: Any = None
    error: str | None = None


class JobManager:

    def __init__(self, max_workers: int = 4):

        self.executor = ThreadPoolExecutor(
            max_workers=max_workers
        )

        self.jobs: dict[str, Job] = {}

        self.lock = Lock()

    def submit(
        self,
        function: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> str:

        job_id = str(uuid4())

        with self.lock:

            self.jobs[job_id] = Job(
                job_id=job_id,
                status="queued",
            )

        self.executor.submit(
            self._run_job,
            job_id,
            function,
            *args,
            **kwargs,
        )

        return job_id

    def _run_job(
        self,
        job_id: str,
        function: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ):

        with self.lock:

            self.jobs[job_id].status = "running"

        try:

            result = function(
                *args,
                **kwargs,
            )

            with self.lock:

                self.jobs[job_id].status = "completed"
                self.jobs[job_id].result = result

        except Exception as exc:

            with self.lock:

                self.jobs[job_id].status = "failed"
                self.jobs[job_id].error = str(exc)

    def get(
        self,
        job_id: str,
    ) -> Job | None:

        with self.lock:

            return self.jobs.get(job_id)


job_manager = JobManager(
    max_workers=4
)