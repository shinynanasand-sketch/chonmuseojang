"""Supabase schema/seed 적용 (service_role 키 필요).

Supabase MCP 또는 SQL Editor가 불가할 때 로컬에서 시도한다.
키가 없으면 SQL 파일 경로와 수동 실행 안내를 출력한다.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import _bootstrap  # noqa: F401
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "supabase" / "schema.sql"
SEED = ROOT / "supabase" / "seed.sql"


def _print_manual_instructions() -> int:
    print("SUPABASE_SERVICE_ROLE_KEY가 없어 자동 적용을 건너뜁니다.")
    print("Supabase SQL Editor에서 아래 파일을 순서대로 실행하세요:")
    print(f"  1. {SCHEMA}")
    print(f"  2. {SEED}")
    print("또는 키 입력 후: uv run python scripts/load_demo_seed.py")
    return 1


def main() -> int:
    if not os.getenv("SUPABASE_SERVICE_ROLE_KEY"):
        return _print_manual_instructions()

    try:
        from scripts.load_demo_seed import load_demo_seed

        result = load_demo_seed()
        print("시드 로드 완료:", result)
        print("schema.sql은 Supabase SQL Editor에서 1회 실행했는지 확인하세요.")
        return 0
    except Exception as exc:
        print("Supabase 연결/시드 실패:", exc)
        return _print_manual_instructions()


if __name__ == "__main__":
    sys.exit(main())
