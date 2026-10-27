-- 체험객 달력 예약. Supabase SQL Editor에서 한 번 실행한다.
-- 정책 없음 = anon/authenticated 거부. service_role은 RLS 우회.

ALTER TABLE public.bookings
    ADD COLUMN IF NOT EXISTS visit_time TEXT;

CREATE TABLE IF NOT EXISTS guest_book_links (
    token TEXT PRIMARY KEY,
    village_id TEXT NOT NULL REFERENCES villages_cache(village_id),
    customer_kakao_id TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_guest_book_links_village ON guest_book_links(village_id);

ALTER TABLE public.guest_book_links ENABLE ROW LEVEL SECURITY;
