from fastapi import FastAPI

from app.api.datasets import (
    router as datasets_router,
)

from app.api.health import (
    router as health_router,
)

from app.api.jobs import (
    router as jobs_router,
)

from app.api.questions import (
    router as questions_router,
)


app = FastAPI(
    title="Natural Language Insights",
    version="0.1.0",
    description=(
        "Natural language analytics "
        "over arbitrary transactional CSVs."
    ),
)


app.include_router(
    health_router
)

app.include_router(
    datasets_router,
    prefix="/datasets",
    tags=["datasets"],
)

app.include_router(
    jobs_router
)

app.include_router(
    questions_router
)