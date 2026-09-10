from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.ingestion.registry import (
    dataset_exists,
    get_dataset_paths,
    get_profile_path,
)

from app.ingestion.schema_context import (
    load_dataset_profile,
)

from app.jobs.manager import job_manager

from app.models.schemas import (
    QuestionRequest,
)

from app.query.answer import (
    generate_answer,
)

from app.query.executor import (
    execute_query,
)

from app.query.planner import (
    create_query_plan,
)

from app.query.sql_generator import (
    generate_sql,
)

from app.query.validator import (
    SQLValidationError,
    validate_sql,
)


router = APIRouter(
    prefix="/questions",
    tags=["questions"],
)


def check_question_capability(
    question: str,
    profile: dict,
) -> str | None:

    question_lower = question.lower()

    columns = profile.get(
        "columns",
        [],
    )

    column_names = [
        column["name"].lower()
        for column in columns
    ]

    # -----------------------------
    # Profit / margin
    # -----------------------------

    profit_terms = [
        "profit",
        "profitability",
        "profit margin",
        "margin",
    ]

    asks_profit = any(
        term in question_lower
        for term in profit_terms
    )

    if asks_profit:

        has_profit = any(
            "profit" in name
            for name in column_names
        )

        has_cost = any(
            term in name
            for name in column_names
            for term in [
                "cost",
                "cogs",
                "expense",
            ]
        )

        has_revenue = any(
            term in name
            for name in column_names
            for term in [
                "revenue",
                "sales",
                "amount",
                "value",
            ]
        )

        if "margin" in question_lower:

            if not (
                has_profit and has_revenue
            ) and not (
                has_cost and has_revenue
            ):

                return (
                    "I cannot answer this question because "
                    "the dataset does not contain enough "
                    "information to calculate profit margin."
                )

        elif not (
            has_profit
            or (has_revenue and has_cost)
        ):

            return (
                "I cannot answer this question because "
                "the dataset does not contain enough "
                "information to calculate profit."
            )

    return None


def process_question(
    dataset_id: str,
    question: str,
):

    if not dataset_exists(dataset_id):

        raise ValueError(
            "Dataset does not exist or is not ready."
        )

    _, db_path = get_dataset_paths(
        dataset_id
    )

    profile_path = get_profile_path(
        dataset_id
    )

    profile = load_dataset_profile(
        profile_path
    )

    columns = [
        column["name"]
        for column in profile["columns"]
    ]

    allowed_columns = set(columns)

    # -----------------------------------
    # FAST DETERMINISTIC CAPABILITY CHECK
    # -----------------------------------

    capability_error = check_question_capability(
        question=question,
        profile=profile,
    )

    if capability_error:

        return {
            "status": "refused",
            "answer": capability_error,
            "plan": {
                "answerable": False,
                "refusal_reason": capability_error,
                "question_type": "other",
            },
        }

    # -----------------------------------
    # GEMINI PLANNING
    # -----------------------------------

    plan = create_query_plan(
        question=question,
        profile=profile,
    )

    # -----------------------------------
    # MODEL REFUSAL
    # -----------------------------------

    if not plan.answerable:

        return {
            "status": "refused",
            "answer": (
                plan.refusal_reason
                or
                "I cannot answer this question "
                "from the available data."
            ),
            "plan": plan.model_dump(),
        }

    # -----------------------------------
    # DETERMINISTIC SQL
    # -----------------------------------

    sql = generate_sql(
        plan=plan,
        table_name="transactions",
        columns=columns,
    )

    # -----------------------------------
    # SQL VALIDATION
    # -----------------------------------

    try:

        validated_sql = validate_sql(
            sql=sql,
            allowed_table="transactions",
            allowed_columns=allowed_columns,
        )

    except SQLValidationError as exc:

        raise ValueError(
            f"Generated query failed validation: {exc}"
        ) from exc

    # -----------------------------------
    # DUCKDB EXECUTION
    # -----------------------------------

    result = execute_query(
        db_path=db_path,
        sql=validated_sql,
    )

    # -----------------------------------
    # DETERMINISTIC ANSWER
    # -----------------------------------

    answer = generate_answer(
        question=question,
        result=result,
        plan=plan,
    )

    return {
        "status": "completed",
        "answer": answer,
        "sql": validated_sql,
        "result": result,
        "plan": plan.model_dump(),
    }


@router.post("")
def ask_question(
    request: QuestionRequest,
):

    if not request.question.strip():

        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_QUESTION",
                "message": "Question cannot be empty.",
            },
        )

    if not dataset_exists(
        request.dataset_id
    ):

        raise HTTPException(
            status_code=404,
            detail={
                "code": "DATASET_NOT_FOUND",
                "message": (
                    "Dataset not found or not ready."
                ),
            },
        )

    job_id = job_manager.submit(
        process_question,
        request.dataset_id,
        request.question,
    )

    return {
        "job_id": job_id,
        "status": "queued",
    }