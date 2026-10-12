"""저장된 마을로 고정 질문 네 개의 추천 이유를 출력한다. 키는 출력하지 않는다."""

import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_ROOT / ".env")
load_dotenv(_ROOT / ".env.local", override=False)

from services.recommend import _match_score, _search_terms, recommend_villages  # noqa: E402
from services.supabase_client import list_public_villages  # noqa: E402

_TIDAL = "아이와 갈만한 갯벌체험"
_BAMBOO = "담양 대나무"
_HEALING = "힐링 여행"
_UNKNOWN = "없는말 xyzxyz"
_QUERIES = (_TIDAL, _BAMBOO, _HEALING, _UNKNOWN)


def _row_for(item: dict, villages: list[dict]) -> dict:
    village_id = item.get("village_id")
    for row in villages:
        if row.get("village_id") == village_id:
            return row
    return {}


def _format_line(item: dict, villages: list[dict]) -> str:
    row = _row_for(item, villages)
    name = item.get("village_name") or row.get("village_name") or ""
    place = row.get("sigungu") or ""
    reason = item.get("reason") or ""
    return f"{name} / {place} / {reason}"


def _overlaps(query: str, row: dict) -> bool:
    score, _reason = _match_score(query, _search_terms(query), row)
    return score > 0


def _print_query(query: str, matches: list[dict], villages: list[dict]) -> None:
    shown = matches[:5]
    print(f"질문: {query}")
    print(f"건수 {len(shown)}")
    for item in shown:
        print(_format_line(item, villages))


def _tidal_ok(matches: list[dict]) -> bool:
    if not matches:
        print("결과: 실패")
        return False
    reason = str(matches[0].get("reason") or "")
    ok = "갯벌" in reason and "맞습니다" in reason
    print("결과: 통과" if ok else "결과: 실패")
    return ok


def _bamboo_note(matches: list[dict], villages: list[dict]) -> None:
    if not matches:
        print("표시: 없음")
        return
    found = []
    for item in matches[:5]:
        row = _row_for(item, villages)
        text = f"{row.get('sigungu') or ''} {item.get('reason') or ''}"
        for word in ("담양", "대나무"):
            if word in text and word not in found:
                found.append(word)
    print("표시: " + ", ".join(found) if found else "표시: 없음")


def _healing_ok(matches: list[dict], villages: list[dict]) -> bool:
    for item in matches[:5]:
        row = _row_for(item, villages)
        reason = str(item.get("reason") or "")
        if "맞습니다" in reason and not _overlaps(_HEALING, row):
            print("결과: 실패")
            return False
    print("결과: 통과")
    return True


def _unknown_ok(matches: list[dict]) -> bool:
    ok = len(matches) == 0
    print("결과: 통과" if ok else "결과: 실패")
    return ok


def main() -> int:
    villages = list_public_villages()
    print(f"마을 {len(villages)}")
    ok = True
    for query in _QUERIES:
        matches = recommend_villages(query, villages)
        print()
        _print_query(query, matches, villages)
        if query == _TIDAL:
            ok = _tidal_ok(matches) and ok
        elif query == _BAMBOO:
            _bamboo_note(matches, villages)
        elif query == _HEALING:
            ok = _healing_ok(matches, villages) and ok
        elif query == _UNKNOWN:
            ok = _unknown_ok(matches) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
