# Vercel 배포 스크립트 (Step 5)

PowerShell에서 `chonmuseojang` 디렉터리 기준으로 실행합니다.

## 1. GitHub 저장소 (최초 1회)

```powershell
cd chonmuseojang
git init
git add .
git commit -m "Initial commit: 체험마을 AI사무장 MVP"
gh repo create chonmuseojang --public --source=. --remote=origin --push
```

이미 원격이 있으면:

```powershell
git remote add origin https://github.com/{계정}/chonmuseojang.git
git push -u origin main
```

## 2. Vercel 프로젝트

[Vercel 대시보드](https://vercel.com/new) → GitHub `chonmuseojang` 연결

- **Root Directory:** `.` (저장소 루트가 chonmuseojang)
- **Framework:** Other
- **Build Command:** (비움)
- **Output Directory:** (비움)
- 진입점: `api/index.py` (`vercel.json` 참고)

또는 CLI:

```powershell
npx vercel@latest login
npx vercel@latest --prod
```

## 3. 환경 변수

Vercel Project → Settings → Environment Variables에 `.env.example` 키 전체 등록  
(특히 `SUPABASE_*`, `CRON_SECRET`, `PUBLIC_DATA_*`)

## 4. 배포 후 확인

```powershell
curl https://{배포URL}/
curl https://{배포URL}/api/villages
curl -H "Authorization: Bearer {CRON_SECRET}" https://{배포URL}/api/cron/sync
```

Cron: Vercel 대시보드 → Cron Jobs에서 `vercel.json` 스케줄 확인
