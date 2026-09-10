from __future__ import annotations

import sqlglot
from sqlglot import expressions as exp


class SQLValidationError(ValueError):
    pass


FORBIDDEN_EXPRESSIONS = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
)


def validate_sql(
    sql: str,
    allowed_table: str,
    allowed_columns: set[str],
) -> str:

    normalized = sql.strip()

    if not normalized:
        raise SQLValidationError(
            "Generated SQL is empty."
        )

    try:
        statements = sqlglot.parse(
            normalized,
            read="duckdb",
        )
    except Exception as exc:

        raise SQLValidationError(
            "SQL could not be parsed."
        ) from exc

    if len(statements) != 1:

        raise SQLValidationError(
            "Multiple SQL statements are not allowed."
        )

    tree = statements[0]

    if not isinstance(tree, exp.Select):

        raise SQLValidationError(
            "Only SELECT queries are allowed."
        )

    for node in tree.walk():

        if isinstance(
            node,
            FORBIDDEN_EXPRESSIONS,
        ):

            raise SQLValidationError(
                "Only read-only SELECT queries are allowed."
            )

    # ----------------------------------
    # Validate physical tables
    # ----------------------------------

    physical_tables = []

    for table in tree.find_all(exp.Table):

        table_name = table.name

        # CTE names are not physical tables.
        if table_name.lower() in {
            cte.alias_or_name.lower()
            for cte in tree.find_all(exp.CTE)
        }:

            continue

        physical_tables.append(
            table_name
        )

    for table_name in physical_tables:

        if table_name.lower() != allowed_table.lower():

            raise SQLValidationError(
                "Query references an unauthorized table."
            )

    # ----------------------------------
    # Validate physical columns
    # ----------------------------------

    aliases = {
        alias.alias
        for alias in tree.find_all(exp.Alias)
        if alias.alias
    }

    for column in tree.find_all(exp.Column):

        column_name = column.name

        if column_name in aliases:
            continue

        if column_name == "*":
            continue

        if column_name not in allowed_columns:

            raise SQLValidationError(
                f"Query references unauthorized "
                f"column: {column_name}"
            )

    return normalized