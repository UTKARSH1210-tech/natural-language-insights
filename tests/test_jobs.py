import time

from app.jobs.manager import JobManager


def test_job_completes():

    manager = JobManager(max_workers=2)

    def work():
        return {"value": 42}

    job_id = manager.submit(work)

    # Give the worker a short opportunity to finish.
    for _ in range(50):

        job = manager.get(job_id)

        if job.status == "completed":
            break

        time.sleep(0.01)

    job = manager.get(job_id)

    assert job is not None
    assert job.status == "completed"
    assert job.result == {"value": 42}


def test_job_failure():

    manager = JobManager(max_workers=2)

    def failing_work():
        raise ValueError("Something went wrong")

    job_id = manager.submit(failing_work)

    for _ in range(50):

        job = manager.get(job_id)

        if job.status == "failed":
            break

        time.sleep(0.01)

    job = manager.get(job_id)

    assert job is not None
    assert job.status == "failed"
    assert job.error == "Something went wrong"


def test_unknown_job():

    manager = JobManager()

    job = manager.get("does-not-exist")

    assert job is None