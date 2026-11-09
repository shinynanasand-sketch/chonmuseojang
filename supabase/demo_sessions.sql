-- 발표 모드 시연 역할. 운영자 등록 행은 바꾸지 않는다.
-- 주소에는 session_id만 쓰고, 카카오 사용자 ID는 넣지 않는다.
-- Supabase SQL 편집기에서 한 번 실행한다. 없으면 역할은 그 서버 프로세스 안에서만 유지된다.

CREATE TABLE IF NOT EXISTS demo_sessions (
    session_id TEXT PRIMARY KEY,
    kakao_user_id TEXT NOT NULL UNIQUE,
    persona TEXT NOT NULL DEFAULT '',
    village_id TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS demo_booking_marks (
    booking_id INTEGER PRIMARY KEY REFERENCES bookings(booking_id) ON DELETE CASCADE,
    kakao_user_id TEXT NOT NULL
);
