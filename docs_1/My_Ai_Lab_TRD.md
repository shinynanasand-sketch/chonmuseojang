# 체험마을 AI사무장 TRD (Technical Requirements Document)

## 0. 문서 개요

| 항목 | 내용 |
|---|---|
| 문서 목적 | PRD에서 정의한 요구사항을 실제 코드 구조·API 명세·DB 설계 수준까지 구체화한 기술 문서 |
| 대상 독자 | Cursor로 직접 개발을 진행하는 비전문가 1인 개발자 (본인 참고용) |
| 관련 문서 | 체험마을 AI사무장 제안서(기획서), 체험마을 AI사무장 PRD |
| 서비스 지역 | 광주·전남 지역 한정 (전남광주통합특별시 5개구 + 22개 시·군) |
| 개발 여건 | 주 3일, 1일 1~2시간, Cursor 바이브코딩 활용 |
| 배포 환경 | Vercel(서버리스, 기존 계정 활용) + Supabase(PostgreSQL, 기존 계정 활용) |
| LLM 정책 | 멀티 LLM 지원 (Gemini/Claude/GPT 중 환경변수로 전환) |
| 패키지 관리 | uv 기반 (pyproject.toml + uv.lock), requirements.txt 미사용 |
| 버전 | v2.30 (공개 사이트는 네이버 서치어드바이저에 등록되어 있다. `site_index.py`가 `GET /sitemap.xml`과 `GET /robots.txt`를 만들고, 확인 태그는 `base.html`의 `<head>`에 있다. 관광객 홈 `GET /`는 카카오 예약 방법, 마을 운영자가 있는 마을의 이름·시군구, 공개 채널 QR을 그린다. QR은 `KAKAO_CHANNEL_URL`을 `segno`로 SVG에 넣는다. 운영자 등록 패턴은 `{village_name} {registration_code}`와 `{village_name} {registration_code} {sys.text}`이고 세 번째 파라미터는 `program_label`이다. 오픈빌더 전체 배포 v2.5. 체험 달력 조회는 `달력 열기`로 `/calendar/{token}`을 연다. `GET·POST·DELETE /api/calendar/{token}`과 `POST /api/calendar/{token}/bookings/{booking_id}`가 있다. 체험 달력은 단체와 인원이고, 체험 담당은 자기 체험만 `simpleText`로 본다. 한 마을에 마을 운영자 1명과 체험 담당을 둔다. 체험 글은 그 마을 운영자가 읽는다. 카카오 마을 추천 이유에 들어 있는 꺼진 항목은 `지금은 운영하지 않음`이다. 프로그램 운영 여부는 `village_program_status`다. promo와 마을 목록의 `programs`는 `label`·`is_operating`이다. 운영자는 `POST /api/operator/programs/status`로 담당 마을만 바꾼다. 마을 홍보 읽기는 `/village/{village_id}`와 `/api/villages/{village_id}/promo`이고 `chonmuseojang.vercel.app`에 배포되어 있다. 공개는 `POST /api/operator/contents/publish`이다. `is_public`과 `content-photos`는 적용되어 있다. Phase A 시나리오 3개·블록 6개. 홍보 사진은 `POST /kakao/ask`가 콜백 대기를 먼저 돌려주고, 같은 실행의 뒷작업이 초안을 저장한 뒤 `simpleText`를 콜백으로 보낸다. 함수 제한은 30초다. 사진 초안 예산은 15초다. 이미지 플러그인 `secureUrls`의 `http://secure.kakaocdn.net`도 받는다. 카카오 CDN 사진은 8MB·10초까지 받고, 2MB를 넘으면 jpeg로 줄인다. 목록 성공은 simpleText이고 마을 추천에는 한 줄 이유가 있다. 멀티턴·가변 품목은 Phase B로 보류됨) |

---

## 1. 기술적 목표

1. 상태 비저장(stateless) 서버리스 환경(Vercel)에서 안정적으로 동작하는 백엔드 구조를 만든다
2. 웹 화면 API와 카카오 웹훅 API를 하나의 FastAPI 애플리케이션으로 통합 운영한다
3. 특정 LLM 벤더에 종속되지 않도록 추상화된 인터페이스로 AI 기능을 구현한다
4. 공공데이터를 실시간 원천으로 삼되, 주기적 캐싱을 통해 응답 속도와 API 호출량을 최적화한다
5. 광주·전남 지역 데이터만 정확히 필터링하며, 행정구역 명칭 변경에 안전하게 대응한다
6. 개발 지식이 많지 않은 1인 개발자가 Cursor의 도움으로 유지보수할 수 있도록 계층을 단순하고 명확하게 분리한다
7. uv를 활용해 패키지 설치 속도를 높이고 의존성 버전을 명확히 고정하여, 로컬 개발 환경과 Vercel 배포 환경의 차이로 인한 오류를 최소화한다
8. 운영자(`operators`)별 `village_id` 기반 멀티테넌시를 적용하여, 운영 데이터(예약·후기·콘텐츠)가 타 마을로 유출되지 않도록 서버 단에서 강제 격리한다
9. 카카오톡 채널·챗봇은 하나다. 스킬 요청의 `userRequest.user.id`로 관광객 모드와 운영자 모드를 가른다. 이번 단계의 예약 안내는 이벤트 API로 보내지 않고, 사용자가 챗봇에 물으면 스킬 응답으로 안내한다. 비즈월렛과 이벤트 API는 이번 단계가 완료되고 성공한 다음 단계에서 구현한다

---

## 2. 전체 기술 아키텍처

### 2-1. 계층 구조

시스템은 아래와 같이 네 개의 계층으로 나뉜다.

1계층. 클라이언트 계층
- 웹 브라우저(HTML/CSS/JS 렌더링 화면)를 사용하는 관광객, 운영자, 심사위원
- 카카오톡 앱을 사용하는 관광객, 운영자

2계층. 라우팅 계층 (FastAPI, Vercel에 서버리스로 배포)
- 웹 라우터: 화면 렌더링 및 화면용 API 제공
- 카카오 라우터: 카카오 스킬 API 웹훅 수신 및 응답

3계층. 서비스 로직 계층
- AI 추천, 신뢰도 계산, 외부 API 연동, LLM 호출, 데이터 동기화 등 비즈니스 로직 전담

4계층. 데이터 계층
- Supabase(PostgreSQL): 마을 캐시 데이터, 예약, 후기 저장
- 외부 원천: 공공데이터포털 OpenAPI, 한국관광공사 TourAPI, 카카오 API

### 2-2. 요청 처리 흐름 (웹 화면 예시: AI 추천)

1. 사용자가 웹 화면에서 자연어 질문을 입력하고 전송한다
2. 브라우저의 JavaScript가 POST 방식으로 API 요청을 보낸다
3. FastAPI 웹 라우터가 요청을 받아 서비스 로직 계층의 추천 모듈을 호출한다
4. 추천 모듈은 Supabase에 캐싱된 광주·전남 마을 데이터를 조회한다
5. 조회된 데이터를 LLM 추상화 계층에 프롬프트와 함께 전달한다
6. LLM 추상화 계층은 환경변수에 설정된 제공자(Gemini/Claude/GPT 중 하나)에게 실제 API 요청을 보낸다
7. LLM의 응답을 정해진 표준 형식으로 변환하여 서비스 로직 계층에 반환한다
8. 서비스 로직 계층은 이를 화면 표시용 데이터 구조로 가공해 웹 라우터에 반환한다
9. 웹 라우터는 JSON 응답을 브라우저에 전달하고, 브라우저는 이를 카드 형태로 렌더링한다

### 2-3. 요청 처리 흐름 (카카오 웹훅 예시: 예약 접수)

1. 운영자 또는 관광객이 같은 카카오톡 채널에서 메시지를 보낸다
2. 카카오 서버가 오픈빌더에 등록된 스킬 URL로 POST 요청을 보낸다 (5초 이내 응답 필요)
3. FastAPI 카카오 라우터가 발화와 `userRequest.user.id`를 추출한다
4. `resolve_kakao_role(user.id)`가 `operators`를 조회한다. 행이 없으면 관광객 모드, 있으면 그 `village_id`의 운영자 모드다
5. 관광객의 예약 발화면 `bookings`에 상태 `pending`(대기)으로 저장한다. 운영자에게 이벤트 API 알림을 보내지 않는다
6. 카카오 라우터는 5초 안에 스킬 응답 JSON을 돌려준다. 외부 API를 부를 때는 3.5초 타임아웃과 fallback 응답을 쓴다 (7-5)

### 2-4. 요청 처리 흐름 (공공데이터 동기화)

1. Vercel Cron 또는 GitHub Actions가 정해진 시간에 동기화용 엔드포인트 또는 스크립트를 실행한다
2. public_data_sync 모듈이 공공데이터포털 OpenAPI를 호출해 전체 마을 목록을 받아온다
3. 광주·전남 지역 필터링 함수를 적용해 대상 지역 데이터만 남긴다
4. 으뜸촌 등급 등 보조 데이터를 병합한다
5. Supabase의 villages_cache 테이블에 upsert 방식으로 반영한다
6. 동기화 결과(수신 건수, 필터링 후 건수, 성공 여부)를 sync_logs 테이블에 기록한다

---

## 3. 기술 스택 상세

