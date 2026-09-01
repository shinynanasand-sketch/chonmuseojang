from pydantic import BaseModel, Field


class RecommendRequest(BaseModel):
    query: str = Field(..., min_length=1)


class RecommendResult(BaseModel):
    village_id: str
    village_name: str
    reason: str
    sigungu: str | None = None
    program_type: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    trust_score: float | None = None
