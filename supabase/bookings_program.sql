ALTER TABLE public.bookings
    ADD COLUMN IF NOT EXISTS program_key TEXT,
    ADD COLUMN IF NOT EXISTS program_label TEXT;
