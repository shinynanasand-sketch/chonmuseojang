"""운영자 AI사무장용 프롬프트 (단일 village_id 컨텍스트)."""

from services.llm_provider import get_llm_provider
from services.supabase_client import get_village_by_id, insert_content

_INTRO = "소개글"
_SNS = "SNS홍보문구"


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


def generate_operator_content(operator: dict, village: dict, user_message: str) -> dict[str, str]:
    """담당 마을 1건과 운영자 설명만으로 소개글·SNS 문구를 만든다."""
    llm = get_llm_provider()
    village_name = village.get("village_name")
    system_prompt = (
        f"당신은 마을 {village_name} (ID: {operator['village_id']})의 AI 사무장입니다. "
        "다른 마을 정보는 절대 언급하지 마세요. "
        "답은 두 줄로만 작성하세요. "
        f"첫째 줄은 '{_INTRO}: '으로, 둘째 줄은 '{_SNS}: '으로 시작하세요."
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


def save_operator_contents(operator: dict, description: str) -> dict:
    village = get_village_by_id(operator["village_id"])
    if not village:
        return {"saved": False, "message": "마을 정보를 찾지 못했습니다."}
    drafts = generate_operator_content(operator, village, description)
    if not drafts:
        return {"saved": False, "message": "홍보문구를 만들지 못했습니다. 설명을 조금 더 적어 주세요."}
    saved = []
    for content_type in (_INTRO, _SNS):
        saved.append(
            insert_content(
                {
                    "village_id": operator["village_id"],
                    "operator_id": operator.get("operator_id"),
                    "content_type": content_type,
                    "body": drafts[content_type],
                }
            )
        )
    return {"saved": True, "contents": saved}
