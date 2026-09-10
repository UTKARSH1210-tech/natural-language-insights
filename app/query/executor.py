from __future__ import annotations

from pathlib import Path

import duckdb


def execute_query(
    db_path: Path,
    sql: str,
) -> dict:

    connection = duckdb.connect(
        str(db_path)
    )

    try:

        result = connection.execute(
            sql
        )

        columns = [
            description[0]
            for description in result.description
        ]

        rows = result.fetchall()

        data = [
            dict(
                zip(columns, row)
            )
            for row in rows
        ]

        return {
            "columns": columns,
            "rows": data,
            "row_count": len(data),
        }

    finally:

        connection.close()