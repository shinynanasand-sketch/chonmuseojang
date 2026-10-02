-- 시연용 시드 데이터 (schema.sql 실행 후 적용)
-- Supabase SQL Editor에서 실행하거나: uv run python scripts/load_demo_seed.py

INSERT INTO villages_cache (
    village_id, village_name, sido, sigungu, program_type,
    latitude, longitude, grade, trust_score
) VALUES
    ('V001', '예시 갯벌마을', '전라남도', '신안군', '갯벌체험', 34.9000, 126.1000, '으뜸촌', 82),
    ('V002', '예시 무등마을', '광주광역시', '북구', '농사체험', 35.1800, 126.9100, NULL, 65),
    ('V004', '예시 여수마을', '전남광주통합특별시', '여수시', '어촌체험', 34.7600, 127.6600, NULL, 70)
ON CONFLICT (village_id) DO UPDATE SET
    village_name = EXCLUDED.village_name,
    sido = EXCLUDED.sido,
    sigungu = EXCLUDED.sigungu,
    program_type = EXCLUDED.program_type,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude,
    grade = EXCLUDED.grade,
    trust_score = EXCLUDED.trust_score,
    synced_at = NOW();

-- 동기화는 registration_code를 덮어쓰지 않는다. 비어 있을 때만 시연 코드를 넣는다.
UPDATE villages_cache
SET registration_code = 'GB-001'
WHERE village_id = 'V001' AND registration_code IS NULL;

INSERT INTO operators (village_id, kakao_user_id, login_id, operator_name, is_active)
VALUES
    ('V001', 'kakao_owner_v001', 'owner_v001', 'V001 운영자', TRUE),
    ('V002', 'kakao_owner_v002', 'owner_v002', 'V002 운영자', TRUE)
ON CONFLICT (village_id) DO UPDATE SET
    kakao_user_id = EXCLUDED.kakao_user_id,
    login_id = EXCLUDED.login_id,
    operator_name = EXCLUDED.operator_name,
    is_active = EXCLUDED.is_active;
