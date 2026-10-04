# 카카오톡 실연동 가이드 (Step 6)

배포 URL: **https://chonmuseojang.vercel.app**

시연 로그인·예약 번호·카카오 ID는 [`docs/OPERATOR_DEMO.md`](docs/OPERATOR_DEMO.md)를 봅니다.

> **보류:** 승인·후기 봇테스트와 개발채널 재연결은 나중에 한다. `/kakao/*` 코드와 V001 `kakao_user_id=206405` 매핑은 유지한다. 공공데이터·TourAPI, 예약·후기 저장, 운영자 웹, 홍보문구(FR-11)는 끝났습니다. 카카오 수동 시연은 재개 요청이 있을 때 합니다.

## 사전 조건

- [x] Vercel HTTPS 배포 (`chonmuseojang.vercel.app`)
- [ ] Supabase Security Advisor에 RLS Disabled가 있으면 [`supabase/enable_rls.sql`](supabase/enable_rls.sql) Run
- [x] `.env.local` / Vercel Production: `KAKAO_REST_API_KEY`, `KAKAO_ADMIN_KEY`, `KAKAO_EVENT_API_URL`
- [x] 오픈빌더 웹훅 3개 URL 등록
- [x] 프로덕션 웹훅 자동 검증 PASS (`scripts/verify_kakao_webhooks.py`)
- [x] 스킬서버로 전송 → `올바른 스킬 서버 응답` 확인됨 (예약 simpleText)
- [x] 봇테스트 예약 동작 확인 (파라미터 없으면 방문일·인원 안내)
- [x] 실 `kakao_user_id` → `operators` 매핑 (V001=`206405`)
- [ ] 개발채널 재연결 (사이드바에 「연결된 채널 없음」이면)
- [ ] 봇테스트/카카오톡: **승인** → **후기** 최소 시연 (아래 4절)


## 1. 채널·오픈빌더 체크리스트

1. [카카오톡 채널](https://center-pf.kakao.com) 개설 (개인 자격)
2. [오픈빌더](https://i.kakao.com) 챗봇 생성·승인
3. 스킬에 아래 **고정 URL** 등록 ([상세](docs/OPENBUILDER_WEBHOOKS.md)):

| 스킬 | URL |
|---|---|
| 예약 접수 | `https://chonmuseojang.vercel.app/kakao/booking` |
| 승인/거절 | `https://chonmuseojang.vercel.app/kakao/approve` |
| 후기 등록 | `https://chonmuseojang.vercel.app/kakao/review` |

4. **시나리오 01**에 예약/승인·거절/후기 **블록을 만들고 스킬 연결** ([상세](docs/OPENBUILDER_SCENARIO.md))  
   → 스킬 목록 **적용 블록수**가 0이 아니어야 함 (탈출 블록에 넣지 말 것)
5. 스킬 파라미터 예시:
   - booking: `visit_date`, `num_people`
   - approve: `booking_id`, `decision` (`approve` / `reject`)
   - review: `booking_id`, `rating` (+ 발화=후기 본문)

## 2. 운영자 등록 (FR-15)

시연용 시드에는 `kakao_owner_v001` / `kakao_owner_v002`가 있습니다.  
실채널에서는 본인 카카오 사용자 ID로 교체하세요.

```sql
-- supabase/operators_kakao_map.sql 참고
UPDATE operators
SET kakao_user_id = '실제_카카오_사용자_ID',
    operator_name = '이장님',
    is_active = TRUE
WHERE village_id = 'V001';
```

## 3. 이벤트 API

이번 단계의 예약·승인 경로는 이벤트 API를 호출하지 않습니다.  
운영자는 `예약 현황`, 관광객은 `내 예약`으로 `POST /kakao/booking`에서 확인합니다.  
발송 함수는 [`services/kakao_client.py`](services/kakao_client.py)에 다음 단계용으로 남아 있습니다.

## 4. 시연 흐름

1. 관광객: 예약 → `/kakao/booking` (예: `2026-09-30 2명 예약`) → 예약번호 확인. 상태는 `내 예약`으로 본다
2. 운영자(`206405`): 승인/거절 → `/kakao/approve`. 마을 예약은 `예약 현황`으로 본다
   - 「등록된 운영자만…」이면 `user.id`와 DB 매핑 불일치
3. 관광객: 후기 → `/kakao/review` → 「후기 등록 완료」

**서버 E2E (자동):** 예약→승인→후기 PASS.  
**수동 최소 시연:** 승인 1회 + 후기 1회면 Step 6 마무리에 충분합니다.  
개발채널이 없으면 **봇테스트**로 위 순서를 돌려도 됩니다.


## 5. 자동 검증

```powershell
cd chonmuseojang
uv run pytest tests/test_kakao_booking.py tests/test_kakao_approve.py tests/test_kakao_review.py -q
uv run python scripts/verify_kakao_webhooks.py
uv run python scripts/verify_kakao_webhooks.py --base-url https://chonmuseojang.vercel.app
```