| 구분 | 기술 | 비고 |
|---|---|---|
| 언어 | Python 3.12 이상 | Vercel Python 런타임이 지원하는 버전 사용, .python-version 파일로 버전 고정 |
| 패키지 관리 | uv | requirements.txt 대신 pyproject.toml + uv.lock으로 의존성 관리, Vercel 빌드에서 네이티브로 지원되어 설치 속도가 빠름 |
| 웹 프레임워크 | FastAPI | ASGI 기반, Vercel 네이티브 지원 |
| ASGI 서버(로컬 개발용) | Uvicorn | 로컬 테스트 시 사용, 배포는 Vercel이 자동 처리 |
| 템플릿 엔진 | Jinja2 | HTML 서버사이드 렌더링 |
| 프론트엔드 | HTML5, CSS3, Vanilla JavaScript | 별도 프레임워크(React 등) 없이 단순 구성, 필요 시 Bootstrap 활용 |
| 지도 라이브러리 | Leaflet.js 또는 카카오맵 JS SDK | 오픈소스/무료, 위경도 마커 표시 |
| 차트 라이브러리 | Chart.js | 운영 현황 통계 시각화 |
| 데이터 검증 | Pydantic | FastAPI 기본 통합, 요청/응답 스키마 정의 |
| DB 클라이언트 | supabase-py (Supabase 공식 파이썬 클라이언트) | PostgreSQL 직접 연결 대신 Supabase REST 클라이언트 우선 사용 |
| HTTP 클라이언트 | httpx | 비동기 외부 API 호출(공공데이터, TourAPI, 카카오, LLM) |
| 배포 플랫폼 | Vercel | 서버리스 함수, 기존 계정 활용, uv 빌드 자동 인식 |
| 데이터베이스 | Supabase (PostgreSQL) | 기존 계정 활용, 무료 티어 우선 사용 |
| 스케줄러 | Vercel Cron 또는 GitHub Actions | 공공데이터 일 1회 동기화 |
| 버전관리 | Git, GitHub | Cursor와 연동, pyproject.toml과 uv.lock 함께 커밋 |
| 환경변수 관리 | python-dotenv(로컬), Vercel 프로젝트 환경변수(배포) | API 키 등 민감정보 관리 |
| 테스트 실행 | pytest (uv run pytest로 실행) | uv 가상환경 내에서 실행 |

---

## 4. 리포지토리 구조

최상위 폴더 chonmuseojang 내부는 다음과 같이 구성한다.

최상위 파일:
- main.py : FastAPI 앱 생성, 미들웨어 등록, 라우터 include
- config.py : 환경변수 로드, 지역 필터 목록, LLM 기본값, 상수 정의
- pyproject.toml : 프로젝트 메타데이터 및 의존성 정의 (uv가 관리)
- uv.lock : uv가 자동 생성하는 잠금 파일, 정확한 버전 고정 (직접 수정 금지, 커밋은 필수)
- .python-version : 사용할 파이썬 버전 명시(예: 3.12)
- .env.example : 필요한 환경변수 키 목록(값은 비움, 커밋 가능)
- .env : 실제 값이 담긴 환경변수 파일(커밋 금지, .gitignore 등록)
- vercel.json : Vercel 빌드/라우팅/크론 설정
- .gitignore : .env, __pycache__, .venv 등 제외 목록

api 폴더 (Vercel 서버리스 진입점):
- index.py : main.py의 FastAPI app 객체를 재노출(export)하는 진입 파일
- cron_sync.py : Vercel Cron이 호출할 동기화 트리거 엔드포인트

routers 폴더 (요청 라우팅만 담당, 비즈니스 로직 미포함):
- web.py : 화면 라우팅(GET) 및 화면용 API 라우팅(POST) 정의
- kakao.py : 카카오 스킬 웹훅 엔드포인트 정의
- operator.py : 운영자 전용 API(인증·대시보드·콘텐츠) 라우팅

services 폴더 (핵심 비즈니스 로직):
- llm_provider.py : LLM 추상화 클래스 및 구현체(Gemini/Claude/OpenAI), 팩토리 함수
- recommend.py : 추천 프롬프트 구성, LLM 호출, 결과 파싱
- operator_assistant.py : 운영자 AI사무장용 프롬프트 구성(단일 village_id 컨텍스트)
- auth.py : 운영자 식별(`user.id` → `village_id`), 자가 등록, 테넌트 필터 공통 헬퍼
- tourapi.py : TourAPI 호출 함수(지역기반, 위치기반), 응답 정규화
- trust_score.py : 신뢰도 점수 계산 함수
- booking.py : 예약 생성/조회/상태변경 함수
- review.py : 후기 생성/조회, 감성분석 연동 함수
- kakao_client.py : 카카오 스킬 응답 포맷. 이번 단계에서는 이벤트 API를 호출하지 않음
- kakao_home.py : 관광객 홈의 카카오 예약 안내. 마을 운영자가 있는 마을의 이름·시군구와 채널 QR만 내보낸다
- public_data_sync.py : 공공데이터 OpenAPI 호출, 지역 필터링, Supabase upsert
- supabase_client.py : Supabase 클라이언트 초기화 및 공용 쿼리 헬퍼

models 폴더 (데이터 형태 정의):
- schemas.py : Pydantic 모델(요청/응답 DTO)
- kakao_schemas.py : 카카오 스킬 요청/응답 전용 Pydantic 모델

templates 폴더 (Jinja2 HTML):
- base.html : 공통 레이아웃(헤더, 푸터, 공통 CSS/JS 로드)
- index.html : 홈 화면. 카카오 예약 안내와 채널 QR. 그 아래 시군·이름 목록
- recommend.html : AI 추천 화면
- map.html : 지도 화면
- nearby.html : 주변정보 화면
- dashboard.html : 운영 현황 화면

static 폴더:
- css/style.css : 전역 스타일
- js/main.js : 공통 스크립트
- js/recommend.js : 추천 화면 전용 스크립트(fetch 호출 등)
- js/map.js : 지도 렌더링 스크립트

tests 폴더 (가능한 범위 내 최소 테스트):
- test_recommend.py : 추천 로직 단위 테스트
- test_public_data_sync.py : 필터링 로직 단위 테스트

scripts 폴더 (수동 실행용 보조 스크립트):
- manual_sync.py : 로컬에서 수동으로 공공데이터 동기화를 실행해보는 스크립트

---

## 5. 프로젝트 설정 파일 및 uv 사용법

### 5-1. pyproject.toml 예시

```toml
[project]
name = "chonmuseojang"
version = "0.1.0"
description = "체험마을 AI사무장 - 광주전남 농촌체험마을 AI 추천 및 카카오톡 연동 서비스"
requires-python = ">=3.12"
dependencies = [
    "fastapi",
    "uvicorn[standard]",
    "jinja2",
    "pydantic",
    "httpx",
    "python-dotenv",
    "supabase",
]

[project.optional-dependencies]
dev = [
    "pytest",
]

[tool.uv]
package = false
```

### 5-2. 로컬 개발 명령어

프로젝트 초기 설정(최초 1회, pyproject.toml 기준으로 가상환경 및 의존성 설치):

```
uv sync
```

FastAPI 개발 서버 실행:

```
uv run uvicorn main:app --reload
```

패키지 추가 시(requirements.txt에 직접 추가하는 대신):

```
uv add 패키지명
```

개발 전용 패키지 추가:

```
uv add --dev pytest
```

테스트 실행:

```
uv run pytest
```

수동 동기화 스크립트 실행 예시:

```
uv run python scripts/manual_sync.py
```

### 5-3. 환경변수 명세

.env 파일에는 다음 키가 필요하다. 실제 값은 각 서비스 대시보드에서 발급받아 채운다.

```
# LLM 관련
LLM_PROVIDER=gemini
GEMINI_API_KEY=
CLAUDE_API_KEY=
OPENAI_API_KEY=

# Supabase 관련
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=

# 공공데이터포털 관련
PUBLIC_DATA_SERVICE_KEY=
PUBLIC_DATA_VILLAGE_ENDPOINT=

# 한국관광공사 TourAPI 관련
TOUR_API_SERVICE_KEY=
TOUR_API_ENDPOINT=

# 카카오 관련 (카카오 연동 단계에서 사용)
KAKAO_REST_API_KEY=
KAKAO_ADMIN_KEY=
KAKAO_EVENT_API_URL=

# 크론 보호용
CRON_SECRET=

# 기타
APP_ENV=development
```

환경변수 관리 원칙:
- .env 파일은 절대 GitHub에 커밋하지 않는다 (.gitignore에 등록)
- .env.example 파일에는 키 이름만 남기고 값은 비워둔 채로 커밋하여, 어떤 값이 필요한지 파악할 수 있게 한다
- Vercel 배포 시에는 Vercel 프로젝트 설정의 Environment Variables 메뉴에 동일한 키와 값을 등록한다
- Supabase의 service role key는 서버 사이드에서만 사용하고, 절대 프론트엔드 JS 코드에 노출하지 않는다
- CRON_SECRET은 Vercel Cron이 호출하는 동기화 엔드포인트를 외부의 임의 호출로부터 보호하기 위한 값이다

---

## 6. API 명세 (웹 화면용)

### 6-0. 관광객 홈

`templates/base.html`의 `<head>`에 네이버 서치어드바이저 확인 태그가 있다. `services/site_index.py`가 `GET /sitemap.xml`과 `GET /robots.txt`를 만든다. 사이트맵은 `/`, `/recommend`, `/map`, `/nearby`, `/villages`, `/dashboard`만 담는다. `robots.txt`는 사이트맵 주소를 알리고 `/operator`, `/calendar/`, `/guide/dev`는 수집하지 않는다. 공개 사이트 `https://chonmuseojang.vercel.app`은 서치어드바이저에 등록되어 있고 사이트맵 제출도 끝났다.

`GET /`는 `templates/index.html`을 그린다. 라우터는 `services/kakao_home.py`의 안내만 템플릿에 넣는다. 마을 번호는 `role=village`이고 활성인 운영자와 `villages_cache`의 이름·시군구만 합친다. 캐시에 없는 마을은 빠진다. 운영자 이름, 카카오 사용자 ID, 등록 코드는 읽지 않는다. QR은 `config.py`의 `KAKAO_CHANNEL_URL`(`https://pf.kakao.com/_RgZaX`)을 `segno`로 SVG에 넣는다. 그 아래 시군·이름 목록은 그대로 `GET /api/villages`로 그린다.

### 6-1. AI 추천 API

요청

```
POST /api/recommend
Content-Type: application/json

{
  "query": "아이와 갈만한 갯벌체험, 당일치기"
}
```

응답 (성공)

```
200 OK
Content-Type: application/json

{
  "status": "success",
  "results": [
    {
      "village_id": "V001",
      "village_name": "예시 갯벌마을",
      "sigungu": "신안군",
      "program_type": "갯벌체험",
      "reason": "가족 단위로 즐기기 좋은 체험형 프로그램이 마련되어 있어 추천합니다.",
      "latitude": 34.9,
      "longitude": 126.1,
      "trust_score": 82
    }
  ]
}
```

응답 (실패, 조건에 맞는 마을 없음)

```
200 OK
Content-Type: application/json

{
  "status": "empty",
  "message": "조건에 맞는 마을을 찾지 못했습니다. 검색어를 조금 더 넓혀보세요.",
  "results": []
}
```

응답 (서버 오류)

