"""운영자 AI사무장용 프롬프트 (단일 village_id 컨텍스트)."""

import os
import re
import uuid

from services.llm_provider import get_llm_provider
from services.supabase_client import get_supabase_client, get_village_by_id, insert_content

_INTRO = "소개글"
_SNS = "SNS홍보문구"
_INTRO_SENTENCES = 4
_INTRO_LIMIT = 400
_SNS_SENTENCES = 2
_SNS_LIMIT = 120
_MAX_PHOTO_BYTES = 2 * 1024 * 1024
_PHOTO_BUCKET = "content-photos"
_PHOTO_TYPES = {
    "jpg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}


class PhotoRejected(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _split_drafts(raw: str) -> dict[str, str]:
    text = (raw or "").strip()
    if not text or text == "[]":
        return {}
    intro_label = f"{_INTRO}:"
    sns_label = f"{_SNS}:"
    if intro_label in text and sns_label in text:
        intro_at = text.index(intro_label)
        sns_at = text.index(sns_label)
        if intro_at < sns_at:
            intro = text[intro_at + len(intro_label) : sns_at]
            sns = text[sns_at + len(sns_label) :]
        else:
            sns = text[sns_at + len(sns_label) : intro_at]
            intro = text[intro_at + len(intro_label) :]
        intro, sns = intro.strip(), sns.strip()
        if intro and sns:
            return {_INTRO: intro, _SNS: sns}
        return {}
    return {_INTRO: text, _SNS: text}


def _clip_draft(text: str, sentences: int, limit: int) -> str:
    parts = [part.strip() for part in re.split(r"(?<=[.!?。])\s+", text.strip()) if part.strip()]
    clipped = " ".join(parts[:sentences]) if parts else text.strip()
    if len(clipped) <= limit:
        return clipped
    return clipped[:limit].rstrip()


def _image_kind(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp"
    return None


def _checked_photo(data: bytes) -> str:
    if len(data) > _MAX_PHOTO_BYTES:
        raise PhotoRejected("사진은 2MB 이하만 올릴 수 있습니다.")
    kind = _image_kind(data)
    if not kind:
        raise PhotoRejected("사진은 jpeg, png, webp만 올릴 수 있습니다.")
    return kind


def store_content_photo(village_id: str, data: bytes) -> str:
    """담당 마을 경로로 사진을 올리고 공개 주소를 돌려준다."""
    kind = _image_kind(data) or "jpg"
    name = f"{village_id}/{uuid.uuid4().hex}.{kind}"
    client = get_supabase_client()
    if client is None:
        raise RuntimeError("storage unavailable")
    client.storage.from_(_PHOTO_BUCKET).upload(
        name,
        data,
        file_options={"content-type": _PHOTO_TYPES[kind]},
    )
    base = os.getenv("SUPABASE_URL", "").rstrip("/")
    return f"{base}/storage/v1/object/public/{_PHOTO_BUCKET}/{name}"


def generate_operator_content(operator: dict, village: dict, user_message: str) -> dict[str, str]:
    """담당 마을 1건과 운영자 설명만으로 소개글·SNS 문구를 만든다."""
    llm = get_llm_provider()
    village_name = village.get("village_name")
    system_prompt = (
        f"당신은 마을 {village_name} (ID: {operator['village_id']})의 AI 사무장입니다. "
        "다른 마을 정보는 절대 언급하지 마세요. "
        "가격과 전화번호는 만들지 마세요. "
        "운영자가 적은 체험 내용을 소개글에 포함하세요. "
        f"소개글은 4문장, 400자 이내입니다. "
        f"SNS 문구는 2문장, 120자 이내입니다. "
        f"앞부분은 '{_INTRO}: '으로, 뒷부분은 '{_SNS}: '으로 시작하세요."
    )
    context = (
        f"마을명: {village_name}\n"
        f"위치: {village.get('sigungu')}\n"
        f"체험: {village.get('program_type')}\n"
    )
    try:
        raw = llm.generate(system_prompt, f"{context}\n\n요청: {user_message}")
    except Exception:
        return {}
    return _split_drafts(raw)


def save_operator_contents(operator: dict, description: str, photo: bytes | None = None) -> dict:
    if photo:
        _checked_photo(photo)
    village = get_village_by_id(operator["village_id"])
    if not village:
        return {"saved": False, "message": "마을 정보를 찾지 못했습니다."}
    drafts = generate_operator_content(operator, village, description)
    if not drafts:
        return {"saved": False, "message": "홍보문구를 만들지 못했습니다. 설명을 조금 더 적어 주세요."}
    drafts[_INTRO] = _clip_draft(drafts[_INTRO], _INTRO_SENTENCES, _INTRO_LIMIT)
    drafts[_SNS] = _clip_draft(drafts[_SNS], _SNS_SENTENCES, _SNS_LIMIT)
    if not drafts[_INTRO] or not drafts[_SNS]:
        return {"saved": False, "message": "홍보문구를 만들지 못했습니다. 설명을 조금 더 적어 주세요."}
    photo_url = ""
    if photo:
        try:
            photo_url = store_content_photo(operator["village_id"], photo)
        except Exception:
            return {"saved": False, "message": "사진을 저장하지 못했습니다."}
    saved = []
    for content_type in (_INTRO, _SNS):
        row = {
            "village_id": operator["village_id"],
            "operator_id": operator.get("operator_id"),
            "content_type": content_type,
            "body": drafts[content_type],
        }
        if photo_url:
            row["photo_url"] = photo_url
        saved.append(insert_content(row))
    return {"saved": True, "contents": saved}
