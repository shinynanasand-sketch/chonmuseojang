"""관광객에게 보여줄 마을 홍보. 확인된 최신 소개글·SNS만 공개한다."""

from services.supabase_client import get_village_by_id, list_contents, set_village_public_contents

_INTRO = "소개글"
_SNS = "SNS홍보문구"


def _latest_by_type(rows: list[dict]) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for row in rows:
        content_type = row.get("content_type")
        if content_type in (_INTRO, _SNS):
            latest[content_type] = row
    return latest


def _http_photo(row: dict) -> str:
    url = str(row.get("photo_url") or "").strip()
    if url.startswith("https://") or url.startswith("http://"):
        return url
    return ""


def public_village_promo(village_id: str) -> dict | None:
    village = get_village_by_id(village_id)
    if not village:
        return None
    public_rows = [row for row in list_contents(village_id=village_id) if row.get("is_public")]
    latest = _latest_by_type(public_rows)
    intro = latest.get(_INTRO, {})
    sns = latest.get(_SNS, {})
    return {
        "village_id": village.get("village_id"),
        "village_name": village.get("village_name") or "",
        "sigungu": village.get("sigungu") or "",
        "program_type": village.get("program_type") or "",
        "intro": str(intro.get("body") or ""),
        "sns": str(sns.get("body") or ""),
        "photo_url": _http_photo(intro) or _http_photo(sns),
    }


def publish_operator_contents(operator: dict) -> dict:
    village_id = operator["village_id"]
    latest = _latest_by_type(list_contents(village_id=village_id))
    if not latest:
        return {"published": False, "message": "공개할 홍보문구가 없습니다."}
    try:
        rows = set_village_public_contents(
            village_id, [int(row["content_id"]) for row in latest.values()]
        )
    except Exception:
        return {
            "published": False,
            "message": "공개 설정을 저장하지 못했습니다. 데이터베이스에 공개 칸을 만든 뒤 다시 눌러 주세요.",
        }
    public_rows = [row for row in rows if row.get("is_public")]
    return {"published": True, "contents": public_rows}
