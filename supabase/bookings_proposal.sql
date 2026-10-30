-- 예약 일정 변경 제안. Supabase SQL Editor에서 한 번 실행한다.
-- 정책 없음 = anon/authenticated 거부. service_role은 RLS 우회.

ALTER TABLE public.bookings
    ADD COLUMN IF NOT EXISTS proposed_visit_date DATE;

ALTER TABLE public.bookings
    ADD COLUMN IF NOT EXISTS proposed_visit_time TEXT;
