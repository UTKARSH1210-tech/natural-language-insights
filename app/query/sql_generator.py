from __future__ import annotations

from app.query.planner import QueryPlan


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def validate_column(column: str | None, allowed_columns: set[str], label: str):
    if column is None:
        raise ValueError(f"{label} is required.")

    if column not in allowed_columns:
        raise ValueError(f"Invalid {label}: {column}")


def generate_frequency_sql(
    plan: QueryPlan,
    table_name: str,
    columns: list[str],
) -> str:

    allowed_columns = set(columns)

    validate_column(
        plan.customer_column,
        allowed_columns,
        "customer column",
    )

    customer = quote_identifier(plan.customer_column)
    table = quote_identifier(table_name)

    if plan.order_column:
        validate_column(
            plan.order_column,
            allowed_columns,
            "order column",
        )

        order = quote_identifier(plan.order_column)

        return f"""
SELECT
    {customer}
FROM {table}
GROUP BY {customer}
HAVING COUNT(DISTINCT {order}) = 1
ORDER BY {customer};
""".strip()

    return f"""
SELECT
    {customer}
FROM {table}
GROUP BY {customer}
HAVING COUNT(*) = 1
ORDER BY {customer};
""".strip()


def generate_revenue_share_sql(
    plan: QueryPlan,
    table_name: str,
    columns: list[str],
) -> str:

    allowed_columns = set(columns)

    validate_column(
        plan.customer_column,
        allowed_columns,
        "customer column",
    )

    validate_column(
        plan.measure_column,
        allowed_columns,
        "revenue measure column",
    )

    customer = quote_identifier(plan.customer_column)
    revenue = quote_identifier(plan.measure_column)
    table = quote_identifier(table_name)

    if plan.order_column:

        validate_column(
            plan.order_column,
            allowed_columns,
            "order column",
        )

        order = quote_identifier(plan.order_column)

        return f"""
WITH customer_orders AS (
    SELECT
        {customer},
        COUNT(DISTINCT {order}) AS order_count
    FROM {table}
    GROUP BY {customer}
),

one_time_revenue AS (
    SELECT
        COALESCE(SUM(t.{revenue}), 0) AS revenue
    FROM {table} t
    INNER JOIN customer_orders c
        ON t.{customer} = c.{customer}
    WHERE c.order_count = 1
),

total_revenue AS (
    SELECT
        COALESCE(SUM({revenue}), 0) AS revenue
    FROM {table}
)

SELECT
    one_time_revenue.revenue
        AS one_time_customer_revenue,

    total_revenue.revenue
        AS total_revenue,

    CASE
        WHEN total_revenue.revenue = 0 THEN 0
        ELSE
            (
                one_time_revenue.revenue
                / total_revenue.revenue
            ) * 100
    END AS revenue_share_percentage

FROM one_time_revenue
CROSS JOIN total_revenue;
""".strip()

    return f"""
WITH customer_transactions AS (
    SELECT
        {customer},
        COUNT(*) AS transaction_count
    FROM {table}
    GROUP BY {customer}
),

one_time_revenue AS (
    SELECT
        COALESCE(SUM(t.{revenue}), 0) AS revenue
    FROM {table} t
    INNER JOIN customer_transactions c
        ON t.{customer} = c.{customer}
    WHERE c.transaction_count = 1
),

total_revenue AS (
    SELECT
        COALESCE(SUM({revenue}), 0) AS revenue
    FROM {table}
)

SELECT
    one_time_revenue.revenue
        AS one_time_customer_revenue,

    total_revenue.revenue
        AS total_revenue,

    CASE
        WHEN total_revenue.revenue = 0 THEN 0
        ELSE
            (
                one_time_revenue.revenue
                / total_revenue.revenue
            ) * 100
    END AS revenue_share_percentage

FROM one_time_revenue
CROSS JOIN total_revenue;
""".strip()


