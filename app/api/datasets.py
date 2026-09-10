from pathlib import Path
from uuid import uuid4

from fastapi import (
    APIRouter,
    File,
    HTTPException,
    UploadFile,
    status,
)

from app.ingestion.loader import (
    load_csv_to_duckdb,
)

from app.ingestion.profiler import (
    profile_csv,
)

from app.ingestion.registry import (
    get_profile_path,
)

from app.ingestion.schema_context import (
    save_dataset_profile,
)

from app.jobs.manager import (
    job_manager,
)

router = APIRouter()


DATA_DIR = Path("data")

DATA_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# Maximum accepted CSV size: 200 MB
MAX_UPLOAD_BYTES = 200 * 1024 * 1024

def process_dataset(
    dataset_id: str,
    csv_path: Path,
    original_filename: str,
):

    # -----------------------------
    # 1. Profile CSV ONCE
    # -----------------------------

    profile = profile_csv(
        csv_path
    )

    # -----------------------------
    # 2. Save profile metadata
    # -----------------------------

    profile_path = get_profile_path(
        dataset_id
    )

    save_dataset_profile(
        dataset_id=dataset_id,
        profile=profile,
        profile_path=profile_path,
    )

    # -----------------------------
    # 3. Load CSV into DuckDB
    # -----------------------------

    db_path, table_name = load_csv_to_duckdb(
        csv_path,
        dataset_id,
    )

    # -----------------------------
    # 4. Return ingestion result
    # -----------------------------

    return {
        "dataset_id": dataset_id,
        "filename": original_filename,
        "rows": profile["row_count"],
        "column_count": profile["column_count"],
        "columns": profile["columns"],
        "duckdb": {
            "path": str(db_path),
            "table": table_name,
        },
        "profile": {
            "path": str(profile_path),
        },
    }
@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_dataset(
    file: UploadFile = File(...),
):

    # -----------------------------
    # Validate filename
    # -----------------------------

    if not file.filename:

        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_FILENAME",
                "message": "A CSV filename is required.",
            },
        )

    # -----------------------------
    # Validate extension
    # -----------------------------

    if Path(file.filename).suffix.lower() != ".csv":

        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_FILE_TYPE",
                "message": "Only CSV files are supported.",
            },
        )

    dataset_id = str(uuid4())

    destination = (
        DATA_DIR / f"{dataset_id}.csv"
    )

    size = 0

    try:

        # --------------------------------
        # Stream upload in 1 MB chunks
        # --------------------------------

        with destination.open("wb") as output:

            while True:

                chunk = await file.read(
                    1024 * 1024
                )

                if not chunk:
                    break

                size += len(chunk)

                # --------------------------------
                # Enforce file-size limit
                # --------------------------------

                if size > MAX_UPLOAD_BYTES:

                    destination.unlink(
                        missing_ok=True
                    )

                    raise HTTPException(
                        status_code=413,
                        detail={
                            "code": "FILE_TOO_LARGE",
                            "message": (
                                "CSV exceeds the "
                                f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit."
                            ),
                        },
                    )

                output.write(chunk)

    except HTTPException:
        raise

    except OSError as exc:

        destination.unlink(
            missing_ok=True
        )

        raise HTTPException(
            status_code=500,
            detail={
                "code": "FILE_STORAGE_ERROR",
                "message": (
                    "The server could not store "
                    "the uploaded CSV."
                ),
            },
        ) from exc

    except Exception as exc:

        destination.unlink(
            missing_ok=True
        )

        raise HTTPException(
            status_code=500,
            detail={
                "code": "UPLOAD_FAILED",
                "message": (
                    "An unexpected error occurred "
                    "while uploading the CSV."
                ),
            },
        ) from exc

    finally:

        await file.close()

    # --------------------------------
    # Start asynchronous processing
    # --------------------------------

    job_id = job_manager.submit(
        process_dataset,
        dataset_id,
        destination,
        file.filename,
    )

    return {
        "job_id": job_id,
        "dataset_id": dataset_id,
        "filename": file.filename,
        "status": "queued",
        "size_bytes": size,
    }