from fastapi import APIRouter, HTTPException

from app.jobs.manager import job_manager


router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
)


@router.get("/{job_id}")
def get_job(job_id: str):

    job = job_manager.get(job_id)

    if job is None:

        raise HTTPException(
            status_code=404,
            detail={
                "code": "JOB_NOT_FOUND",
                "message": "Job not found.",
            },
        )

    response = {
        "job_id": job.job_id,
        "status": job.status,
    }

    if job.status == "completed":

        response["result"] = job.result

    elif job.status == "failed":

        response["error"] = {
            "code": "JOB_FAILED",
            "message": job.error,
        }

    return response