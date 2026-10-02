-- 실채널 연동 시 운영자 카카오 ID 매핑 (FR-15)
-- SQL Editor에서 kakao_user_id만 본인 ID로 바꿔 실행하세요.
--
-- ID 확인 순서:
-- 1) 오픈빌더 봇테스트 또는 개발채널 채팅 1회
-- 2) 왼쪽 「작업이력」 → 요청 JSON → userRequest.user.id
-- 3) 아래 '실제_카카오_사용자_ID'를 그 값으로 교체 후 Run
--
-- 주의: 스킬 테스트(스킬서버로 전송)의 accountId(예: 536285)는
--       실 카카오톡 botUserKey와 다를 수 있습니다. 작업이력 ID를 쓰세요.
--
-- 현재 DB 시드: kakao_owner_v001 (V001), kakao_owner_v002 (V002)
-- 실 ID가 아직 없으면 이 파일을 실행하지 마세요 (시드로 서버 E2E는 가능).

UPDATE operators
SET kakao_user_id = '206405',
    operator_name = '이장님',
    is_active = TRUE
WHERE village_id = 'V001';

-- 확인
SELECT village_id, kakao_user_id, operator_name, is_active FROM operators ORDER BY village_id;
