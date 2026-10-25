"""운영자 AI사무장용 프롬프트 (단일 village_id 컨텍스트)."""

import io
import logging
import os
import re
import uuid
from urllib.parse import urljoin, urlparse

import httpx

from services.llm_provider import get_llm_provider
from services.supabase_client import get_supabase_client, get_village_by_id, insert_content

logger = logging.getLogger(__name__)

_INTRO = "소개글"
_SNS = "SNS홍보문구"
_INTRO_SENTENCES = 4
_INTRO_LIMIT = 400
_SNS_SENTENCES = 2
_SNS_LIMIT = 120
_MAX_PHOTO_BYTES = 2 * 1024 * 1024
_MAX_PHOTO_DOWNLOAD = 8 * 1024 * 1024
_PHOTO_DOWNLOAD_TIMEOUT = 10.0
PHOTO_LLM_TIMEOUT = 15.0
_PHOTO_TOO_LARGE = "사진은 8MB 이하만 올릴 수 있습니다."
_PHOTO_REDIRECTS = {301, 302, 303, 307, 308}
_MAX_PHOTO_HOPS = 4
_PHOTO_GUIDE = "사진을 한 장 올려 주세요."
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


def _fit_photo(data: bytes) -> bytes:
    """2MB를 넘는 jpeg, png, webp를 2MB 이하 jpeg로 줄인다."""
    from PIL import Image, UnidentifiedImageError

    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError, ValueError):
        raise PhotoRejected("사진은 jpeg, png, webp만 올릴 수 있습니다.") from None
    image = image.convert("RGB")
    edge = min(max(image.size), 1600)
    quality = 85
    while True:
        working = image.copy()
        if max(working.size) > edge:
            working.thumbnail((edge, edge))
        buf = io.BytesIO()
        working.save(buf, format="JPEG", quality=quality, optimize=True)
        out = buf.getvalue()
        if len(out) <= _MAX_PHOTO_BYTES:
            return out
        if quality > 40:
            quality -= 15
            continue
        if edge > 480:
            edge = int(edge * 0.75)
            quality = 75
            continue
        raise PhotoRejected(_PHOTO_TOO_LARGE)


def _kakao_photo_host(host: str) -> bool:
    name = (host or "").lower().rstrip(".")
    return any(name == suffix or name.endswith("." + suffix) for suffix in ("kakaocdn.net", "kakao.com"))


def download_kakao_photo(url: str) -> bytes:
    """카카오 CDN 사진을 10초 안에 받는다. 8MB까지 받고, 2MB를 넘으면 jpeg로 줄인다."""
    current = url
    try:
        with httpx.Client(timeout=_PHOTO_DOWNLOAD_TIMEOUT, follow_redirects=False) as client:
            for _ in range(_MAX_PHOTO_HOPS):
                parsed = urlparse(current)
                if parsed.scheme not in {"http", "https"} or not _kakao_photo_host(parsed.hostname or ""):
                    raise PhotoRejected(_PHOTO_GUIDE)
                with client.stream("GET", current) as response:
                    if response.status_code in _PHOTO_REDIRECTS:
                        location = str(response.headers.get("location") or "").strip()
                        if not location:
                            raise PhotoRejected(_PHOTO_GUIDE)
                        current = urljoin(current, location)
                        continue
                    if response.status_code != 200:
                        raise PhotoRejected(_PHOTO_GUIDE)
                    chunks: list[bytes] = []
                    total = 0
                    for chunk in response.iter_bytes():
                        total += len(chunk)
                        if total > _MAX_PHOTO_DOWNLOAD:
                            raise PhotoRejected(_PHOTO_TOO_LARGE)
                        chunks.append(chunk)
                    data = b"".join(chunks)
                    break
            else:
                raise PhotoRejected(_PHOTO_GUIDE)
    except PhotoRejected:
        raise
    except Exception:
        raise PhotoRejected(_PHOTO_GUIDE) from None
    if len(data) > _MAX_PHOTO_BYTES:
        data = _fit_photo(data)
    _checked_photo(data)
    return data


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
    llm = get_llm_provider("openai")
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


def generate_operator_photo_content(
    operator: dict,
    village: dict,
    photo: bytes,
    media_type: str,
) -> dict[str, str]:
    """담당 마을 1건과 사진만으로 소개글·SNS 문구를 만든다."""
    llm = get_llm_provider("openai")
    village_name = village.get("village_name")
    system_prompt = (
        f"당신은 마을 {village_name} (ID: {operator['village_id']})의 AI 사무장입니다. "
        "다른 마을 정보는 절대 언급하지 마세요. "
        "가격과 전화번호는 만들지 마세요. "
        "사진에 보이는 체험만 소개글에 포함하세요. "
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
        raw = llm.generate_with_image(
            system_prompt,
            f"{context}\n\n이 사진으로 소개글과 SNS 문구를 작성하세요.",
            photo,
            media_type,
            timeout=PHOTO_LLM_TIMEOUT,
        )
    except Exception as exc:
        logger.warning("홍보 사진 초안 생성 실패: %s", type(exc).__name__)
        return {}
    return _split_drafts(raw)


def save_operator_photo_draft(operator: dict, photo: bytes) -> dict:
    """카카오 사진으로 소개글·SNS 초안만 저장한다. 공개와 후기는 바꾸지 않는다."""
    try:
        kind = _checked_photo(photo)
    except PhotoRejected as exc:
        return {"saved": False, "message": exc.message}
    village = get_village_by_id(operator["village_id"])
    if not village:
        return {"saved": False, "message": "마을 정보를 찾지 못했습니다."}
    drafts = generate_operator_photo_content(operator, village, photo, _PHOTO_TYPES[kind])
    if not drafts:
        return {"saved": False, "message": "홍보문구를 만들지 못했습니다."}
    drafts[_INTRO] = _clip_draft(drafts[_INTRO], _INTRO_SENTENCES, _INTRO_LIMIT)
    drafts[_SNS] = _clip_draft(drafts[_SNS], _SNS_SENTENCES, _SNS_LIMIT)
    if not drafts[_INTRO] or not drafts[_SNS]:
        return {"saved": False, "message": "홍보문구를 만들지 못했습니다."}
    try:
        photo_url = store_content_photo(operator["village_id"], photo)
    except Exception:
        return {"saved": False, "message": "사진을 저장하지 못했습니다."}
    saved = []
    for content_type in (_INTRO, _SNS):
        saved.append(
            insert_content(
                {
                    "village_id": operator["village_id"],
                    "operator_id": operator.get("operator_id"),
                    "content_type": content_type,
                    "body": drafts[content_type],
                    "photo_url": photo_url,
                    "is_public": False,
                }
            )
        )
    return {"saved": True, "contents": saved}


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
