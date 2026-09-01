# 다음 단계 설정 가이드

코드·테스트는 완료되었습니다. 아래 순서대로 **실데이터 연동**을 진행하세요.

## Step 1 — `.env` 확인

[`chonmuseojang/.env`](.env) 파일이 생성되어 있습니다.

```powershell
cd chonmuseojang
uv run python scripts/check_env.py
```

**필수 입력:** `SUPABASE_SERVICE_ROLE_KEY`  
Supabase 대시보드 → Project Settings → API → `service_role` (secret)

## Step 2 — Supabase 스키마

1. [Supabase SQL Editor](https://supabase.com/dashboard) 열기
2. [`supabase/schema.sql`](supabase/schema.sql) 전체 실행
3. [`supabase/seed.sql`](supabase/seed.sql) 실행 (시연용 마을·운영자)

또는 로컬 시드 (인메모리 또는 Supabase 연결 시):

```powershell
uv run python scripts/load_demo_seed.py
```

## Step 3 — 첫 동기화

공공 API 키가 있으면 `.env`에 `PUBLIC_DATA_SERVICE_KEY`, `PUBLIC_DATA_VILLAGE_ENDPOINT` 설정 후:

```powershell
uv run python scripts/manual_sync.py
```

API 키가 없으면 시연 시드 폴백:

```powershell
uv run python scripts/manual_sync.py --demo-only
```

## Step 4 — 시연 경로 점검

```powershell
uv run python scripts/verify_demo.py
uv run pytest -v
```

## Step 5 — Vercel 배포

[`DEPLOYMENT.md`](DEPLOYMENT.md) 참고:

1. GitHub에 `chonmuseojang` 푸시 (`.env` 제외)
2. Vercel → New Project → `api/index.py` 진입점
3. Environment Variables에 `.env` 키 전체 등록
4. 배포 후 Cron 동기화 수동 1회 테스트

## Step 6 — 카카오 실연동

[`KAKAO_SETUP.md`](KAKAO_SETUP.md) 참고
