-- 체험객 예약의 단체 이름. Supabase SQL Editor에서 한 번 실행한다.
-- 정책 없음 = anon/authenticated 거부. service_role은 RLS 우회.

ALTER TABLE public.bookings
    ADD COLUMN IF NOT EXISTS group_name TEXT;
