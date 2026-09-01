"""로컬 시연 경로 자동 점검 (Step 4)."""

import os
import sys

import _bootstrap  # noqa: F401

from dotenv import load_dotenv
from fastapi.testclient import TestClient

load_dotenv()

from main import app  # noqa: E402
from services.public_data_sync import sync_village_data

client = TestClient(app)
CRON_SECRET = os.getenv("CRON_SECRET", "")


def check(name: str, ok: bool, detail: str = "") -> bool:
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))
    return ok


def main() -> int:
    print("=== 체험마을 AI사무장 시연 경로 점검 ===\n")
    sync_village_data(use_demo_fallback=True)
    all_ok = True

    r = client.get("/")
    all_ok &= check("홈 화면 GET /", r.status_code == 200)

    r = client.get("/api/villages")
    all_ok &= check("마을 목록 GET /api/villages", r.status_code == 200 and "villages" in r.json())

    r = client.post("/api/recommend", json={"query": "갯벌체험"})
    body = r.json()
    all_ok &= check(
        "AI 추천 POST /api/recommend",
        r.status_code == 200 and body.get("status") in ("success", "empty"),
    )

    r = client.get("/api/nearby?village_id=V001")
    all_ok &= check("주변정보 GET /api/nearby", r.status_code == 200)

    r = client.get("/api/dashboard/summary")
    all_ok &= check(
        "공개 대시보드 GET /api/dashboard/summary",
        r.status_code == 200 and "total_villages" in r.json(),
    )

    r = client.get("/api/operator/dashboard")
    all_ok &= check("운영자 API 인증 없음 → 401/403", r.status_code in (401, 403))

    r = client.get(
        "/api/operator/dashboard",
        headers={"Authorization": "Bearer kakao_owner_v001"},
    )
    all_ok &= check("운영자 A 대시보드", r.status_code == 200)

    if CRON_SECRET:
        r = client.get("/api/cron/sync", headers={"Authorization": f"Bearer {CRON_SECRET}"})
        all_ok &= check("Cron 동기화", r.status_code == 200 and r.json().get("status") == "success")
    else:
        print("  [SKIP] CRON_SECRET 미설정 — cron 동기화 생략")

    r = client.post(
        "/kakao/booking",
        json={
            "userRequest": {"utterance": "예약", "user": {"id": "demo_user"}},
            "action": {"params": {"visit_date": "2026-09-20", "num_people": "2"}},
        },
    )
    all_ok &= check("카카오 예약 웹훅", r.status_code == 200 and r.json().get("version") == "2.0")

    print()
    if all_ok:
        print("모든 시연 경로 점검 통과")
        return 0
    print("일부 점검 실패 — 위 FAIL 항목을 확인하세요.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
