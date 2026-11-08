-- 기존 DB: 체험 담당이 여러 체험을 맡도록 배정 표를 만든다.
-- 체험 하나는 담당 한 명. 담당이 지워지면 그 배정도 지운다.
-- 권한은 operators.program_key가 아니라 이 표를 본다.

CREATE TABLE IF NOT EXISTS operator_programs (
    village_id TEXT NOT NULL REFERENCES villages_cache(village_id),
    program_key TEXT NOT NULL,
    label TEXT NOT NULL,
    operator_id INTEGER NOT NULL REFERENCES operators(operator_id) ON DELETE CASCADE,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (village_id, program_key)
);

CREATE INDEX IF NOT EXISTS idx_operator_programs_operator ON operator_programs(operator_id);

INSERT INTO operator_programs (village_id, program_key, label, operator_id)
SELECT village_id, program_key, program_key, operator_id
FROM operators
WHERE role = 'program' AND program_key IS NOT NULL
ON CONFLICT (village_id, program_key) DO NOTHING;

ALTER TABLE operators DROP CONSTRAINT IF EXISTS operators_role_program_key;
ALTER TABLE operators
    ADD CONSTRAINT operators_role_program_key CHECK (
        (role = 'village' AND program_key IS NULL)
        OR role = 'program'
    );

DROP INDEX IF EXISTS operators_one_program_role;

ALTER TABLE public.operator_programs ENABLE ROW LEVEL SECURITY;
