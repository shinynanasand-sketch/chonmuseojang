from typing import Any

from pydantic import BaseModel


class KakaoUserRequest(BaseModel):
    utterance: str = ""
    user: dict[str, Any] = {}


class KakaoAction(BaseModel):
    name: str = ""
    params: dict[str, Any] = {}


class KakaoSkillRequest(BaseModel):
    userRequest: KakaoUserRequest
    action: KakaoAction = KakaoAction()
