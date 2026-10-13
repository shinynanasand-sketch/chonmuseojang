INSERT INTO storage.buckets (id, name, public)
VALUES ('content-photos', 'content-photos', true)
ON CONFLICT (id) DO NOTHING;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'storage'
      AND tablename = 'objects'
      AND policyname = 'public read content photos'
  ) THEN
    CREATE POLICY "public read content photos"
    ON storage.objects FOR SELECT
    TO public
    USING (bucket_id = 'content-photos');
  END IF;
END $$;
