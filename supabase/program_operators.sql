-- 기존 DB: 마을당 운영자 1명 제약을 역할 제약으로 바꾼다.
-- 마을 운영자는 마을당 1명, 체험 담당은 체험당 1명.
-- 이미 같은 마을에 운영자가 둘 이상이면 아래 유니크 인덱스 생성이 실패한다.

ALTER TABLE operators DROP CONSTRAINT IF EXISTS operators_village_id_key;

ALTER TABLE operators ADD COLUMN IF NOT EXISTS role TEXT;
ALTER TABLE operators ADD COLUMN IF NOT EXISTS program_key TEXT;

UPDATE operators SET role = 'village' WHERE role IS NULL OR btrim(role) = '';

ALTER TABLE operators ALTER COLUMN role SET DEFAULT 'village';
ALTER TABLE operators ALTER COLUMN role SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'operators_role_check'
    ) THEN
        ALTER TABLE operators
            ADD CONSTRAINT operators_role_check CHECK (role IN ('village', 'program'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'operators_role_program_key'
    ) THEN
        ALTER TABLE operators
            ADD CONSTRAINT operators_role_program_key CHECK (
                (role = 'village' AND program_key IS NULL)
                OR (role = 'program' AND program_key IS NOT NULL)
            );
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS operators_one_village_role
    ON operators (village_id) WHERE role = 'village';
CREATE UNIQUE INDEX IF NOT EXISTS operators_one_program_role
    ON operators (village_id, program_key) WHERE role = 'program';

CREATE TABLE IF NOT EXISTS program_notes (
    village_id TEXT NOT NULL REFERENCES villages_cache(village_id),
    program_key TEXT NOT NULL,
    label TEXT NOT NULL,
    body TEXT NOT NULL,
    updated_by INTEGER REFERENCES operators(operator_id),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (village_id, program_key)
);

CREATE TABLE IF NOT EXISTS experience_calendar (
    calendar_id SERIAL PRIMARY KEY,
    village_id TEXT NOT NULL REFERENCES villages_cache(village_id),
    program_key TEXT NOT NULL,
    label TEXT NOT NULL,
    visit_date DATE NOT NULL,
    group_name TEXT NOT NULL,
    num_people INTEGER NOT NULL,
    note TEXT,
    created_by INTEGER REFERENCES operators(operator_id),
    UNIQUE (village_id, program_key, visit_date, group_name)
);

ALTER TABLE public.program_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.experience_calendar ENABLE ROW LEVEL SECURITY;
