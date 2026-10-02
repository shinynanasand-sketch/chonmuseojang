"""카카오 스킬 웹훅 시연 점검 (로컬 또는 배포 URL).

키(KAKAO_ADMIN_KEY) 없이도 스킬 JSON 응답은 검증 가능합니다.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta

import httpx


def _ok(name: str, condition: bool, detail: str = "") -> bool:
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {name}" + (f" - {detail}" if detail else ""))
    return condition


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url",
        default="http://testserver",
        help="배포 URL 예: https://chonmuseojang.vercel.app (미지정 시 TestClient)",
    )
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    visit = (date.today() + timedelta(days=7)).isoformat()

    print(f"=== Kakao webhook check ({base}) ===\n")
    all_ok = True

    if base == "http://testserver":
        from fastapi.testclient import TestClient

        import _bootstrap  # noqa: F401
        from main import app

        client = TestClient(app)

        def post(path: str, payload: dict):
            return client.post(path, json=payload)
    else:

        def post(path: str, payload: dict):
            return httpx.post(f"{base}{path}", json=payload, timeout=30.0)

    r = post("/kakao/ping", {})
    body = r.json() if r.status_code == 200 else {}
    text = body.get("template", {}).get("outputs", [{}])[0].get("simpleText", {}).get("text", "")
    all_ok &= _ok(
        "POST /kakao/ping",
        r.status_code == 200 and text == "스킬 연결 OK" and "\n" not in text,
        f"status={r.status_code}",
    )

    booking_payload = {
        "userRequest": {
            "utterance": f"{visit} 2명 예약",
            "user": {"id": "kakao_customer_demo"},
        },
        "action": {
            "name": "booking",
            "params": {"visit_date": visit, "num_people": "2"},
        },
    }
    r = post("/kakao/booking", booking_payload)
    body = r.json() if r.status_code == 200 else {}
    booking_text = (
        body.get("template", {}).get("outputs", [{}])[0].get("simpleText", {}).get("text", "")
    )
    all_ok &= _ok(
        "POST /kakao/booking",
        r.status_code == 200
        and "simpleText" in body.get("template", {}).get("outputs", [{}])[0]
        and "\n" not in booking_text,
        f"status={r.status_code}",
    )

    # 오픈빌더 스킬 테스트에서 복사한 실 payload (num_people: number)
    openbuilder_payload = {
        "intent": {"id": "9kap24yhdblpya9n0qe4lbrg", "name": "블록 이름"},
        "userRequest": {
            "timezone": "Asia/Seoul",
            "params": {"ignoreMe": "true"},
            "block": {"id": "9kap24yhdblpya9n0qe4lbrg", "name": "블록 이름"},
            "utterance": "발화 내용",
            "lang": None,
            "user": {"id": "536285", "type": "accountId", "properties": {}},
        },
        "bot": {"id": "6aad4321707aa28d466ccfaf", "name": "봇 이름"},
        "action": {
            "name": "3uq4ole7qy",
            "clientExtra": None,
            "params": {"visit_date": "2026-09-30", "num_people": 2},
            "id": "9aea15uifaop2fmeu8aljjpq",
            "detailParams": {
                "visit_date": {
                    "origin": "2026-09-30",
                    "value": "2026-09-30",
                    "groupName": "",
                },
                "num_people": {"origin": 2, "value": 2, "groupName": ""},
            },
        },
    }
    r = post("/kakao/booking", openbuilder_payload)
    body = r.json() if r.status_code == 200 else {}
    ob_text = body.get("template", {}).get("outputs", [{}])[0].get("simpleText", {}).get("text", "")
    all_ok &= _ok(
        "POST /kakao/booking (openbuilder exact)",
        r.status_code == 200 and "예약" in ob_text and "\n" not in ob_text,
        f"status={r.status_code}",
    )

    # 배포/실DB에서는 booking_id를 응답 설명에서 파싱하기 어려워 승인·후기는 샘플 ID로 호출
    # (없을 때에도 스킬 에러 카드로 200 응답해야 함)
    approve_payload = {
        "userRequest": {"utterance": "승인", "user": {"id": "kakao_owner_v001"}},
        "action": {"params": {"booking_id": "1", "decision": "approve"}},
    }
    r = post("/kakao/approve", approve_payload)
    body = r.json() if r.status_code == 200 else {}
    all_ok &= _ok(
        "POST /kakao/approve",
        r.status_code == 200 and "outputs" in body.get("template", {}),
        f"status={r.status_code}",
    )

    review_payload = {
        "userRequest": {
            "utterance": "체험이 즐거웠어요",
            "user": {"id": "kakao_customer_demo"},
        },
        "action": {"params": {"booking_id": "1", "rating": "5"}},
    }
    r = post("/kakao/review", review_payload)
    body = r.json() if r.status_code == 200 else {}
    all_ok &= _ok(
        "POST /kakao/review",
        r.status_code == 200 and "outputs" in body.get("template", {}),
        f"status={r.status_code}",
    )

    print("\n" + ("All kakao webhook checks passed" if all_ok else "Some checks failed"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
