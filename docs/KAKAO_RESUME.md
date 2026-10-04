# 카카오 연동 재개

카카오 수동 시연은 보류합니다. 스킬 서버 코드와 운영자 매핑은 유지합니다. 웹·공공데이터를 먼저 진행한 뒤, 아래 순서로 다시 시작합니다.

카카오 사용자 ID의 수집·사용 범위는 [`PRIVACY_KAKAO_ID.md`](PRIVACY_KAKAO_ID.md)를 봅니다. 시연 로그인·예약 번호·카카오 ID는 [`OPERATOR_DEMO.md`](OPERATOR_DEMO.md)를 봅니다. 상세 설정은 [`../KAKAO_SETUP.md`](../KAKAO_SETUP.md), 시나리오 블록은 [`OPENBUILDER_SCENARIO.md`](OPENBUILDER_SCENARIO.md), 웹훅 URL은 [`OPENBUILDER_WEBHOOKS.md`](OPENBUILDER_WEBHOOKS.md)를 봅니다.

## 이미 된 것

- 배포: `https://chonmuseojang.vercel.app`
- 스킬 URL (삭제하지 않음)
  - 질문 `https://chonmuseojang.vercel.app/kakao/ask`
  - 예약 `https://chonmuseojang.vercel.app/kakao/booking`
  - 승인 `https://chonmuseojang.vercel.app/kakao/approve`
  - 후기 `https://chonmuseojang.vercel.app/kakao/review`
- 질문 스킬: 등록 운영자면 자기 마을과 주변정보만, 그 외에는 광주·전남 비교 추천. 오픈빌더 블록의 스킬 URL을 `/kakao/ask`로 두면 사용자 발화가 그대로 질문입니다.
- 스킬 응답은 `simpleText` (한 줄). 스킬서버로 전송 시 「올바른 스킬 서버 응답」 확인됨
- 예약 봇테스트 동작 확인 (방문일·인원이 없으면 안내 문구)
- V001 운영자 `kakao_user_id=206405` (`operators_kakao_map.sql` 적용됨)
- 웹 로그인 `owner_v001`. 시연 예약은 1번 대기(2026-12-01, 2명), 2번 승인(2026-12-15, 3명). 후기는 2번에 별점 4, `시연 후기입니다`. `scripts/load_demo_fixtures.py`를 다시 실행해도 이 행은 늘지 않고, `kakao_user_id`는 바꾸지 않는다. `load_demo_seed.py`는 카카오 ID를 시드 값으로 덮으므로 다시 실행하지 않는다.

## 보류 중인 것

- 오픈빌더 승인·후기 봇테스트
- 개발채널 재연결 (사이드바에 「연결된 채널 없음」이면)
- 카카오톡 실기기 시연

## 다시 시작할 때

1. 오픈빌더에서 개발채널을 다시 연결합니다.
2. 예약 블록으로 예약번호를 받습니다. 예: `2026-09-30 2명 예약`
3. 같은 사용자로 승인 1회. 예약번호와 `decision=approve`. 대기 중인 시연 예약은 1번이다.
4. 후기 1회. 예약번호와 별점.
5. 「등록된 운영자만 승인/거절할 수 있습니다」가 나오면 `userRequest.user.id`를 작업 요청 JSON에서 복사해 `operators.kakao_user_id`와 맞춥니다. 스킬 응답 화면에는 이 ID가 없습니다.