```
500 Internal Server Error
Content-Type: application/json

{
  "status": "error",
  "message": "일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
}
```

### 6-2. 마을 지도 데이터 API

요청

```
GET /api/villages?sigungu=신안군&program_type=갯벌체험
```

응답

```
200 OK
Content-Type: application/json

{
  "status": "success",
  "count": 1,
  "villages": [
    {
      "village_id": "V001",
      "village_name": "예시 갯벌마을",
      "latitude": 34.9,
      "longitude": 126.1,
      "sigungu": "신안군",
      "grade": "으뜸촌"
    }
  ]
}
```

### 6-2-1. 마을 홍보 공개

관광객 화면은 `GET /village/{village_id}`이다. 공개된 마을 목록은 `GET /villages`이고 상단 메뉴 마을 소개다. 예시 마을도 공개했으면 포함한다. 공개 읽기 API는 `GET /api/villages/{village_id}/promo`이다. 응답은 마을 이름, 시군구, 체험명, 확인된 최신 소개글, SNS 문구, 사진 주소다. 사진 주소가 `http`로 시작할 때만 화면에 사진을 넣는다. 확인된 글이 없으면 소개글과 SNS 문구는 비어 있고, 화면에는 체험명과 시군구가 남는다. 관광객 후기는 넣지 않는다.

운영자 공개는 `POST /api/operator/contents/publish`이다. Bearer 토큰의 담당 마을만 공개한다. 본문이나 쿼리의 `village_id`가 담당 마을과 다르면 403이다. 그 마을의 최신 소개글과 SNS홍보문구 한 쌍만 `is_public`이 되고, 이전 공개는 내려간다. `contents.is_public`과 `content-photos` 버킷은 적용되어 있고, 화면은 `chonmuseojang.vercel.app`에 배포되어 있다.

### 6-2-2. 프로그램 운영 여부

`program_name`을 괄호 밖 `+`와 줄바꿈으로 나눈 항목이다. 그 칸이 비어 있으면 `program_type`을 같은 방식으로 나눈다. 괄호 안의 `+`는 자르지 않는다. 상태 행이 없으면 운영 중이다.

`GET /api/villages/{village_id}/promo`와 `GET /api/villages`의 각 마을에 `programs`가 있다.

```json
"programs": [
  {"label": "자연생태체험", "is_operating": true},
  {"label": "기타(영농체험+먹거리체험)", "is_operating": false}
]
```

마을 소개는 끈 항목에 `지금은 운영하지 않음`을 붙인다. 홈 카드는 운영 중인 항목만 짧게 보여 주고, 모두 꺼져 있으면 체험명 한 줄을 보여 준다.

운영자 변경은 `POST /api/operator/programs/status`이다. 본문은 `label`, `is_operating`이다. 마을은 Bearer 토큰의 `current_operator.village_id`만 쓴다. 다른 마을 번호는 403, 그 마을 글에 없는 항목은 400이다. 저장은 `village_program_status`이고, 공공데이터 upsert는 이 표를 덮지 않는다. 적용 SQL은 `chonmuseojang/supabase/village_program_status.sql`이다. 표가 아직 없으면 공개 화면은 항목을 모두 운영 중으로 보여 주고, 저장은 503이다. 목록 조회는 `GET /api/operator/programs`이다.

### 6-3. 주변 관광정보 API

요청

```
GET /api/nearby?village_id=V001&radius=5000
```

응답

```
200 OK
Content-Type: application/json

{
  "status": "success",
  "village_id": "V001",
  "attractions": [
    {
      "title": "예시 해변",
      "addr": "전남 신안군 ...",
      "content_type": "관광지",
      "image_url": "https://example.test/beach.jpg",
      "distance_m": 1200
    }
  ],
  "restaurants": [
    {
      "title": "예시 식당",
      "addr": "전남 신안군 ...",
      "content_type": "음식점",
      "image_url": "https://example.test/food.jpg",
      "distance_m": 800
    }
  ]
}
```

### 6-4. 운영 현황 API

**관광객/공개용** (`GET /api/dashboard/summary`): 전체 마을 통계(심사·시연용). 운영 원장 상세는 포함하지 않는다.

**운영자 전용** (`GET /api/operator/dashboard`): 인증된 운영자의 `current_operator.village_id`에 한정된 예약·후기·신뢰도만 반환한다.

요청 (운영자 전용)

```
GET /api/operator/dashboard
Authorization: Bearer {operator_session_token}
```

응답 (운영자 전용)

```
200 OK
Content-Type: application/json

{
  "status": "success",
  "village_id": "V001",
  "village_name": "예시 갯벌마을",
  "sigungu": "신안군",
  "grade": "으뜸촌",
  "total_bookings": 5,
  "pending_bookings": 2,
  "confirmed_bookings": 2,
  "rejected_bookings": 1,
  "review_count": 1,
  "average_rating": 5,
  "recent_reviews": [
    {"rating": 5, "comment": "아이들이 좋아했어요"}
  ],
  "trust_score": 82
}
```

요청 (공개용, 기존)

```
GET /api/dashboard/summary
```

응답 (공개용, 기존)

```
200 OK
Content-Type: application/json

{
  "status": "success",
  "total_villages": 87,
  "total_bookings": 12,
  "pending_bookings": 3,
  "recent_reviews": [
    {"village_name": "예시 갯벌마을", "rating": 5, "comment": "아이들이 좋아했어요"}
  ],
  "top_trusted_villages": [
    {"village_name": "예시 갯벌마을", "trust_score": 82}
  ]
}
```

### 6-5. 동기화 트리거 API (Vercel Cron 전용)

요청

```
GET /api/cron/sync
Authorization: Bearer {CRON_SECRET}
```

응답

```
200 OK
Content-Type: application/json

{
  "status": "success",
  "total_fetched": 320,
  "total_filtered": 87,
  "executed_at": "2026-10-05T09:00:00Z"
}
```

이 엔드포인트는 CRON_SECRET 값을 헤더로 확인하여, 정당한 스케줄러 호출인지 검증한 뒤에만 동기화를 실행한다.

---

## 7. API 명세 (카카오 웹훅용)

카카오 스킬 API는 카카오 오픈빌더가 정한 고정 규격을 따라야 한다. 요청과 응답 모두 이 규격을 준수한다.

Phase A 시나리오는 `관광객_마을정보`, `운영자_예약관리`, `운영자_등록` 세 개다. 블록은 여섯 개다. 각각 한 발화와 한 응답이다. 목록이 있는 성공과 한 문장 결과·안내·실패는 모두 `simpleText`다. 상세는 7-0이다. 컨텍스트와 Lifespan은 바꾸지 않는다.

- `관광객_마을정보`: 마을 추천(관광객, 조건 하나, 최대 5곳), 후기 조회(관광객, 마을 이름 하나, `reviews.rating`과 `comment`)
- `운영자_예약관리`: 예약 현황 조회(운영자, 추가 파라미터 없음), 예약승인(운영자), 예약거절(운영자)
- `운영자_등록`: 운영자 등록. 호출자는 아직 `operators`에 없는 사용자다. 한 문장에 마을명과 코드

기본 시나리오의 웰컴 블록은 서비스 소개와 사용 예시, 폴백 블록은 Phase A 블록을 떠올릴 수 있는 안내로 교체했다. 탈출 블록은 그대로 둔다.

예약 접수는 여섯 블록에 없다. 멀티턴으로 받지 않는다. 방문일과 인원을 한 문장에 넣도록 안내하거나 웹 대시보드 링크로 안내하고, 그 요청에서 끝낸다. 7-2의 `basicCard`는 예약 접수 응답이고, 여섯 블록 응답으로 바꾸지 않는다.

멀티턴 대화와 가변 품목 파싱은 Phase B로 보류됨.

### 7-0. Phase A 블록 트리거와 응답

안내·실패·권한 없음과 목록이 있는 성공은 모두 `simpleText`다. `basicCard`는 7-2 예약 접수에만 쓴다. 목록은 최대 5건이다. 더 많으면 앞 5건만 넣고 제목에 최근 5건이라고 적는다. 이어지는 말풍선은 만들지 않는다. `listCard`는 이번 단계 여섯 블록 응답으로 쓰지 않는다.

스키마에 `branch_name`은 없다. 사람이 말하는 이름은 `villages_cache.village_name`이고 대표값은 `village_id`다. 마을 이름 커스텀 엔티티의 항목은 `village_name`, 대표값은 `village_id`, 스킬 파라미터 이름은 `village_id`다. 날짜는 `@sys.date`, 숫자는 `@sys.number`다. 파라미터는 필수로 두지 않는다. 값이 없으면 안내만 하고 그 요청에서 끝낸다.

- 마을 추천
  - 시나리오: `관광객_마을정보`. 역할: 관광객
  - 트리거: 조건 한 문장. 예: `아이와 갈 갯벌`
  - 엔티티: 없음. 조건은 발화 전체다. 마을 엔티티를 걸면 마을 이름이 아닌 문장이 빠진다
  - 성공: `simpleText`. 마을명, 시군구, 한 줄 추천 이유. 최대 5곳. 이유는 질문에서 맞은 말을 최대 두 개 적고, 그 마을의 프로그램명과 질문과 맞은 시설을 붙인다. 예: `갯벌·가족과 맞습니다. 조개잡이, 가족 체험장.` 겹치는 칸이 없으면 그 마을에 있는 프로그램명과 시설만 적는다. 80자 안에서 자르며 대표자, 전화번호, 등록 코드는 넣지 않는다. 그 이유에 들어 있는 꺼진 프로그램은 `라벨은 지금은 운영하지 않음`으로 바꾼다. 이유에 없는 꺼진 항목은 나열하지 않는다
  - 후보 없음: `simpleText`로 조건 완화 안내
- 후기 조회
  - 시나리오: `관광객_마을정보`. 역할: 관광객
  - 트리거: 마을 이름 하나. 예: `예시 갯벌마을 후기`
  - 엔티티: 파라미터 `village_id`. 커스텀 `village_name`, 대표값 `village_id`. 없으면 안내만 하고 종료
  - 성공: `simpleText`. 별점과 `reviews.comment`. 최대 5건
  - 마을이 없거나 후기가 없음: `simpleText`
