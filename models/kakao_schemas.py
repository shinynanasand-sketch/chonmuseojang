from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class KakaoUserRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    utterance: str = ""
    user: dict[str, Any] = Field(default_factory=dict)

    @field_validator("utterance", mode="before")
    @classmethod
    def _utterance_none_to_empty(cls, value: Any) -> str:
        return "" if value is None else str(value)

    @field_validator("user", mode="before")
    @classmethod
    def _user_none_to_dict(cls, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}


class KakaoAction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = ""
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name", mode="before")
    @classmethod
    def _name_none_to_empty(cls, value: Any) -> str:
        return "" if value is None else str(value)

    @field_validator("params", mode="before")
    @classmethod
    def _params_none_to_dict(cls, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}


class KakaoSkillRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    userRequest: KakaoUserRequest = Field(default_factory=KakaoUserRequest)
    action: KakaoAction = Field(default_factory=KakaoAction)

    @model_validator(mode="before")
    @classmethod
    def _null_sections_to_defaults(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return {}
        if data.get("userRequest") is None:
            data = {**data, "userRequest": {}}
        if data.get("action") is None:
            data = {**data, "action": {}}
        return data
