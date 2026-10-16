CREATE TABLE IF NOT EXISTS village_program_status (
    village_id TEXT NOT NULL REFERENCES villages_cache(village_id),
    program_key TEXT NOT NULL,
    label TEXT NOT NULL,
    is_operating BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (village_id, program_key)
);

ALTER TABLE public.village_program_status ENABLE ROW LEVEL SECURITY;