- 운영자 등록
  - 시나리오: `운영자_등록`. 호출자는 아직 `operators`에 없는 사용자
  - 트리거: 마을명과 코드를 한 문장. 마을 운영자 예: `예시 갯벌마을 GB-001`. 체험 담당 예: `예시 갯벌마을 GB-001 갯벌체험`. 체험마다 발화를 추가하지 않는다
  - 엔티티: `village_id`는 커스텀 `village_name`의 대표값. `registration_code`는 스키마 컬럼 이름 그대로이며 `@sys.number`가 아니다. `program_label`은 `@sys.text`이고 필수 아님. 패턴은 `{village_name} {registration_code}`와 `{village_name} {registration_code} {sys.text}`다. 세 번째 칸의 파라미터 이름은 `program_label`이다. 마을명이나 코드가 없으면 안내만 하고 종료
  - 성공과 실패: `simpleText`. 목록 카드는 없음
- 예약 현황 조회
  - 시나리오: `운영자_예약관리`. 역할: 운영자
  - 트리거: 발화 `예약 현황`
  - 엔티티: 없음. 날짜 범위를 받지 않는다. `start_date`, `end_date` 컬럼은 없고 `visit_date`만 있다. 나중에 범위를 받으면 파라미터만 그 두 이름으로 나누고 둘 다 `@sys.date`, 필수 아님으로 둔다. 이번 블록에는 만들지 않는다
  - 성공: `simpleText`. 예약 번호, 대기/승인/거절, 방문일, 인원. 최대 5건
  - 예약이 없거나 관광객: `simpleText`. 관광객은 등록 안내만
- 예약승인
  - 시나리오: `운영자_예약관리`. 역할: 운영자
  - 트리거: 숫자가 있는 발화 `7번 승인`, `7번 승인해줘`, `3번 예약 승인할게요`. 숫자 없는 발화 `승인할게요`도 받는다
  - 엔티티: `booking_id`는 `@sys.number`로만 추출한다. 필수가 아니다. `decision` 파라미터는 만들지 않는다
  - 성공: `simpleText` 승인 안내
  - 번호 없음: `몇 번 예약을 승인하시겠어요? 예시: 7번 승인`만 반환하고 종료. 상태는 그대로
  - 권한 없음·다른 마을: `simpleText`
- 예약거절
  - 시나리오: `운영자_예약관리`. 역할: 운영자
  - 트리거: 숫자가 있는 발화 `7번 거절`, `7번 거절해줘`, `3번 예약 거절할게요`. 숫자 없는 발화 `거절할게요`도 받는다
  - 엔티티: `booking_id`는 `@sys.number`로만 추출한다. 필수가 아니다. `decision` 파라미터는 만들지 않는다
  - 성공: `simpleText` 거절 안내
  - 번호 없음: `몇 번 예약을 거절하시겠어요? 예시: 7번 거절`만 반환하고 종료. 상태는 그대로
  - 권한 없음·다른 마을: `simpleText`
- 홍보 사진
  - 시나리오: `운영자_예약관리`. 역할: 등록된 운영자. 블록 이름은 `홍보 사진`. 스킬은 `POST /kakao/ask`. 블록 콜백을 켠다
  - 입력: 이미지 플러그인 한 장. 주소는 `secureUrls`, `userRequest.params.media.url`, 발화가 `https` 주소 하나인 순으로 고른다. 플러그인 `secureUrls`의 `http://secure.kakaocdn.net`도 카카오 주소다. 카카오 CDN만 받는다. 카카오 호스트로 이어지는 리다이렉트는 따라가고, 받기 제한은 8MB·10초다. 2MB를 넘는 jpeg, png, webp는 2MB 이하 jpeg로 줄인 뒤 초안을 저장한다. 다른 호스트로는 넘어가지 않는다
  - 응답: 운영자의 카카오 사진과 `callbackUrl`이 있으면 첫 응답은 `useCallback: true`뿐이다. 사진 받기·글 생성·저장과 같은 `simpleText` 콜백은 그 요청의 뒷작업이다. 함수 제한은 30초다
  - 글: 담당 마을 1건과 사진만 OpenAI에 보낸다. 예산은 15초. 가격·전화번호·다른 마을은 만들지 않는다
  - 저장: `contents` 소개글·SNS 초안. 공개와 `reviews`는 바꾸지 않는다. 성공은 콜백의 `simpleText`이고 마을 화면은 웹의 공개 버튼 다음이다
  - 사진이 없거나 운영자가 아니거나 콜백 주소가 없음: 대기 없이 `simpleText` 안내만. 체험 담당도 저장하지 않는다
- 체험 글 저장
  - 시나리오: `운영자_예약관리`. 블록 이름 `체험 글 저장`. 스킬은 `POST /kakao/ask`
  - 호출자: `role=program`. 본문은 발화에서 `체험 글` 뒤를 쓴다
  - 성공: `simpleText`. `program_notes`에 자기 `program_key`만 저장한다
  - 마을 운영자·다른 체험·관광객: `simpleText` 안내만. 저장하지 않는다
- 체험 글 조회
  - 블록 이름 `체험 글 조회`. 같은 마을 마을 운영자와 체험 담당이 `program_notes`를 `simpleText` 최대 5건으로 본다
  - 다른 마을 글은 포함하지 않는다. 관광객은 안내만
- 체험 달력 등록
  - 블록 이름 `체험 달력 등록`. 호출자는 `role=village`. 발화에서 체험 이름, `visit_date`(`YYYY-MM-DD`), 단체 이름, `N명`을 읽는다. 예: `조개잡이 2026-11-01 광주소등학교 30명`
  - 성공: `experience_calendar`에 그 마을 일정 1건. 같은 체험·날짜·단체는 인원만 바꾼다. 단체가 다르면 같은 날도 별도 일정이다
  - 단체나 인원이 없으면 안내만 하고 저장하지 않는다. 체험 담당과 관광객도 안내만. 저장하지 않는다
- 체험 달력 조회
  - 블록 이름 `체험 달력 조회`. 마을 운영자는 그 마을 일정을, 체험 담당은 자기 `program_key`만 `simpleText` 최대 5건으로 본다. 한 줄은 체험 이름, 날짜, 단체, `N명`. 운영자에게는 `달력 열기`가 붙고 `GET /calendar/{token}`을 연다. 주소에 카카오 사용자 ID는 없다. 관광객 화면에는 넣지 않는다
  - 달력 API: `GET /api/calendar/{token}`은 토큰 운영자의 마을 일정과 예약이다. `POST /api/calendar/{token}`은 일정 등록, `DELETE /api/calendar/{token}`은 일정 삭제, `POST /api/calendar/{token}/bookings/{booking_id}`는 승인·거절이다. 쓰기는 `role=village`만 한다. 체험 담당은 자기 체험 일정과 예약만 읽고, 등록·삭제·승인·거절은 403이다. 체험 이름 예약은 그 날짜에 예약번호와 대기로 보인다. 이름이 없으면 `체험 미정`이며 마을 운영자 달력에만 나온다. 다른 마을 예약번호는 403이다

### 7-1. 카카오 요청 공통 구조 (카카오 → 우리 서버)

```
POST /kakao/booking
Content-Type: application/json

{
  "intent": {"id": "...", "name": "예약신청"},
  "userRequest": {
    "utterance": "9월 20일 3명 예약할게요",
    "user": {"id": "kakao_user_id_abc123"}
  },
  "action": {
    "name": "booking_action",
    "params": {
      "visit_date": "2026-09-20",
      "num_people": "3"
    }
  }
}
```

### 7-2. 예약 접수 응답 (우리 서버 → 카카오, 5초 이내)

```
200 OK
Content-Type: application/json

{
  "version": "2.0",
  "template": {
    "outputs": [
      {
        "basicCard": {
          "title": "예약이 접수되었습니다",
          "description": "예약번호 12번으로 접수되었습니다. 상태는 '내 예약'으로 확인할 수 있습니다.",
          "buttons": [
            {"action": "message", "label": "내 예약", "messageText": "내 예약"}
          ]
        }
      }
    ]
  }
}
```

### 7-3. 예약승인 블록

`운영자_예약관리`의 예약승인이다. 운영자용 단일 턴이다. 예약거절과 다른 블록이다. `decision` 파라미터는 없다. 승인인 이유는 이 블록이 호출됐기 때문이다.

오픈빌더에서 `booking_id`는 `@sys.number`다. 필수 파라미터가 아니다. 발화 예시는 `7번 승인해줘`, `7번 승인`, `3번 예약 승인할게요`, `승인할게요`다.

`booking_id`가 없으면 `몇 번 예약을 승인하시겠어요? 예시: 7번 승인`만 `simpleText`로 반환하고 종료한다. 상태를 바꾸지 않는다.

```
POST /kakao/approve

{
  "intent": {"name": "예약승인"},
  "userRequest": {
    "utterance": "7번 승인",
    "user": {"id": "kakao_owner_id_xyz789"}
  },
  "action": {
    "params": {"booking_id": "7"}
  }
}
```

번호가 있고 담당 마을이 맞으면 상태를 `confirmed`로 바꾸고 `simpleText`로 승인 안내를 반환한다.

### 7-3A. 예약거절 블록

`운영자_예약관리`의 예약거절이다. 운영자용 단일 턴이다. `booking_id`는 `@sys.number`이고 필수 파라미터가 아니다. `decision` 파라미터는 없다. 거절인 이유는 이 블록이 호출됐기 때문이다.

발화 예시는 `7번 거절해줘`, `7번 거절`, `3번 예약 거절할게요`, `거절할게요`다. `booking_id`가 없으면 `몇 번 예약을 거절하시겠어요? 예시: 7번 거절`만 반환하고 종료한다. 상태를 바꾸지 않는다.

```
POST /kakao/approve

{
  "intent": {"name": "예약거절"},
  "userRequest": {
    "utterance": "7번 거절",
    "user": {"id": "kakao_owner_id_xyz789"}
  },
  "action": {
    "params": {"booking_id": "7"}
  }
}
```

번호가 있고 담당 마을이 맞으면 상태를 `rejected`로 바꾸고 `simpleText`로 거절 안내를 반환한다.

### 7-4. 후기 등록 요청

```
POST /kakao/review

{
  "userRequest": {
    "utterance": "정말 즐거웠어요",
    "user": {"id": "kakao_user_id_abc123"}
  },
  "action": {
    "params": {
      "booking_id": "12",
      "rating": "5",
      "photo_url": "https://.../photo.jpg"
    }
  }
}
```

