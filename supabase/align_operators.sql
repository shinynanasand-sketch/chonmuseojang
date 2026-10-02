-- 기존 DB를 문서 스키마에 맞춘다.
-- villages_cache.registration_code, operators.operator_name / registered_at
-- kakao_user_id는 비어 있는 행이 없을 때만 NOT NULL로 올린다.

ALTER TABLE villages_cache ADD COLUMN IF NOT EXISTS registration_code TEXT;

ALTER TABLE operators ADD COLUMN IF NOT EXISTS operator_name TEXT;
ALTER TABLE operators ADD COLUMN IF NOT EXISTS registered_at TIMESTAMP;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'operators' AND column_name = 'display_name'
    ) THEN
        UPDATE operators
        SET operator_name = display_name
        WHERE operator_name IS NULL AND display_name IS NOT NULL;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'operators' AND column_name = 'created_at'
    ) THEN
        UPDATE operators
        SET registered_at = created_at
        WHERE registered_at IS NULL AND created_at IS NOT NULL;
    END IF;
END $$;

UPDATE operators SET operator_name = '운영자' WHERE operator_name IS NULL;
UPDATE operators SET registered_at = NOW() WHERE registered_at IS NULL;

ALTER TABLE operators ALTER COLUMN operator_name SET NOT NULL;
ALTER TABLE operators ALTER COLUMN registered_at SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM operators WHERE kakao_user_id IS NULL) THEN
        ALTER TABLE operators ALTER COLUMN kakao_user_id SET NOT NULL;
    END IF;
END $$;
