# 다음 단계 설정 가이드

코드·테스트는 완료되었습니다. 아래 순서대로 **실데이터 연동**을 진행하세요.

## Step 1 — `.env` / `.env.local` 확인

로컬은 `.env` 또는 `.env.local`을 사용합니다 (`config.py`가 둘 다 로드).  
커밋하지 마세요 (`.gitignore` 등록됨).

```powershell
cd chonmuseojang
uv run python scripts/check_env.py
```

**필수 입력:** `SUPABASE_SERVICE_ROLE_KEY`  
Supabase 대시보드 → Project Settings → API → `service_role` (secret)  
프로젝트 URL 예: `https://ymdgbdnnafhdgzhtztmr.supabase.co`

공공데이터 키는 `PUBLIC_DATA_SERVICE_KEY` 또는 `PUBLIC_DATA_API_KEY` 모두 인식합니다.

## Step 2 — Supabase 스키마

1. [Supabase SQL Editor](https://supabase.com/dashboard) 열기
2. [`supabase/schema.sql`](supabase/schema.sql) 전체 실행 (말미에 RLS ENABLE 포함)
3. [`supabase/seed.sql`](supabase/seed.sql) 실행 (시연용 마을·운영자)

이미 스키마만 적용한 프로젝트에서 Security Advisor에 **RLS Disabled**가 보이면  
[`supabase/enable_rls.sql`](supabase/enable_rls.sql)을 SQL Editor에서 한 번 실행하세요.  
(`Run without RLS`로 테이블을 만든 경우. 앱은 `service_role`이라 동작은 그대로입니다.)

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

저장소: https://github.com/shinynanasand-sketch/chonmuseojang

[`DEPLOYMENT.md`](DEPLOYMENT.md) 및 [`scripts/deploy_vercel.md`](scripts/deploy_vercel.md) 참고:

1. GitHub 저장소: https://github.com/shinynanasand-sketch/chonmuseojang (푸시 완료)
2. Vercel 프로덕션: https://chonmuseojang.vercel.app
3. Environment Variables에 `.env` 키 전체 등록
4. 배포 후 Cron 동기화 수동 1회 테스트

## Step 6 — 카카오 실연동

[`KAKAO_SETUP.md`](KAKAO_SETUP.md) 참고
