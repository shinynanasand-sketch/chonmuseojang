"""운영자 AI사무장용 프롬프트 (단일 village_id 컨텍스트)."""

from services.llm_provider import get_llm_provider


def generate_operator_content(operator: dict, village: dict, user_message: str) -> str:
    llm = get_llm_provider()
    system_prompt = (
        f"당신은 마을 {village.get('village_name')} (ID: {operator['village_id']})의 AI 사무장입니다. "
        "다른 마을 정보는 절대 언급하지 마세요."
    )
    context = (
        f"마을명: {village.get('village_name')}\n"
        f"위치: {village.get('sigungu')}\n"
        f"체험: {village.get('program_type')}\n"
    )
    return llm.generate(system_prompt, f"{context}\n\n요청: {user_message}")
