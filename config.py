import os
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent
# .env 우선, 없으면 .env.local (로컬 전용) 로드
load_dotenv(_ROOT / ".env")
load_dotenv(_ROOT / ".env.local", override=False)

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
CRON_SECRET = os.getenv("CRON_SECRET", "")

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
