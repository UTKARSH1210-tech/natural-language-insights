from __future__ import annotations

from app.query.planner import QueryPlan


def format_number(value) -> str:
    if value is None:
        return "N/A"

    if isinstance(value, float):
        return f"{value:,.2f}"

    if isinstance(value, int):
        return f"{value:,}"

    return str(value)


def generate_answer(
    question: str,
    result: dict,
    plan: QueryPlan | None = None,
) -> str:

    rows = result.get("rows", [])
    row_count = result.get("row_count", 0)

    if row_count == 0:
        return "No matching data was found for this question."

    if plan:

        if plan.question_type == "revenue_share":

            row = rows[0]

            revenue = row.get(
                "one_time_customer_revenue"
            )

            total = row.get(
                "total_revenue"
            )

            percentage = row.get(
                "revenue_share_percentage"
            )

            return (
                f"Customers who bought only once generated "
                f"{format_number(revenue)} in revenue, "
                f"which represents "
                f"{format_number(percentage)}% "
                f"of total revenue "
                f"({format_number(total)})."
            )

        if plan.question_type == "frequency":

            return (
                f"{row_count} customer(s) "
                f"bought only once."
            )

        if plan.question_type == "product_pairs":

            lines = []

            for row in rows[:10]:

                product_a = row.get(
                    "product_a"
                )

                product_b = row.get(
                    "product_b"
                )

                count = row.get(
                    "times_bought_together"
                )

                lines.append(
                    f"{product_a} + {product_b}: "
                    f"{format_number(count)} order(s)"
                )

            return (
                "Products most frequently bought together:\n"
                + "\n".join(lines)
            )

        if plan.question_type == "comparison":

            lines = []

            for row in rows[:10]:

                prefix = ""

                for dimension in plan.dimension_columns:
                    prefix += (
                        f"{dimension}: "
                        f"{row.get(dimension)} | "
                    )

                lines.append(
                    prefix
                    + f"Period 1: "
                    f"{format_number(row.get('period_1_revenue'))} | "
                    f"Period 2: "
                    f"{format_number(row.get('period_2_revenue'))} | "
                    f"Growth: "
                    f"{format_number(row.get('growth_percentage'))}%"
                )

            return (
                "Period comparison:\n"
                + "\n".join(lines)
            )

        if (
            plan.question_type == "aggregation"
            and len(rows) == 1
        ):

            row = rows[0]

            if "net_revenue" in row:

                return (
                    f"Net revenue for the requested period was "
                    f"{format_number(row['net_revenue'])}."
                )

    if row_count == 1:

        row = rows[0]

        if len(row) == 1:

            value = next(iter(row.values()))

            return (
                f"The answer is {format_number(value)}."
            )

        parts = [
            f"{key}: {format_number(value)}"
            for key, value in row.items()
        ]

        return "; ".join(parts) + "."

    lines = []

    for row in rows[:10]:

        parts = [
            f"{key}: {format_number(value)}"
            for key, value in row.items()
        ]

        lines.append(" | ".join(parts))

    answer = (
        f"Found {row_count} result(s).\n"
        f"Top results:\n"
        + "\n".join(lines)
    )

    if row_count > 10:
        answer += (
            f"\nShowing the first 10 of "
            f"{row_count} results."
        )

    return answer