### 7-5. 카카오 응답 처리 시간 제약 대응

- 카카오 스킬 응답은 호출 후 5초 이내에 반환해야 한다. 이 시간을 넘기면 카카오가 오류 안내를 보여 준다
- 스킬 처리 중 LLM 등 외부 API를 호출할 때는 타임아웃을 3.5초로 둔다. 마을 추천은 그 예산 안에서 기본 제공자를 호출하고, 빠른 실패이고 남은 시간이 2초 이상일 때만 Gemini와 OpenAI 중 다른 제공자를 한 번 호출한다. 시간 초과이거나 둘 다 실패하면 키워드 결과로 응답하고, 키워드도 없으면 조건 완화 안내를 반환한다
- fallback은 같은 요청의 스킬 응답이다. 이벤트 API로 나중에 메시지를 보내지 않는다
- 예약 저장처럼 외부 API가 필요 없는 작업은 저장 후 바로 응답한다

### 7-6. 운영자 인증 및 승인/거절 필터링

카카오 스킬 요청은 모두 같은 채널에서 들어오며, 역할은 아래 순서로 가른다.

1. `resolve_kakao_role(userRequest.user.id)`가 `operators.kakao_user_id`와 대조한다. 조회는 `services/auth.py`만 사용한다
2. 일치하는 행이 없으면 관광객 모드다. 예약 신청·후기·발화 `내 예약`만 허용한다. `내 예약`은 `bookings.customer_kakao_id`가 그 `user.id`인 행만 반환한다. 승인/거절과 발화 `예약 현황`은 거부하고, `예약 현황`은 등록 안내만 한다
3. 일치하는 행이 있으면 운영자 모드다. `role`이 `village`이면 마을 운영자이고, `program`이면 체험 담당이다. 헬퍼가 반환한 `village_id`가 담당 마을이다. 발화 `예약 현황`과 승인·거절·홍보 사진은 `role=village`만 한다. 체험 담당은 안내만 받고 예약 상태를 바꾸지 않는다
4. 상태 변경은 운영자 모드이고 `bookings.village_id`가 그 담당 마을과 같을 때만 한다. 예약승인 블록이면 `confirmed`, 예약거절 블록이면 `rejected`다. `decision` 값으로 가르지 않는다. `booking_id`가 비어 있으면 7-3, 7-3A의 안내만 반환하고 종료한다. 상태값은 `pending`(대기), `confirmed`(승인), `rejected`(거절)뿐이다
5. 불일치·권한 없음은 안내 카드로 응답한다 (HTTP 200, 카카오 규격). 관광객에게 이벤트 API로 결과를 푸시하지 않는다. 관광객이 `내 예약`으로 물으면 본인 예약의 저장 값을 안내한다. 화면 문구는 대기/승인/거절이다

### 7-7. 운영자 자가 등록

`운영자_등록`의 운영자 등록 블록이면 예약 처리보다 먼저 자가 등록을 시도한다. 한 문장에 마을명과 코드가 있다. 지점이름은 `villages_cache.village_name`이다. 호출자는 아직 `operators`에 없는 사용자다.

1. 마을명이 `villages_cache.village_name` 하나와 일치해야 한다
2. 코드가 그 행의 `registration_code`와 일치할 때만 `operators`에 행을 만든다. 마을 운영자 예: `예시 갯벌마을 GB-001`. 체험 담당 예: `예시 갯벌마을 GB-001 갯벌체험`. 오픈빌더 패턴은 `{village_name} {registration_code}`와 `{village_name} {registration_code} {sys.text}`이고, 세 번째 파라미터는 `program_label`이다. 체험마다 발화를 추가하지 않는다. 마을명이나 코드가 없으면 안내만 하고 종료한다
3. 그 마을에 마을 운영자가 없으면 `role=village`, `program_key`는 비운다. 이미 있으면 코드 뒤의 체험 이름이 그 마을 프로그램과 맞고 담당이 없을 때만 `role=program`과 `program_key`를 저장한다
4. 저장 컬럼은 `kakao_user_id`, `village_id`, `role`, `program_key`, `operator_name`, `registered_at`이다
5. 코드 불일치, 마을명 불일치, 체험 이름이 없는 추가 등록, 없는 체험, 이미 있는 담당이면 행을 만들지 않고 관광객 모드를 유지한다
6. 등록에 성공한 뒤의 요청부터 7-6의 운영자 모드로 분기한다

공공데이터 동기화 upsert는 `registration_code`를 덮어쓰지 않는다.

---

## 8. 데이터베이스 설계 (Supabase / PostgreSQL)

### 8-1. 테이블 목록

| 테이블명 | 용도 |
|---|---|
| villages_cache | 마을 캐시. `village_name`은 후기 조회·운영자 등록의 마을명, `address`·`program_type`은 추천 응답의 위치·체험유형, `registration_code`는 등록 코드. `village`라는 테이블명은 쓰지 않는다 |
| operators | 운영자 계정. `kakao_user_id` UNIQUE. `role=village`는 마을당 1명, `role=program`은 체험당 1명. `program_key`는 체험 담당만 |
| bookings | 예약. `reservations`가 아니다. `booking_id`는 승인·거절 번호, `visit_date`·`num_people`·`status`는 예약 현황 안내, `customer_kakao_id`는 본인 예약 |
| reviews | 후기. `rating`과 `comment`를 후기 조회가 안내한다. `village_id` NOT NULL FK |
| contents | 운영 콘텐츠. `village_id` NOT NULL FK |
| village_program_status | 프로그램 운영 여부. `village_id` NOT NULL FK. 공공데이터 upsert는 이 표를 덮지 않는다 |
| program_notes | 체험 글. 마을·체험당 1건. 담당자만 갱신. 관광객 API에 넣지 않는다 |
| experience_calendar | 체험 달력. 마을·체험·날짜·단체당 1건. `group_name`, `num_people`. 마을 운영자만 등록. 체험 담당은 자기 체험만 읽는다. 관광객 API에 넣지 않는다 |
| sync_logs | 공공데이터 동기화 이력 기록(운영 모니터링용) |

### 8-2. 테이블 정의

```sql
-- 마을 정보 캐시
CREATE TABLE villages_cache (
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

CREATE INDEX idx_villages_sigungu ON villages_cache(sigungu);
CREATE INDEX idx_villages_program_type ON villages_cache(program_type);

-- 마을 운영자는 마을당 1명, 체험 담당은 체험당 1명.
CREATE TABLE operators (
    operator_id SERIAL PRIMARY KEY,
    kakao_user_id TEXT NOT NULL UNIQUE,
    village_id TEXT NOT NULL REFERENCES villages_cache(village_id),
    operator_name TEXT NOT NULL,
    registered_at TIMESTAMP NOT NULL DEFAULT NOW(),
    login_id TEXT UNIQUE,
    password_hash TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    last_login_at TIMESTAMP,
    role TEXT NOT NULL DEFAULT 'village' CHECK (role IN ('village', 'program')),
    program_key TEXT,
    CONSTRAINT operators_role_program_key CHECK (
        (role = 'village' AND program_key IS NULL)
        OR (role = 'program' AND program_key IS NOT NULL)
    )
);

CREATE UNIQUE INDEX operators_one_village_role ON operators (village_id) WHERE role = 'village';
CREATE UNIQUE INDEX operators_one_program_role ON operators (village_id, program_key) WHERE role = 'program';

CREATE INDEX idx_operators_kakao ON operators(kakao_user_id);

-- 예약 테이블명은 bookings다.
-- bookings, reviews, contents는 모두 village_id NOT NULL FK다. sync_logs는 운영 원장이 아니므로 village_id가 없다.
CREATE TABLE bookings (
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

CREATE INDEX idx_bookings_village ON bookings(village_id);
CREATE INDEX idx_bookings_status ON bookings(status);

-- 후기 (village_id 필수)
CREATE TABLE reviews (
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

CREATE INDEX idx_reviews_village ON reviews(village_id);

-- 운영 콘텐츠 (village_id 필수)
CREATE TABLE contents (
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

CREATE INDEX idx_contents_village ON contents(village_id);

-- 프로그램 운영 여부. 동기화 upsert는 이 표를 갱신하지 않는다.
CREATE TABLE village_program_status (
    village_id TEXT NOT NULL REFERENCES villages_cache(village_id),
    program_key TEXT NOT NULL,
    label TEXT NOT NULL,
    is_operating BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (village_id, program_key)
);

CREATE TABLE program_notes (
    village_id TEXT NOT NULL REFERENCES villages_cache(village_id),
    program_key TEXT NOT NULL,
    label TEXT NOT NULL,
    body TEXT NOT NULL,
    updated_by INTEGER REFERENCES operators(operator_id),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (village_id, program_key)
);

CREATE TABLE experience_calendar (
    calendar_id SERIAL PRIMARY KEY,
    village_id TEXT NOT NULL REFERENCES villages_cache(village_id),
    program_key TEXT NOT NULL,
    label TEXT NOT NULL,
    visit_date DATE NOT NULL,
    group_name TEXT NOT NULL,
    num_people INTEGER NOT NULL,
    note TEXT,
    created_by INTEGER REFERENCES operators(operator_id),
    UNIQUE (village_id, program_key, visit_date, group_name)
);

-- 동기화 로그
CREATE TABLE sync_logs (
    log_id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    total_fetched INTEGER,
    total_filtered INTEGER,
    status TEXT,
    message TEXT,
    executed_at TIMESTAMP DEFAULT NOW()
);
```

### 8-3. 신뢰도 점수(trust_score) 계산 규칙

trust_score는 다음 요소를 합산한 값으로 정의한다.

1. 기본 점수: 으뜸촌 등급이 있으면 40점, 없으면 20점
2. 최신성 점수: 데이터 동기화 후 30일 이내면 20점, 그 이후 경과일에 따라 감점
3. 후기 점수: 후기 평균 평점(1~5)에 8을 곱한 값(최대 40점)

계산 로직은 services/trust_score.py에 함수로 구현하며, 채점 기준이 바뀌더라도 이 함수만 수정하면 되도록 로직을 한곳에 모은다.

### 8-4. 인증/인가 및 테넌트 필터링

#### 8-4-1. 역할 구분

