# 카카오톡 실연동 가이드 (Step 6)

## 사전 조건

- Vercel 배포 URL 확보 (HTTPS 필수)
- `.env` / Vercel 환경변수:
  - `KAKAO_REST_API_KEY`
  - `KAKAO_ADMIN_KEY` (이벤트 API 발송용)
  - `KAKAO_EVENT_API_URL` (기본값 설정됨)

## 1. 채널·오픈빌더

1. [카카오톡 채널](https://center-pf.kakao.com) 개설 (개인 자격)
2. [오픈빌더](https://i.kakao.com) 챗봇 생성·승인
3. 스킬 블록에 웹훅 URL 등록:

| 스킬 | URL |
|---|---|
| 예약 접수 | `https://{배포URL}/kakao/booking` |
| 승인/거절 | `https://{배포URL}/kakao/approve` |
| 후기 등록 | `https://{배포URL}/kakao/review` |

## 2. 운영자 등록

Supabase `operators` 테이블에 카카오 사용자 ID와 `village_id` 1:1 매핑:

```sql
INSERT INTO operators (village_id, kakao_user_id, display_name, is_active)
VALUES ('V001', '실제_카카오_사용자_ID', '이장님', TRUE)
ON CONFLICT (village_id) DO UPDATE SET kakao_user_id = EXCLUDED.kakao_user_id;
```

## 3. 이벤트 API

[`services/kakao_client.py`](services/kakao_client.py)에서 `KAKAO_ADMIN_KEY` 설정 시 예약·승인 알림이 발송됩니다.  
키가 없으면 로그만 남기고 스킬 응답은 정상 동작합니다.

## 4. 시연 흐름

1. 여행객: 카카오톡에서 예약 → `/kakao/booking`
2. 운영자: 승인/거절 → `/kakao/approve` (자기 마을 예약만)
3. 여행객: 후기 → `/kakao/review`

## 5. 로컬 테스트

```powershell
uv run pytest tests/test_kakao_booking.py tests/test_kakao_approve.py tests/test_kakao_review.py -v
```
