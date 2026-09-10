from pathlib import Path


DATA_DIR = Path("data")
DB_DIR = DATA_DIR / "db"
PROFILE_DIR = DATA_DIR / "profiles"

DATA_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

DB_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

PROFILE_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


def get_dataset_paths(
    dataset_id: str,
) -> tuple[Path, Path]:

    csv_path = DATA_DIR / f"{dataset_id}.csv"

    db_path = DB_DIR / f"{dataset_id}.duckdb"

    return csv_path, db_path


def get_profile_path(
    dataset_id: str,
) -> Path:

    return (
        PROFILE_DIR
        / f"{dataset_id}.json"
    )


def dataset_exists(
    dataset_id: str,
) -> bool:

    csv_path, db_path = get_dataset_paths(
        dataset_id
    )

    return (
        csv_path.exists()
        and db_path.exists()
    )