def generate_product_pairs_sql(
    plan: QueryPlan,
    table_name: str,
    columns: list[str],
) -> str:

    allowed_columns = set(columns)

    validate_column(
        plan.product_column,
        allowed_columns,
        "product column",
    )

    validate_column(
        plan.order_column,
        allowed_columns,
        "order column",
    )

    product = quote_identifier(plan.product_column)
    order = quote_identifier(plan.order_column)
    table = quote_identifier(table_name)

    limit = plan.limit or 10

    return f"""
WITH distinct_order_products AS (
    SELECT DISTINCT
        {order} AS order_id,
        {product} AS product
    FROM {table}
    WHERE {product} IS NOT NULL
      AND {order} IS NOT NULL
),

product_pairs AS (
    SELECT
        a.product AS product_a,
        b.product AS product_b,
        COUNT(*) AS times_bought_together
    FROM distinct_order_products a
    INNER JOIN distinct_order_products b
        ON a.order_id = b.order_id
       AND a.product < b.product
    GROUP BY
        a.product,
        b.product
)

SELECT
    product_a,
    product_b,
    times_bought_together
FROM product_pairs
ORDER BY times_bought_together DESC
LIMIT {int(limit)};
""".strip()


def generate_monthly_revenue_sql(
    plan: QueryPlan,
    table_name: str,
    columns: list[str],
) -> str:

    allowed_columns = set(columns)

    validate_column(
        plan.measure_column,
        allowed_columns,
        "revenue measure column",
    )

    validate_column(
        plan.date_column,
        allowed_columns,
        "date column",
    )

    if not plan.date_start or not plan.date_end:
        raise ValueError(
            "Both date_start and date_end are required."
        )

    measure = quote_identifier(plan.measure_column)
    date_column = quote_identifier(plan.date_column)
    table = quote_identifier(table_name)

    return f"""
SELECT
    COALESCE(SUM({measure}), 0) AS net_revenue
FROM {table}
WHERE CAST({date_column} AS DATE)
      >= DATE '{plan.date_start}'
  AND CAST({date_column} AS DATE)
      <= DATE '{plan.date_end}';
""".strip()

def generate_quarter_comparison_sql(
    plan: QueryPlan,
    table_name: str,
    columns: list[str],
) -> str:

    allowed_columns = set(columns)

    validate_column(
        plan.measure_column,
        allowed_columns,
        "measure column",
    )

    validate_column(
        plan.date_column,
        allowed_columns,
        "date column",
    )

    if not plan.period_1_start or not plan.period_1_end:
        raise ValueError(
            "First comparison period is incomplete."
        )

    if not plan.period_2_start or not plan.period_2_end:
        raise ValueError(
            "Second comparison period is incomplete."
        )

    measure = quote_identifier(plan.measure_column)
    date_column = quote_identifier(plan.date_column)
    table = quote_identifier(table_name)

    # Validate dimensions
    for dimension in plan.dimension_columns:
        validate_column(
            dimension,
            allowed_columns,
            "dimension column",
        )

    # ----------------------------------------
    # Dimensions
    # ----------------------------------------

    if plan.dimension_columns:

        dimension_select = ", ".join(
            quote_identifier(d)
            for d in plan.dimension_columns
        )

        dimension_group = dimension_select

    else:

        dimension_select = ""
        dimension_group = ""

    # ----------------------------------------
    # SELECT dimensions
    # ----------------------------------------

    if dimension_select:
        final_dimensions = dimension_select + ","
        group_by_dimensions = (
            f"GROUP BY {dimension_group}"
        )
    else:
        final_dimensions = ""
        group_by_dimensions = ""

    # ----------------------------------------
    # Generate SQL
    # ----------------------------------------

    return f"""
WITH classified_data AS (

    SELECT
        {dimension_select + "," if dimension_select else ""}

        CASE
            WHEN CAST({date_column} AS DATE)
                 BETWEEN DATE '{plan.period_1_start}'
                 AND DATE '{plan.period_1_end}'
            THEN 'period_1'

            WHEN CAST({date_column} AS DATE)
                 BETWEEN DATE '{plan.period_2_start}'
                 AND DATE '{plan.period_2_end}'
            THEN 'period_2'
        END AS period,

        {measure} AS measure_value

    FROM {table}

    WHERE
        CAST({date_column} AS DATE)
        BETWEEN DATE '{plan.period_1_start}'
        AND DATE '{plan.period_1_end}'

        OR

        CAST({date_column} AS DATE)
        BETWEEN DATE '{plan.period_2_start}'
        AND DATE '{plan.period_2_end}'
),

aggregated AS (

    SELECT
        {dimension_select + "," if dimension_select else ""}

        SUM(
            CASE
                WHEN period = 'period_1'
                THEN measure_value
                ELSE 0
            END
        ) AS period_1_value,

        SUM(
            CASE
                WHEN period = 'period_2'
                THEN measure_value
                ELSE 0
            END
        ) AS period_2_value

    FROM classified_data

    {group_by_dimensions}

)

SELECT
    {final_dimensions}

    period_1_value,
    period_2_value,

    period_2_value - period_1_value
        AS absolute_change,

    CASE
        WHEN period_1_value = 0 THEN NULL
        ELSE
            (
                (period_2_value - period_1_value)
                / period_1_value
            ) * 100
    END AS growth_percentage

FROM aggregated

ORDER BY growth_percentage DESC;
""".strip()