| 역할 | 데이터 접근 범위 | 대표 API |
|---|---|---|
| 관광객(일반 사용자) | `villages_cache` 전체 읽기(비교·추천). `bookings`/`reviews` 쓰기 없음. 확인된 홍보 최신 1건만 읽기 | `/api/recommend`, `/api/villages`, `/api/villages/{village_id}/promo`, `/village/{village_id}`, `/api/nearby` |
| 마을 운영자 | `role=village`이고 `current_operator.village_id` 1건. 예약·후기·홍보·프로그램 운영 여부·체험 달력 쓰기. 체험 글은 읽기 | `/api/operator/*`, `/kakao/approve` |
| 체험 담당 | 같은 `village_id`의 체험 글 읽기. 자기 `program_key` 달력만 읽기. 자기 `program_key` 글만 쓰기. 예약·홍보·달력 쓰기 없음 | `POST /kakao/ask` 체험 글·달력 |

지금 `contents` 쓰기는 운영자만 한다. 관광객 공개 읽기는 `/village/{village_id}`와 `GET /api/villages/{village_id}/promo`이다. 공개는 `POST /api/operator/contents/publish`로, 그 마을의 최신 소개글·SNS홍보문구만 `is_public`이 된다. 홍보가 없으면 체험명과 시군구만 보여 주고, 관광객 후기는 넣지 않는다. `is_public` 칸과 `content-photos` 버킷은 적용되어 있고, 화면은 `chonmuseojang.vercel.app`에 배포되어 있다.

#### 8-4-2. 운영자 식별

- **카카오톡**: `resolve_kakao_role(userRequest.user.id)`. `mode`가 `operator`이면 그 `village_id`와 `role`, `tourist`이면 관광객 모드다
- **웹 대시보드**: 로그인 세션 또는 Bearer 토큰의 `operator_id`로 `scoped_village_id_for_session(operator_id)`를 호출한다. 카카오 `user.id` 헬퍼를 쓰지 않는다
- 담당 마을은 요청 본문의 `village_id`가 아니라 위 헬퍼 결과만 사용한다

#### 8-4-3. 인가 규칙 (서버 강제)

운영자용 쿼리의 `WHERE village_id = ...`는 `services/auth.py` 공통 헬퍼로만 만든다. 라우터와 개별 서비스에 조건을 직접 적지 않는다.

```python
# services/auth.py (설계 개념)

def resolve_kakao_role(user_id: str) -> dict:
    """user.id로 operators.kakao_user_id를 대조한다."""
    row = db.query(
        "SELECT village_id FROM operators WHERE kakao_user_id = :uid",
        {"uid": user_id},
    )
    if not row:
        return {"mode": "tourist", "village_id": None, "role": None}
    return {"mode": "operator", "village_id": row["village_id"], "role": row["role"]}


def scoped_village_id(user_id: str) -> str:
    """카카오 운영자 쿼리에 붙일 village_id. 관광객이면 운영자 쿼리를 실행하지 않는다."""
    role = resolve_kakao_role(user_id)
    if role["mode"] != "operator":
        raise PermissionError("operator required")
    return role["village_id"]


def scoped_village_id_for_session(operator_id: int) -> str:
    """웹 세션의 operator_id로 담당 village_id를 반환한다."""
    row = db.query(
        "SELECT village_id FROM operators WHERE operator_id = :oid",
        {"oid": operator_id},
    )
    return row["village_id"]


def list_bookings_for_operator(user_id: str):
    return db.query(
        "SELECT * FROM bookings WHERE village_id = :vid",
        {"vid": scoped_village_id(user_id)},
    )
```

- 카카오 운영자용 SELECT/UPDATE/DELETE는 `WHERE village_id = scoped_village_id(user.id)` 를 강제한다
- 웹 운영자용 쿼리는 `WHERE village_id = scoped_village_id_for_session(operator_id)` 를 강제한다
- 경로·쿼리·본문의 `village_id`가 헬퍼 결과와 다르면 **403 Forbidden** (카카오 웹훅은 200 + 안내 카드)
- INSERT 시 `village_id`는 서버가 헬퍼 값으로 주입한다 (클라이언트 값 무시)

#### 8-4-4. 이중 방어 (권장)

- 1차: 애플리케이션 레이어 `WHERE` 강제 (`services/auth.py`, `services/booking.py` 등)
- 2차(권장): Supabase Row Level Security(RLS)로 `operators.village_id`와 일치하는 행만 허용

#### 8-4-5. 관광객 API 예외

`/api/recommend`, `/api/villages`, `/api/nearby`는 인증 없이 광주·전남 전체 마을 데이터를 읽기 전용으로 제공한다. 운영 원장(예약 상세, 카카오 사용자 식별자)은 포함하지 않는다.

---

## 9. 외부 API 연동 상세

### 9-1. 공공데이터포털 OpenAPI (전국농어촌체험휴양마을표준데이터)

| 항목 | 내용 |
|---|---|
| 인증 방식 | 발급받은 서비스키를 쿼리 파라미터로 전달 |
| 호출 방식 | HTTP GET, 페이지네이션 파라미터(페이지 번호, 페이지당 건수) 사용 |
| 응답 형식 | JSON 또는 XML(신청 시 JSON 지정 권장) |
| 호출 주체 | public_data_sync.py의 동기화 함수 |
| 호출 주기 | 하루 1회 (Vercel Cron 또는 GitHub Actions) |
| 실패 시 처리 | 이전 캐싱 데이터를 그대로 유지하고, sync_logs에 실패 이력 기록 |

### 9-2. 한국관광공사 TourAPI

| 항목 | 내용 |
|---|---|
| 인증 방식 | 발급받은 서비스키를 쿼리 파라미터로 전달 |
| 주요 기능 | 위치기반 조회(마을 위경도 기준 반경 검색), 지역기반 조회(광주·전남 지역코드 한정) |
| 콘텐츠 타입 | 관광지, 문화시설, 축제행사, 숙박, 음식점 등 |
| 호출 방식 | 매 요청 시 실시간 호출(캐싱하지 않음) |
| 실패 시 처리 | 주변정보 영역을 비워두고 "정보를 불러오지 못했습니다" 안내 표시 |

### 9-3. 카카오 API (카카오톡 연동 단계)

| 항목 | 내용 |
|---|---|
| 채널/챗봇 | 카카오톡 채널 1개 + 오픈빌더 챗봇 1개(개인 유형). 운영자와 관광객이 함께 사용 |
| 스킬 API | 오픈빌더 블록에 서버 엔드포인트를 등록. 역할은 `user.id`로 서버에서 분기 |
| 이벤트 API | 이번 단계에서는 호출하지 않는다. 비즈월렛은 이번 단계에서 만들지 않으며, 예약은 조회 응답으로 안내한다. 성공한 다음 단계에서 구현한다 |
| 요청 검증 | 카카오 서버에서 온 요청인지 확인하는 기본적인 검증 로직 포함 |
| 응답 시간 제약 | 스킬 응답 5초 이내. 외부 API는 3.5초 타임아웃 후 fallback 응답 (7-5) |

### 9-4. LLM API 공통 처리 원칙

| 항목 | 내용 |
|---|---|
| 프롬프트 구성 | 시스템 프롬프트(역할 정의) + 컨텍스트(마을 데이터 일부) + 사용자 질문을 조합 |
| 응답 파싱 | LLM 응답을 그대로 노출하지 않고, 정해진 구조(JSON 등)로 파싱을 시도하며 실패 시 원문 텍스트로 폴백 |
| 오류 처리 | 추천은 기본 제공자를 한 번 호출한다. 키가 없거나 HTTP 401·403·408·429·500·502·503·504이거나 JSON을 읽지 못하면, 남은 시간이 2초 이상이고 다른 키가 있을 때 Gemini와 OpenAI 중 나머지를 한 번 호출한다. 두 번째 호출의 제한 시간은 첫 호출 뒤 남은 시간이다. 시간 초과와 올바른 빈 배열은 키워드 결과로 끝낸다. 소개글, 후기 감성, Claude는 이 대체를 쓰지 않는다 |
| 타임아웃 | 스킬 경로의 외부 API(LLM 포함) 타임아웃은 3.5초. 웹 API의 전체 응답 목표는 10초 |
| 비용 관리 | 프롬프트에 포함하는 마을 데이터 수를 제한(지역/조건으로 사전 필터링 후 일부만 포함)하여 토큰 사용량 최적화 |

---

## 10. LLM 추상화 계층 기술 명세

### 10-1. 인터페이스 정의

```python
# services/llm_provider.py

from abc import ABC, abstractmethod
import os


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """주어진 프롬프트로 텍스트를 생성해 문자열로 반환한다."""
        raise NotImplementedError


class GeminiProvider(LLMProvider):
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        # Gemini API 호출 구현 위치
        raise NotImplementedError


class ClaudeProvider(LLMProvider):
    def __init__(self):
        self.api_key = os.getenv("CLAUDE_API_KEY")

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        # Claude API 호출 구현 위치
        raise NotImplementedError


class OpenAIProvider(LLMProvider):
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        # OpenAI API 호출 구현 위치
        raise NotImplementedError


def get_llm_provider() -> LLMProvider:
    provider_name = os.getenv("LLM_PROVIDER", "gemini").lower()
    mapping = {
        "gemini": GeminiProvider,
        "claude": ClaudeProvider,
        "openai": OpenAIProvider,
    }
    provider_class = mapping.get(provider_name, GeminiProvider)
    return provider_class()
```

### 10-2. 호출 사용 예시

```python
# services/recommend.py

from services.llm_provider import get_llm_provider


def recommend_villages(user_query: str, village_rows: list[dict]) -> list[dict]:
    llm = get_llm_provider()

    system_prompt = (
        "당신은 광주·전남 농촌체험마을 추천 도우미입니다. "
        "제공된 마을 목록 중에서 사용자 질문에 가장 적합한 마을을 최대 5곳 골라 "
        "마을명과 추천 이유를 함께 제시하세요."
    )
    context = format_village_context(village_rows)
    user_prompt = f"마을 목록:\n{context}\n\n사용자 질문: {user_query}"

    raw_response = llm.generate(system_prompt, user_prompt)
    return parse_recommendation_response(raw_response, village_rows)
```

### 10-3. 제공자 전환 방법

