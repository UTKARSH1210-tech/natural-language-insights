from __future__ import annotations

from pathlib import Path

import duckdb


DB_DIR = Path("data/db")
DB_DIR.mkdir(parents=True, exist_ok=True)


def load_csv_to_duckdb(csv_path: str | Path, dataset_id: str) -> tuple[Path, str]:
    """Materialize an unfamiliar CSV into an isolated DuckDB database."""
    csv_path = Path(csv_path)
    db_path = DB_DIR / f"{dataset_id}.duckdb"
    table_name = "transactions"

    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            f"""
            CREATE OR REPLACE TABLE {table_name} AS
            SELECT * FROM read_csv_auto(?, header=true, sample_size=-1)
            """,
            [str(csv_path)],
        )
    finally:
        con.close()

    return db_path, table_name