def generate_basic_sql(
    plan: QueryPlan,
    table_name: str,
    columns: list[str],
) -> str:

    allowed_columns = set(columns)

    for column in plan.dimension_columns:
        validate_column(
            column,
            allowed_columns,
            "dimension column",
        )

    if plan.measure_column:
        validate_column(
            plan.measure_column,
            allowed_columns,
            "measure column",
        )

    if plan.date_column:
        validate_column(
            plan.date_column,
            allowed_columns,
            "date column",
        )

    table = quote_identifier(table_name)

    dimensions = [
        quote_identifier(column)
        for column in plan.dimension_columns
    ]

    select_parts = []
    group_parts = []

    for dimension in dimensions:
        select_parts.append(dimension)
        group_parts.append(dimension)

    measure = (
        quote_identifier(plan.measure_column)
        if plan.measure_column
        else None
    )

    if plan.aggregation != "none":

        if plan.aggregation != "count" and measure is None:
            raise ValueError(
                "This aggregation requires a measure column."
            )

        if plan.aggregation == "sum":
            expression = f"SUM({measure})"

        elif plan.aggregation == "avg":
            expression = f"AVG({measure})"

        elif plan.aggregation == "min":
            expression = f"MIN({measure})"

        elif plan.aggregation == "max":
            expression = f"MAX({measure})"

        elif plan.aggregation == "count":
            expression = "COUNT(*)"

        elif plan.aggregation == "count_distinct":
            expression = f"COUNT(DISTINCT {measure})"

        else:
            raise ValueError(
                f"Unsupported aggregation: {plan.aggregation}"
            )

        alias = f"{plan.aggregation}_value"

        select_parts.append(
            f"{expression} AS {quote_identifier(alias)}"
        )

    elif not select_parts:

        select_parts.append("*")

    sql = (
        "SELECT "
        + ", ".join(select_parts)
        + f" FROM {table}"
    )

    if plan.date_column:

        date_column = quote_identifier(plan.date_column)

        conditions = []

        if plan.date_start:
            conditions.append(
                f"CAST({date_column} AS DATE) "
                f">= DATE '{plan.date_start}'"
            )

        if plan.date_end:
            conditions.append(
                f"CAST({date_column} AS DATE) "
                f"<= DATE '{plan.date_end}'"
            )

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

    if group_parts:
        sql += " GROUP BY " + ", ".join(group_parts)

    if plan.sort_direction:

        if plan.aggregation != "none":

            sort_expression = quote_identifier(
                f"{plan.aggregation}_value"
            )

        elif dimensions:

            sort_expression = dimensions[0]

        else:

            raise ValueError(
                "Invalid sorting configuration."
            )

        sql += (
            " ORDER BY "
            + sort_expression
            + " "
            + plan.sort_direction.upper()
        )

    if plan.limit:
        sql += f" LIMIT {int(plan.limit)}"

    sql += ";"

    return sql


def generate_sql(
    plan: QueryPlan,
    table_name: str,
    columns: list[str],
) -> str:

    if plan.question_type == "frequency":
        return generate_frequency_sql(
            plan,
            table_name,
            columns,
        )

    if plan.question_type == "revenue_share":
        return generate_revenue_share_sql(
            plan,
            table_name,
            columns,
        )

    if plan.question_type == "product_pairs":
        return generate_product_pairs_sql(
            plan,
            table_name,
            columns,
        )

    if plan.question_type == "comparison":
        return generate_quarter_comparison_sql(
            plan,
            table_name,
            columns,
        )

    if (
        plan.question_type == "aggregation"
        and plan.date_start
        and plan.date_end
        and plan.measure_column
    ):
        return generate_monthly_revenue_sql(
            plan,
            table_name,
            columns,
        )

    return generate_basic_sql(
        plan,
        table_name,
        columns,
    )