.env 파일의 LLM_PROVIDER 값을 gemini, claude, openai 중 하나로 변경하고 서버를 재시작(또는 재배포)하면, 코드 수정 없이 전체 시스템의 LLM이 전환된다. 기본값은 gemini이다. 추천 호출의 Gemini 모델은 `gemini-3.5-flash-lite`, Claude는 `claude-haiku-4-5`, OpenAI는 `gpt-4.1-mini`이다. 추천만 JSON 모드를 쓰고, OpenAI는 `json_schema`를 쓴다. 카카오 추천 타임아웃은 3.5초, 웹 추천 타임아웃은 8초이다.

추천의 기본 제공자는 `LLM_PROVIDER`이다. 값이 `gemini`이면 다음 후보는 OpenAI이고, `openai`이면 다음 후보는 Gemini이다. 다른 쪽 키가 없으면 그 호출은 만들지 않는다. 키가 없거나 HTTP 401·403·408·429·500·502·503·504이거나 JSON을 읽지 못하고, 남은 시간이 2초 이상일 때만 다음 후보를 한 번 호출한다. 두 번째 호출은 8초나 3.5초를 새로 받지 않고 남은 시간만 쓴다. 시간 초과와 올바른 빈 배열은 키워드 결과로 끝낸다. 소개글, 후기 감성, Claude는 기본 제공자만 쓴다.

### 10-4. 프롬프트 분리 (추천봇 vs 운영자 AI사무장)

AI사무장은 두 가지 LLM 프롬프트 프로필을 사용한다.

#### 10-4-1. 추천봇용 (관광객)

| 항목 | 내용 |
|---|---|
| 호출 모듈 | `services/recommend.py` |
| 컨텍스트 | 사전 필터된 마을 요약 **최대 20건** (마을명, 위치, 체험유형, 신뢰도 등) |
| 목적 | 여러 마을을 비교하여 조건에 맞는 곳 추천 |
| 금지 사항 | 예약 원장, `customer_kakao_id` 등 운영·개인 식별 정보 미포함 |

```python
# 추천봇 시스템 프롬프트 (요지)
system_prompt = (
    "당신은 광주·전남 농촌체험마을 추천 도우미입니다. "
    "제공된 여러 마을 목록을 비교하여 사용자 질문에 가장 적합한 마을을 최대 5곳 추천하세요."
)
```

#### 10-4-2. 운영자 AI사무장용

| 항목 | 내용 |
|---|---|
| 호출 모듈 | `services/operator_assistant.py` |
| 컨텍스트 | `village_id = current_operator.village_id` 인 마을 **1건** + 해당 마을의 예약·후기·콘텐츠 요약만 |
| 목적 | 홍보문구 생성, 운영 안내, 후기 감성 요약 등 자기 마을 운영 지원. 소개글·SNS 문구는 운영자 확인 후 마을 화면의 최신 1건으로 공개한다 |
| 금지 사항 | **다른 마을의 데이터를 프롬프트에 절대 포함하지 않음**. 다른 마을 언급·비교 금지 |

```python
# 운영자 AI사무장 시스템 프롬프트 (요지)
system_prompt = (
    "당신은 이 마을의 AI사무장입니다. "
    "제공된 단일 마을 정보만을 바탕으로 운영자를 돕습니다. "
    "다른 마을을 언급하거나 비교하지 마세요."
)
```

홍보문구 쓰기는 운영자만 한다. 관광객 공개 읽기는 `/village/{village_id}`이다. 그 화면은 운영자가 공개한 마을의 최신 소개글·SNS 문구·사진만 보여 준다. 확인 전 초안은 `is_public`이 아니므로 보이지 않는다. 글이 없는 마을은 체험명과 시군구만 보여 준다. 관광객 후기는 이 화면에 넣지 않는다. 카카오 후기 조회는 `simpleText` 최대 5건으로 두고, 사진 피드는 만들지 않는다. `contents.is_public`과 `content-photos` 버킷은 적용되어 있고, 화면은 `chonmuseojang.vercel.app`에 배포되어 있다.

---

## 11. 지역 필터링 기술 명세

### 11-1. 필터링 함수

```python
# config.py

TARGET_SIDO_NAMES = [
    "광주광역시",
    "전라남도",
    "전남광주통합특별시",
    "광주특별시",
]

TARGET_SIGUNGU_LIST = [
    "동구", "서구", "남구", "북구", "광산구",
    "목포시", "여수시", "순천시", "나주시", "광양시",
    "담양군", "곡성군", "구례군", "고흥군", "보성군",
    "화순군", "장흥군", "강진군", "해남군", "영암군",
    "무안군", "함평군", "영광군", "장성군", "완도군",
    "진도군", "신안군",
]
```

```python
# services/public_data_sync.py

from config import TARGET_SIDO_NAMES, TARGET_SIGUNGU_LIST


def filter_gwangju_jeonnam(rows: list[dict]) -> list[dict]:
    filtered = []
    for row in rows:
        sido = row.get("sido", "")
        sigungu = row.get("sigungu", "")
        if sido in TARGET_SIDO_NAMES or sigungu in TARGET_SIGUNGU_LIST:
            filtered.append(row)
    return filtered
```

### 11-2. 검증 절차

동기화 함수 실행 시 다음을 로그로 남겨 필터링이 정상 작동하는지 확인한다.

1. 공공데이터 API로부터 수신한 전체 건수
2. 필터링 후 남은 건수
3. 시군구명 기준으로만 걸러진 건수와 시도명 기준으로만 걸러진 건수의 차이(중복 확인용)

이 값이 예상보다 지나치게 적거나 0에 가까우면, 필드명이 실제 응답과 다르게 매핑되었을 가능성을 우선 점검한다.

---

## 12. 데이터 동기화 파이프라인

### 12-1. 처리 순서

```python
# services/public_data_sync.py

def sync_village_data():
    raw_rows = fetch_from_public_data_api()
    filtered_rows = filter_gwangju_jeonnam(raw_rows)
    enriched_rows = merge_with_grade_info(filtered_rows)
    upsert_to_supabase(enriched_rows)  # registration_code 컬럼은 갱신하지 않는다
    log_sync_result(
        source="public_data_village",
        total_fetched=len(raw_rows),
        total_filtered=len(filtered_rows),
        status="success",
    )
```

### 12-2. 스케줄링 방식

| 방식 | 설명 |
|---|---|
| Vercel Cron | vercel.json에 cron 설정을 추가해 /api/cron/sync 경로를 하루 1회 자동 호출 |
| GitHub Actions (대안) | 저장소에 워크플로우 파일을 추가해 정해진 시간에 동기화 스크립트를 실행하고 결과를 Supabase에 반영 |

두 방식 중 하나를 선택하여 구현하며, Vercel Cron 사용 시 CRON_SECRET 값으로 해당 엔드포인트를 보호하여 외부에서 임의로 호출하지 못하도록 한다.

### 12-3. vercel.json 설정 예시

```json
{
  "crons": [
    {
      "path": "/api/cron/sync",
      "schedule": "0 18 * * *"
    }
  ]
}
```

---

## 13. 보안 요구사항

| 항목 | 내용 |
|---|---|
| 환경변수 보호 | 모든 API 키는 .env 및 Vercel 환경변수로만 관리, 코드에 하드코딩 금지 |
| Supabase 접근 키 | service role key는 서버 사이드 전용, 프론트엔드에는 노출하지 않음(필요 시 anon key 및 RLS 정책 활용 검토) |
| 카카오 웹훅 검증 | 요청 출처를 검증하는 최소한의 로직 포함 |
| 동기화 엔드포인트 보호 | CRON_SECRET 값을 헤더로 확인하여 정당한 스케줄러 호출만 허용 |
| 입력값 검증 | Pydantic 스키마를 통해 모든 요청 데이터의 형식을 강제 검증 |
| 에러 메시지 노출 제한 | 사용자에게는 일반적인 오류 메시지만 노출하고, 상세 오류는 서버 로그에만 기록 |
| CORS 설정 | 웹 화면 API는 동일 출처 기준으로 운영, 필요 시 허용 출처를 명시적으로 제한 |
| 운영자 데이터 격리 | 운영자 API는 `current_operator.village_id` 기준으로만 데이터 접근. 요청 파라미터의 `village_id` 변조 차단 |
| Supabase RLS (권장) | `bookings`, `reviews`, `contents`에 `village_id` 기반 RLS 정책 적용 검토 |

---

## 14. 성능 및 확장성 고려사항

| 항목 | 내용 |
|---|---|
| 응답 시간 목표 | 웹 API 10초 이내, 카카오 스킬 API 5초 이내. 스킬 처리 중 외부 API는 3.5초 타임아웃 |
| 캐싱 전략 | 마을 기본 정보는 Supabase에 캐싱, 매 요청마다 공공데이터 API를 직접 호출하지 않음 |
| 프롬프트 길이 관리 | LLM에 전달하는 마을 데이터는 지역/조건으로 사전 필터링한 뒤 일부(예: 20건 이내)만 포함하여 응답 속도와 비용을 관리 |
| Vercel 서버리스 제약 | 요청마다 함수가 새로 실행되므로, 전역 변수에 상태를 저장하는 방식은 사용하지 않고 모든 상태는 Supabase에 저장 |
| 콜드 스타트 대응 | 의존성 패키지를 최소화하여 함수 초기화 시간을 줄임, uv sync로 빠른 빌드 유지 |

---

## 15. 에러 처리 전략

| 상황 | 처리 방식 |
|---|---|
| 외부 API(공공데이터, TourAPI) 호출 실패 | 이전에 캐싱된 데이터로 폴백, 사용자에게는 자연스러운 안내 문구 표시 |
| LLM 호출 실패 또는 타임아웃 | 추천은 빠른 실패(키 없음, HTTP 401·403·408·429·500·502·503·504, 읽지 못한 JSON)이고 남은 시간이 2초 이상이면 Gemini와 OpenAI 중 다른 제공자를 한 번 호출한다. 시간 초과와 올바른 빈 배열은 키워드 결과로 끝낸다. 카카오 예산은 3.5초, 웹 예산은 8초이다. 키워드도 없으면 조건 완화 안내이다 |
| 카카오 스킬 처리 중 예외 발생 | 카카오 규격에 맞는 안내 메시지로 응답하여 사용자 화면에 오류가 그대로 노출되지 않도록 처리 |
| 데이터베이스 연결 실패 | 서비스 전반에 공통 예외 처리기를 두어 사용자에게는 "잠시 후 다시 시도해주세요" 형태로 응답 |

