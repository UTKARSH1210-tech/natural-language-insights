from pydantic import BaseModel, Field


class QuestionRequest(BaseModel):
    dataset_id: str = Field(
        min_length=1,
        description="ID of the uploaded dataset.",
    )

    question: str = Field(
        min_length=1,
        max_length=1000,
        description="Natural-language analytics question.",
    )