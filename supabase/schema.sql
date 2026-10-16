-- Supabase schema (TRD 8장, DDD)
-- Run in Supabase SQL Editor

CREATE TABLE IF NOT EXISTS villages_cache (
    village_id TEXT PRIMARY KEY,
    village_name TEXT NOT NULL,
    sido TEXT,
    sigungu TEXT NOT NULL,
    program_type TEXT,
    program_name TEXT,
    address TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    facilities TEXT,
    representative_name TEXT,
    phone TEXT,
    homepage_url TEXT,
    grade TEXT,
    trust_score NUMERIC DEFAULT 0,
    registration_code TEXT,
    synced_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_villages_sigungu ON villages_cache(sigungu);
CREATE INDEX IF NOT EXISTS idx_villages_program_type ON villages_cache(program_type);

CREATE TABLE IF NOT EXISTS operators (
    operator_id SERIAL PRIMARY KEY,
    village_id TEXT NOT NULL REFERENCES villages_cache(village_id),
    kakao_user_id TEXT NOT NULL UNIQUE,
    login_id TEXT UNIQUE,
    password_hash TEXT,
    operator_name TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    registered_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMP,
    role TEXT NOT NULL DEFAULT 'village' CHECK (role IN ('village', 'program')),
    program_key TEXT,
    CONSTRAINT operators_role_program_key CHECK (
        (role = 'village' AND program_key IS NULL)
        OR (role = 'program' AND program_key IS NOT NULL)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS operators_one_village_role
    ON operators (village_id) WHERE role = 'village';
CREATE UNIQUE INDEX IF NOT EXISTS operators_one_program_role
    ON operators (village_id, program_key) WHERE role = 'program';

CREATE INDEX IF NOT EXISTS idx_operators_kakao ON operators(kakao_user_id);

CREATE TABLE IF NOT EXISTS bookings (
    booking_id SERIAL PRIMARY KEY,
    village_id TEXT NOT NULL REFERENCES villages_cache(village_id),
    customer_kakao_id TEXT,
    customer_name TEXT,
    visit_date DATE,
    num_people INTEGER,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'rejected')),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bookings_village ON bookings(village_id);
CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(status);

CREATE TABLE IF NOT EXISTS reviews (
    review_id SERIAL PRIMARY KEY,
    village_id TEXT NOT NULL REFERENCES villages_cache(village_id),
    booking_id INTEGER REFERENCES bookings(booking_id),
    customer_kakao_id TEXT,
    rating INTEGER CHECK (rating BETWEEN 1 AND 5),
    comment TEXT,
    photo_url TEXT,
    sentiment TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reviews_village ON reviews(village_id);

CREATE TABLE IF NOT EXISTS contents (
    content_id SERIAL PRIMARY KEY,
    village_id TEXT NOT NULL REFERENCES villages_cache(village_id),
    operator_id INTEGER REFERENCES operators(operator_id),
    content_type TEXT NOT NULL,
    title TEXT,
    body TEXT NOT NULL,
    photo_url TEXT,
    is_public BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_contents_village ON contents(village_id);

CREATE TABLE IF NOT EXISTS village_program_status (
    village_id TEXT NOT NULL REFERENCES villages_cache(village_id),
    program_key TEXT NOT NULL,
    label TEXT NOT NULL,
    is_operating BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (village_id, program_key)
);

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
    note TEXT,
    created_by INTEGER REFERENCES operators(operator_id),
    UNIQUE (village_id, program_key, visit_date)
);

CREATE TABLE IF NOT EXISTS sync_logs (
    log_id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    total_fetched INTEGER,
    total_filtered INTEGER,
    status TEXT,
    message TEXT,
    executed_at TIMESTAMP DEFAULT NOW()
);

-- RLS: anon/authenticated 기본 거부. FastAPI는 service_role로 우회 접근.
ALTER TABLE public.villages_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.operators ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bookings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.contents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.village_program_status ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.program_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.experience_calendar ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sync_logs ENABLE ROW LEVEL SECURITY;
