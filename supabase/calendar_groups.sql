-- 이미 있는 experience_calendar에 단체와 인원을 더한다.
-- 같은 체험·날짜·단체는 1건이다. 단체가 다르면 같은 날도 별도 일정이다.

ALTER TABLE public.experience_calendar
    ADD COLUMN IF NOT EXISTS group_name TEXT,
    ADD COLUMN IF NOT EXISTS num_people INTEGER;

UPDATE public.experience_calendar
SET group_name = COALESCE(NULLIF(btrim(note), ''), '단체 미입력')
WHERE group_name IS NULL OR btrim(group_name) = '';

UPDATE public.experience_calendar
SET num_people = 0
WHERE num_people IS NULL;

ALTER TABLE public.experience_calendar
    ALTER COLUMN group_name SET NOT NULL,
    ALTER COLUMN num_people SET NOT NULL;

ALTER TABLE public.experience_calendar
    DROP CONSTRAINT IF EXISTS experience_calendar_village_id_program_key_visit_date_key;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'experience_calendar_village_program_date_group_key'
          AND conrelid = 'public.experience_calendar'::regclass
    ) THEN
        ALTER TABLE public.experience_calendar
            ADD CONSTRAINT experience_calendar_village_program_date_group_key
            UNIQUE (village_id, program_key, visit_date, group_name);
    END IF;
END $$;
