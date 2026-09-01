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
    synced_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_villages_sigungu ON villages_cache(sigungu);
CREATE INDEX IF NOT EXISTS idx_villages_program_type ON villages_cache(program_type);

CREATE TABLE IF NOT EXISTS operators (
    operator_id SERIAL PRIMARY KEY,
    village_id TEXT NOT NULL UNIQUE REFERENCES villages_cache(village_id),
    kakao_user_id TEXT UNIQUE,
    login_id TEXT UNIQUE,
    password_hash TEXT,
    display_name TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    last_login_at TIMESTAMP
);

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
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_contents_village ON contents(village_id);

CREATE TABLE IF NOT EXISTS sync_logs (
    log_id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    total_fetched INTEGER,
    total_filtered INTEGER,
    status TEXT,
    message TEXT,
    executed_at TIMESTAMP DEFAULT NOW()
);
