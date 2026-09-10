from pathlib import Path

import duckdb

from app.ingestion.loader import load_csv_to_duckdb


def test_load_csv_to_duckdb(tmp_path: Path):
    csv = tmp_path / "sales.csv"
    csv.write_text(
        "product,quantity,revenue\n"
        "A,2,10\n"
        "B,3,20\n",
        encoding="utf-8",
    )

    db_path, table = load_csv_to_duckdb(csv, "test-dataset")

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        revenue = con.execute(f"SELECT SUM(revenue) FROM {table}").fetchone()[0]
    finally:
        con.close()

    assert count == 2
    assert revenue == 30
