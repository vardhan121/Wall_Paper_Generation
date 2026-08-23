from pydantic import BaseModel, Field


class Activity(BaseModel):
    url: str = Field(max_length=2048)
    domain: str = Field(max_length=512)
    title: str = Field(max_length=1000)
    started_at: float
    duration_seconds: int = Field(default=0, ge=0, le=86400)


class ActivityBatch(BaseModel):
    events: list[Activity] = Field(max_length=200)
