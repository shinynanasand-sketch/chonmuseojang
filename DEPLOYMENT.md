# Vercel 배포 및 운영 체크리스트 (DOR 요약)

상세 설정: [SETUP.md](SETUP.md)

## 최초 배포

1. `uv sync` 및 `uv run pytest` 로컬 통과 확인
2. GitHub 저장소 `chonmuseojang`에 푸시
3. Vercel New Project → 저장소 연결, 진입점 `api/index.py`
4. Environment Variables: `.env.example` 키 전체 등록
5. Supabase SQL Editor에서 `supabase/schema.sql` 실행
6. 배포 후 `/` 홈, `/api/villages` JSON 응답 확인
7. 네이버 서치어드바이저에 `https://chonmuseojang.vercel.app`이 등록되어 있다. 홈 `<head>`에 확인 태그가 있고, 제출한 사이트맵은 `https://chonmuseojang.vercel.app/sitemap.xml`이다. 담는 주소는 `/`, `/recommend`, `/map`, `/nearby`, `/villages`, `/dashboard`다. `/robots.txt`는 운영자 화면, 달력 토큰, 개발 화면을 수집하지 않는다
8. `curl -H "Authorization: Bearer {CRON_SECRET}" https://{배포URL}/api/cron/sync` 수동 동기화
9. Vercel 대시보드 Cron Jobs 등록 확인 (`vercel.json`)

## 기능 추가 시

1. `uv run pytest` 통과
2. Git push → Vercel 자동 배포
3. 배포 URL에서 변경 기능 확인