---

## 16. 테스트 전략

개발 여건(1인, 제한된 시간)을 고려해 테스트는 핵심 로직 위주로 최소한으로 구성한다. 모든 테스트는 uv run pytest 명령으로 실행한다.

| 대상 | 테스트 방식 |
|---|---|
| 지역 필터링 함수 | 샘플 데이터를 입력해 광주·전남 마을만 정확히 걸러지는지 단위 테스트로 확인 |
| 신뢰도 점수 계산 함수 | 다양한 입력값에 대해 예상 점수가 계산되는지 확인 |
| 추천 API | 실제 LLM 호출 대신 응답을 모방(mock)하여 API가 정상적으로 카드 데이터를 반환하는지 확인 |
| 카카오 웹훅 응답 형식 | 카카오가 요구하는 JSON 스키마와 정확히 일치하는지 확인 |

---

## 17. 로깅 및 모니터링

| 항목 | 내용 |
|---|---|
| 로그 대상 | 공공데이터 동기화 결과, LLM 호출 성공/실패, 카카오 웹훅 수신 내역, 예약/후기 생성 내역 |
| 저장 위치 | 개발 단계는 Vercel 함수 로그로 충분, 필요 시 sync_logs 테이블처럼 Supabase에도 주요 이벤트 기록 |
| 확인 방법 | Vercel 대시보드의 함수 로그, Supabase 대시보드의 테이블 데이터 직접 확인 |

---

## 18. 배포 파이프라인 (uv 기반)

1. 로컬에서 uv sync로 의존성을 설치한다 (최초 1회 또는 pyproject.toml 변경 시)
2. Cursor로 코드 작성 및 uv run uvicorn main:app --reload로 로컬 테스트
3. 패키지가 새로 필요하면 uv add 패키지명으로 추가하고, 이때 자동 갱신되는 uv.lock도 함께 커밋한다
4. GitHub 저장소에 pyproject.toml, uv.lock, .python-version을 포함해 커밋 및 푸시
5. Vercel이 GitHub 저장소와 연동되어 있으면, 푸시 시 uv 기반 빌드를 자동 인식하여 배포 진행
6. 배포 완료 후 Vercel이 제공하는 URL로 접속하여 정상 동작 확인
7. 카카오 연동 단계에서는 배포된 URL을 오픈빌더 스킬 설정에 등록
8. vercel.json의 crons 설정이 반영되었는지 Vercel 대시보드에서 확인

---

## 19. 단계별 구현 우선순위 (기술 관점)

| 순서 | 구현 대상 | 완료 기준 |
|---|---|---|
| 1 | 프로젝트 뼈대(pyproject.toml, main.py, config.py, 폴더 구조) | uv sync 및 uv run uvicorn main:app --reload로 로컬 서버가 정상 기동됨 |
| 2 | 공공데이터 동기화 및 지역 필터링 | Supabase villages_cache 테이블에 광주·전남 마을만 저장됨 |
| 2-1 | operators 테이블 및 테넌트 필터 미들웨어 | 운영자 인증 시 `current_operator.village_id`만 접근, 교차 마을 요청 403 |
| 3 | LLM 추상화 계층 | 환경변수 전환만으로 다른 LLM 응답을 받을 수 있음 |
| 4 | AI 추천 API 및 화면 | 자연어 질문에 대해 카드 형태로 마을이 추천됨 |
| 5 | 지도 화면 | 캐싱된 마을이 지도에 정확히 표시됨 |
| 6 | 주변정보 연동 | 특정 마을 선택 시 주변 관광정보가 표시됨 |
| 7 | 운영 현황 화면 | 예약/후기 통계가 화면에 표시됨(초기에는 데이터가 적어도 무방) |
| 8 | Vercel 배포 및 크론 설정 | Vercel에 배포 완료, /api/cron/sync가 정상 동작함 |
| 9 | 카카오 채널/오픈빌더 신청 | 채널·챗봇 1개 연결. 비즈월렛은 이번 단계에서 만들지 않고, 성공 후 다음 단계에서 만든다 |
| 10 | 카카오 Phase A 블록 6개 | 시나리오 3개. 예약승인과 예약거절은 분리되고 `decision`이 없다. `booking_id`는 `@sys.number`이며 비면 안내 후 종료. 선톡은 없다 |
| 11 | 통합 테스트 및 안정화 | 전체 시나리오가 오류 없이 시연 가능함 |

---

## 20. 문서 변경 이력

| 버전 | 일자 | 변경 내용 |
|---|---|---|
| v2.2 | 2026-10-01 | 단일 채널, `user.id` 역할 분기, 자가 등록, 조회형 알림을 반영. `operators.kakao_user_id` NOT NULL, 운영 테이블 `village_id` NOT NULL FK, 공통 헬퍼, 스킬 5초·외부 API 3.5초 fallback을 명시 |
| v2.3 | 2026-10-01 | 역할 용어 통일. 역할 함수를 `resolve_kakao_role`로 고정하고 웹은 `scoped_village_id_for_session`을 쓴다. 예약 테이블명 `reservations` 별칭을 제거 |
| v2.4 | 2026-10-01 | 운영자 발화 `예약 현황`과 관광객 발화 `내 예약`을 분리. 둘 다 `POST /kakao/booking` |
| v2.5 | 2026-10-01 | 비즈월렛·이벤트 API는 이번 단계에서 호출하지 않고, 단계 성공 후 구현한다고 명시 |
| v2.6 | 2026-10-07 | Phase A 시나리오 3개·블록 6개. 7-3을 예약승인과 예약거절로 분리. `booking_id`는 `@sys.number`, 비면 안내 후 종료. 멀티턴 대화와 가변 품목 파싱은 Phase B로 보류됨 |
| v2.7 | 2026-10-07 | 7-6 예약 현황을 `listCard`로 적고, 숫자 없는 승인·거절 발화와 `registration_code`가 `@sys.number`가 아님을 맞춤 |
| v2.8 | 2026-10-11 | 여섯 블록의 목록 성공을 `simpleText`로 맞춘다. `listCard`는 이번 단계 응답으로 쓰지 않는다 |
| v2.9 | 2026-10-11 | 마을 추천은 점수·동의어로 후보를 고르고, 카카오도 같은 함수를 쓴다. 성공 문구에 한 줄 이유를 넣는다. Gemini 2.5 Flash, 카카오 3.5초·웹 8초 |
| v2.10 | 2026-10-12 | 마을 추천은 키 없음·빠른 HTTP 거절·읽지 못한 JSON일 때 남은 시간이 2초 이상이면 Gemini와 OpenAI를 한 번 교대한다. 시간 초과와 빈 배열은 키워드 결과이다 |
| v2.11 | 2026-10-12 | 추천 이유는 맞은 말과 프로그램명·시설로 다시 쓴다. 겹치지 않으면 그 마을에 있는 것만 적는다 |
| v2.12 | 2026-10-12 | 확인된 홍보 최신 1건의 관광객 공개 읽기는 이후 화면이다. `contents` 쓰기는 운영자만이고, 공개 전 확인 상태가 필요하다 |
| v2.13 | 2026-10-13 | 마을 홍보 읽기 `/village/{village_id}`, `/api/villages/{village_id}/promo`와 공개 `POST /api/operator/contents/publish`를 적는다. 원격 `is_public`과 사진 버킷 SQL이 남아 있다 |
| v2.14 | 2026-10-13 | 마을 홍보 화면을 `chonmuseojang.vercel.app`에 배포했다. `is_public`과 `content-photos`는 적용되어 있다 |
| v2.15 | 2026-10-14 | 홍보 사진은 `POST /kakao/ask`다. 카카오 CDN 사진 한 장을 1초에 받고, 소개글·SNS는 3.5초 안에 초안으로 저장한다 |
| v2.16 | 2026-10-14 | 홍보 사진은 첫 응답으로 콜백 대기만 알리고, 초안 `simpleText`는 `callbackUrl`로 보낸다 |
| v2.17 | 2026-10-14 | 홍보 사진 초안 요청은 전달된 https 주소로 보내고, 308이면 https로 한 번 더 보낸다 |
| v2.18 | 2026-10-14 | 홍보 사진 초안 요청은 콜백 대기를 돌려주기 전에 보내고, 읽기가 끊겨도 전달된 것으로 본다 |
| v2.19 | 2026-10-15 | 홍보 사진은 카카오 호스트 리다이렉트를 따라 4초 안에 받는다. 다른 호스트로는 넘어가지 않는다. 첫 응답의 1초 대기는 그대로다 |
| v2.20 | 2026-10-15 | 홍보 사진 초안은 콜백 대기 응답의 뒷작업에서 저장한다. 자기 호출의 1초 대기는 없다. 함수 제한은 30초다 |
| v2.21 | 2026-10-15 | 이미지 플러그인 `secureUrls`의 `http://secure.kakaocdn.net`도 카카오 사진 주소로 받는다 |
| v2.22 | 2026-10-15 | 홍보 사진은 8MB·10초까지 받고, 2MB를 넘으면 jpeg로 줄인 뒤 초안을 저장한다 |
| v2.23 | 2026-10-15 | 홍보 사진 초안의 OpenAI 예산은 15초다. 마을 추천의 카카오 예산은 3.5초다 |
| v2.25 | 2026-10-16 | 카카오 마을 추천 이유에 들어 있는 꺼진 항목은 `지금은 운영하지 않음`으로 말한다 |
| v2.26 | 2026-10-17 | 마을 운영자 1명과 체험 담당. `program_notes`·`experience_calendar`. 카카오 블록 4개는 `simpleText`다 |
| v2.27 | 2026-10-17 | 체험 달력에 `group_name`·`num_people`. 같은 체험·날짜·단체는 1건. 체험 담당은 자기 체험만 조회 |
| v2.28 | 2026-10-17 | 운영자 등록 `program_label` 패턴. 달력 열기 `/calendar/{token}`과 예약 승인 API. 오픈빌더 전체 배포 v2.5 |
| v2.29 | 2026-10-17 | 관광객 홈 `GET /`는 `kakao_home.py`로 예약 안내, 마을 운영자 마을의 이름·시군구, 채널 QR을 그린다 |
| v2.30 | 2026-10-17 | 네이버 서치어드바이저 등록. `site_index.py`의 공개 사이트맵과 `robots.txt`, `base.html` 확인 태그 |
