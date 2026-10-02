# 오픈빌더 웹훅 등록 (복사해서 붙여넣기)

오픈빌더 → 스킬 → URL:

```
https://chonmuseojang.vercel.app/kakao/booking
https://chonmuseojang.vercel.app/kakao/approve
https://chonmuseojang.vercel.app/kakao/review
```

| 스킬 이름 예시 | 메서드 | URL | 파라미터 |
|---|---|---|---|
| 예약접수 | POST | .../kakao/booking | visit_date, num_people |
| 예약승인 | POST | .../kakao/approve | booking_id, decision |
| 후기등록 | POST | .../kakao/review | booking_id, rating |

등록 후 서버 응답 확인:

```powershell
cd chonmuseojang
uv run python scripts/verify_kakao_webhooks.py --base-url https://chonmuseojang.vercel.app
```

스킬만 만들고 **시나리오 블록에 연결하지 않으면** 카카오톡에서 호출되지 않습니다.  
→ [`OPENBUILDER_SCENARIO.md`](OPENBUILDER_SCENARIO.md) 참고
