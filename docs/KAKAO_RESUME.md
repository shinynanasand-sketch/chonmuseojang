# 카카오 연동 재개

Phase A 블록을 카카오 비즈니스 화면에 넣을 때는 [`PHASE_A_KAKAO_INPUT.md`](PHASE_A_KAKAO_INPUT.md)를 봅니다.

스킬 서버 시연, 오픈빌더 봇테스트, 카카오톡 실기기 시연은 끝났습니다. 개발채널은 연결되어 있습니다. 비즈월렛·이벤트 API는 호출하지 않습니다.

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
- 2026-10-05 스킬 서버 호출 (오픈빌더 화면이 아님)
  - 예약 `2026-09-30` 2명, 사용자 `kakao_guest_demo` → 예약번호 3, 대기
  - 승인 예약번호 1, `decision=approve`, 사용자 `206405` → 승인 완료
  - 후기 예약번호 1, 별점 5, 발화 `시연 후기 재개` → 후기 등록 완료
- `206405`는 그날 스킬 서버 요청에 넣은 값입니다. 지금 DB의 V001 운영자 `kakao_user_id`는 그 값이 아닙니다. [`../supabase/operators_kakao_map.sql`](../supabase/operators_kakao_map.sql)은 다시 실행하지 않습니다. 새 ID 값은 이 문서에 적지 않습니다.
- 개발채널 `체험마을AI사무장` `@chonmuseojang` 연결됨. 사이드바의 「연결된 채널 없음」은 운영 채널입니다.
- 2026-10-06 오픈빌더 봇테스트
  - 승인·거절: 「등록된 운영자만 승인/거절할 수 있습니다」. 예약 상태는 바뀌지 않음
  - 후기: 등록 완료
  - 예약 6번: `2026-11-20`, 2명, 대기
- 2026-10-06 카카오톡 실기기
  - 예약 7번: `2026-12-20`, 2명, 승인
  - 후기 5번: 예약 7번, 별점 5, 발화 `후기`
  - 예약 3·4·5·6번은 대기
- 저장된 블록 파라미터: 예약 `visit_date` = `2026-12-20`, `num_people` = `2`. 승인 `booking_id` = `7`, `decision` = `approve`. 후기 `booking_id` = `7`, `rating` = `5`
- 웹 로그인 `owner_v001`: 예약 7건, 대기 4건. 1·2·7번 승인, 3·4·5·6번 대기. 신뢰도 60점, 187곳 중 1위. `scripts/load_demo_fixtures.py`를 다시 실행해도 기존 예약·후기를 지우지 않습니다. `load_demo_seed.py`는 카카오 ID를 시드 값으로 덮으므로 다시 실행하지 않습니다.

## 남은 것

- 비즈월렛
- 이벤트 API 선톡 (비즈월렛 다음)

## 오픈빌더에서 확인한 것

입력칸에는 발화만 넣습니다. 예약번호, `decision`, 사용자 ID는 입력칸에 붙이지 않습니다. 그 문장은 폴백 블록으로 갑니다.

승인 블록은 예약 7번·`approve`, 후기 블록은 예약 7번·별점 5로 저장되어 있습니다. 7번은 이미 승인이고 후기 5번도 등록되어 있습니다. 같은 발화를 다시 보내면 예약이 더 생기거나 후기가 더 붙습니다.
