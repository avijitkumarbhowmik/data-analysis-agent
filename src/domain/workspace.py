from pydantic import BaseModel, Field


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    dataset_id: str | None = None
