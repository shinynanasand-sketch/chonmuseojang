-- Security Advisor "RLS Disabled in Public" 해소용 (기존 DB에 1회 실행)
-- 정책 없음 = anon/authenticated 거부. service_role은 RLS 우회.

ALTER TABLE public.villages_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.operators ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bookings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.contents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sync_logs ENABLE ROW LEVEL SECURITY;
