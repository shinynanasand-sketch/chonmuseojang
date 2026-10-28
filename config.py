import os
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent
# .env 우선, 없으면 .env.local (로컬 전용) 로드
load_dotenv(_ROOT / ".env")
load_dotenv(_ROOT / ".env.local", override=False)

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
CRON_SECRET = os.getenv("CRON_SECRET", "")


def presentation_enabled(raw: str | None = None) -> bool:
    """0만 끈다. 비어 있거나 다른 값은 발표 화면을 연다."""
    if raw is None:
        raw = os.getenv("PRESENTATION_MODE", "1")
    return raw.strip() != "0"


# 0이면 홈의 시연 순서와 발화 복사를 숨긴다. 그 외는 발표 화면을 연다.
PRESENTATION_MODE = presentation_enabled()
KAKAO_CHANNEL_URL = "https://pf.kakao.com/_RgZaX"
KAKAO_CARD_IMAGE_URL = "https://chonmuseojang.vercel.app/static/kakao-card.png"

TARGET_SIDO_NAMES = [
    "광주광역시",
    "전라남도",
    "전남광주통합특별시",
    "광주특별시",
]

TARGET_SIGUNGU_LIST = [
    "동구",
    "서구",
    "남구",
    "북구",
    "광산구",
    "목포시",
    "여수시",
    "순천시",
    "나주시",
    "광양시",
    "담양군",
    "곡성군",
    "구례군",
    "고흥군",
    "보성군",
    "화순군",
    "장흥군",
    "강진군",
    "해남군",
    "영암군",
    "무안군",
    "함평군",
    "영광군",
    "장성군",
    "완도군",
    "진도군",
    "신안군",
]
