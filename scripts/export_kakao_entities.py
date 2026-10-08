"""villages_cache를 오픈빌더 엔티티 CSV 두 개로 저장한다."""

import sys
from pathlib import Path

import _bootstrap  # noqa: F401

import config  # noqa: F401  .env를 읽어야 Supabase 마을 목록을 가져온다
from services.kakao_entity_export import EntityExportError, export_entity_csvs
from services.supabase_client import list_villages

OUT_DIR = Path(__file__).resolve().parents[1] / "exports"


def main() -> None:
    try:
        export_entity_csvs(list_villages(), OUT_DIR)
    except EntityExportError as exc:
        for line in exc.errors:
            print(line, file=sys.stderr)
        sys.exit(1)
    print(OUT_DIR / "village_name.csv")
    print(OUT_DIR / "registration_code.csv")


if __name__ == "__main__":
    main()
