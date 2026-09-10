from __future__ import annotations

import os
from typing import Literal

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

load_dotenv()


class QueryPlan(BaseModel):
    answerable: bool
    refusal_reason: str | None = None

    question_type: Literal[
        "aggregation",
        "ranking",
        "comparison",
        "trend",
        "frequency",
        "revenue_share",
        "product_pairs",
        "grouped_analysis",
        "other",
    ] = "other"

    # General analytics
    measure_column: str | None = None
    dimension_columns: list[str] = Field(default_factory=list)

    aggregation: Literal[
        "sum",
        "avg",
        "count",
        "count_distinct",
        "min",
        "max",
        "none",
    ] = "none"

    sort_direction: Literal["asc", "desc"] | None = None
    limit: int | None = Field(default=None, ge=1, le=1000)

    # Time analysis
    date_column: str | None = None
    date_start: str | None = None
    date_end: str | None = None

    # Customer / product / order analysis
    customer_column: str | None = None
    product_column: str | None = None
    order_column: str | None = None

    # Quarter comparison
    period_1_start: str | None = None
    period_1_end: str | None = None
    period_2_start: str | None = None
    period_2_end: str | None = None

    # Kept for compatibility with your earlier version
    filter_expression: str | None = None


def build_schema_context(profile: dict) -> str:
    lines = [
        f"Dataset rows: {profile['row_count']}",
        f"Dataset columns: {profile['column_count']}",
        "",
        "AVAILABLE COLUMNS:",
    ]

    for column in profile["columns"]:
        lines.append(
            f"- name={column['name']}; "
            f"type={column['type']}; "
            f"role={column['role']}; "
            f"distinct={column['distinct_count']}; "
            f"nulls={column['null_count']}"
        )

    return "\n".join(lines)


def create_query_plan(question: str, profile: dict) -> QueryPlan:
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")

    model = os.getenv("GEMINI_MODEL", "gemini-3.7-flash")

    client = genai.Client(api_key=api_key)

    schema_context = build_schema_context(profile)

    system_instruction = """
You are a careful analytics query planner.

Your ONLY job is to translate a user's natural-language analytics
question into a structured QueryPlan.

You do NOT calculate answers.
You do NOT write SQL.

STRICT RULES:

1. ONLY use columns listed in AVAILABLE COLUMNS.
2. NEVER invent columns.
3. NEVER invent metrics.
4. If the requested concept cannot be confidently mapped to available
   columns, set answerable=false.
5. Customer questions require a customer/entity identifier.
6. Product questions require a product/item identifier or description field.
7. Geographic questions require a geographic field.
8. Time questions require a date/time column.
9. Revenue questions require a numeric column that can reasonably
   represent revenue, sales, amount, or value.
10. Profit questions require enough information to calculate profit.
11. Margin questions require enough information to calculate margin.
12. Do not assume that every numeric column represents revenue.
13. For "top N" questions, set limit=N.
14. dimension_columns MUST contain actual dataset columns only.
15. measure_column MUST contain an actual dataset column only.
16. If there is insufficient information, refuse the question.
17. Do not write SQL.
18. Do not calculate numerical answers.
19. Be conservative. If uncertain, refuse.
20. Return only the requested structured object.

ANALYTICS TYPES:

21. Simple totals/averages/counts should use question_type="aggregation".

22. "Top N", "highest", "lowest", "best", or "worst" questions
    should use question_type="ranking".

23. Questions comparing two periods should use question_type="comparison".

24. Questions about change over time should use question_type="trend".

25. Questions asking which customers bought only once should use
    question_type="frequency".

26. For frequency questions:
    - customer_column identifies the customer.
    - order_column identifies an order/transaction when available.
    - If order_column exists, use unique orders to determine purchase count.
    - "Bought only once" means exactly one unique order.

27. Questions asking for revenue share/percentage from one-time customers
    should use question_type="revenue_share".
    They require:
    - customer_column
    - measure_column
    - order_column when available

28. Questions asking which products were bought together should use
    question_type="product_pairs".
    They require:
    - product_column
    - order_column

29. Product-pair analysis means two different products appearing in
    the same order.

30. For country/region analysis, identify the appropriate geographic
    dimension column in dimension_columns.

31. Quarter-over-quarter questions require:
    - date_column
    - measure_column
    - period_1_start
    - period_1_end
    - period_2_start
    - period_2_end

32. If the user specifies quarters such as Q1 2024 and Q2 2024,
    convert them into actual calendar dates.

33. If a required year is missing and the question cannot be interpreted
    safely, refuse rather than inventing a year.

34. Monthly revenue questions require:
    - date_column
    - measure_column
    - date_start
    - date_end

35. "Net revenue" may only be answered if the dataset has a suitable
    revenue/value field and there is no evidence that a separate
    deduction is required. Do not invent returns, discounts, taxes,
    or costs.

36. If a requested metric cannot be reliably calculated from the schema,
    refuse.

37. Customer, product, order, geography and date fields must come
    directly from AVAILABLE COLUMNS.

38. Never use natural-language concepts as column names.

39. Never write SQL.

40. Never calculate the result.
"""

    user_prompt = f"""
DATASET SCHEMA
==============

{schema_context}

USER QUESTION
=============

{question}
"""

    response = client.models.generate_content(
        model=model,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=QueryPlan,
            temperature=0,
        ),
    )

    if not response.text:
        raise RuntimeError("Gemini returned an empty response.")

    try:
        return QueryPlan.model_validate_json(response.text)
    except Exception as exc:
        raise RuntimeError(
            "Gemini returned an invalid query plan."
        ) from exc