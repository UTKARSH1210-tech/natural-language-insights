from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb


def _semantic_role(
    name: str,
    logical_type: str,
    distinct_count: int,
    row_count: int,
) -> str:
    """Conservative, explainable heuristic for semantic profiling."""
    normalized = name.lower().replace("-", "_").replace(" ", "_")

    date_tokens = (
        "date",
        "time",
        "timestamp",
        "day",
        "month",
        "year",
        "quarter",
    )

    id_tokens = (
        "id",
        "code",
        "number",
        "no",
        "sku",
        "invoice",
    )

    if any(token in normalized for token in date_tokens):
        return "date_or_time"

    if logical_type.upper() == "DATE":
        return "date_or_time"

    if any(token in normalized.split("_") for token in id_tokens):
        return "identifier"

    numeric_types = {
        "INTEGER",
        "BIGINT",
        "SMALLINT",
        "TINYINT",
        "HUGEINT",
        "DOUBLE",
        "FLOAT",
        "DECIMAL",
        "REAL",
    }

    if any(logical_type.upper().startswith(t) for t in numeric_types):
        return "numeric_measure"

    if row_count > 0 and distinct_count / row_count < 0.05:
        return "categorical"

    return "text_or_other"


def profile_csv(path: str | Path) -> dict[str, Any]:
    """
    Profile an arbitrary CSV using DuckDB.

    Nothing about the sample Online Retail dataset is hardcoded here.
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(path)

    con = duckdb.connect()

    try:
        relation = con.sql(
            """
            SELECT *
            FROM read_csv_auto(
                ?,
                header=true,
                sample_size=-1
            )
            """,
            params=[str(path)],
        )

        description = relation.description
        row_count = relation.shape[0]

        columns = []

        for column in description:
            name = column[0]
            logical_type = str(column[1])

            # The column name is an identifier, so it cannot be passed as
            # a normal SQL parameter. DuckDB's quote_identifier() isn't
            # available consistently across versions, so quote it safely.
            escaped_name = '"' + name.replace('"', '""') + '"'

            stats_query = f"""
                SELECT
                    COUNT(*) AS row_count,
                    COUNT(DISTINCT CAST({escaped_name} AS VARCHAR))
                        AS distinct_count,
                    SUM(
                        CASE
                            WHEN {escaped_name} IS NULL THEN 1
                            ELSE 0
                        END
                    ) AS null_count
                FROM read_csv_auto(
                    ?,
                    header=true,
                    sample_size=-1
                )
            """

            stats = con.execute(
                stats_query,
                [str(path)],
            ).fetchone()

            _, distinct_count, null_count = stats

            distinct_count = distinct_count or 0
            null_count = null_count or 0

            role = _semantic_role(
                name=name,
                logical_type=logical_type,
                distinct_count=distinct_count,
                row_count=row_count,
            )

            columns.append(
                {
                    "name": name,
                    "type": logical_type,
                    "role": role,
                    "distinct_count": distinct_count,
                    "null_count": null_count,
                }
            )

        return {
            "row_count": row_count,
            "column_count": len(columns),
            "columns": columns,
        }

    finally:
        con.close()