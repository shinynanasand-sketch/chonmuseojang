"""환경 변수 설정 상태를 점검한다."""

import os
import sys

import _bootstrap  # noqa: F401

from dotenv import load_dotenv

load_dotenv()

REQUIRED_FOR_DB = ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"]
OPTIONAL = {
    "PUBLIC_DATA_SERVICE_KEY": "공공데이터 동기화",
    "PUBLIC_DATA_VILLAGE_ENDPOINT": "공공데이터 동기화",
    "GEMINI_API_KEY": "AI 추천 (LLM_PROVIDER=gemini)",
    "TOUR_API_SERVICE_KEY": "주변 관광정보",
    "KAKAO_REST_API_KEY": "카카오 이벤트 API",
    "CRON_SECRET": "동기화 API 보호",
}


def main() -> int:
    missing = [k for k in REQUIRED_FOR_DB if not os.getenv(k)]
    if missing:
        print("필수 (Supabase 실연동):", ", ".join(missing))
        print("  → Supabase 대시보드 > Project Settings > API 에서 service_role 키를 .env에 입력하세요.")
    else:
        print("Supabase: 설정 완료")

    for key, purpose in OPTIONAL.items():
        status = "OK" if os.getenv(key) else "미설정"
        print(f"  [{status}] {key} - {purpose}")

    if missing:
        print("\n인메모리 폴백으로 로컬 개발은 가능합니다. 시드: uv run python scripts/load_demo_seed.py")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
