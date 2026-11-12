# 체험마을 AI사무장 PRD (Product Requirements Document)

## 0. 문서 개요

| 항목 | 내용 |
|---|---|
| 문서 목적 | Cursor를 활용한 개발 시 참조할 기준 문서 |
| 개발 환경 | Cursor (AI 페어 프로그래밍), 비전문가 1인 개발 |
| 개발 여건 | 주 3일, 1일 1~2시간 |
| 서비스 지역 | 광주·전남 지역 한정 (전남광주통합특별시 5개구 + 22개 시·군) |
| LLM 정책 | 멀티 LLM 지원 (Gemini/Claude/GPT 중 설정으로 전환 가능) |
| 배포 환경 | Vercel(서버리스) + Supabase(PostgreSQL) |
| 데이터 연동 방식 | 공공데이터 OpenAPI 실시간 호출 + 주기적 캐싱 동기화 (CSV 다운로드 방식 미사용) |
| 버전 | v4.18 (공개 사이트는 네이버 서치어드바이저에 `https://chonmuseojang.vercel.app`로 등록되어 있다. 관광객 홈은 카카오톡 채널 체험마을AI사무장 예약 방법, 마을 운영자가 있는 마을의 이름·시군구, 채널 QR을 보여 준다. 운영자 등록은 `{village_name} {registration_code}`와 `{village_name} {registration_code} {sys.text}`(`program_label`)이고 오픈빌더 전체 배포 v2.5다. 체험 달력 열기는 `/calendar/{token}`에서 그 날짜의 예약번호와 대기를 본다. 승인과 거절은 마을 운영자만 하고, 체험 담당은 자기 체험만 본다. 체험 달력은 단체와 인원이다. 마을 홍보 화면이 `https://chonmuseojang.vercel.app/village/{village_id}`에 배포되어 있다. Phase A 시나리오 3개·블록 6개. 목록 성공은 simpleText이고 마을 추천에는 한 줄 이유가 있다. 멀티턴·가변 품목은 Phase B로 보류됨) |

---

## 1. 제품 개요

### 1-1. 한 줄 정의
광주·전남 지역 공공데이터 기반 AI 추천과 카카오톡 예약·후기 자동화를 결합한 농촌체험마을 통합 운영 지원 서비스

### 1-2. 배경 (Why)
- 농촌체험마을 운영자(사무장 부재)는 콘텐츠 생산·예약 응대 여력이 없음
- 기존 포털(웰촌, jnfarmtour)은 정보 노후화·분산으로 활용도가 낮음
- AI가 추천·콘텐츠 생성·예약 응대·운영 현황 관리를 대신함으로써 문제 해결

### 1-3. 서비스 범위 정의

**① 지역 범위: 광주·전남 한정**

이 공모전(전남·광주/전북/제주 대상)의 취지에 맞춰, MVP는 전국이 아닌 광주·전남 지역으로 한정한다. 데이터 관리 범위 축소로 개발 난이도를 낮추고, 검증 이후 전국 확장을 로드맵으로 제시한다.

> 행정구역 변경 유의사항: 2026년 7월 1일부로 광주광역시와 전라남도가 행정통합되어 "전남광주통합특별시"가 출범했다. 다만 기초자치단체(광주 5개구, 전남 22개 시·군)의 명칭과 경계는 유지된다. 공공데이터의 시도명 필드가 통합 이전 명칭("광주광역시"/"전라남도")으로 남아있을 가능성과 통합 이후 명칭("전남광주통합특별시")으로 갱신되었을 가능성이 모두 있으므로, 신·구 명칭 및 기초자치단체 목록을 이중으로 매칭하는 필터링 로직을 적용한다.

**② 기능 범위: 웹 대시보드 + 카카오톡 연동을 하나의 로드맵으로 통합**

카카오톡 실제 연동(오픈빌더, 스킬 API)은 신청·승인 절차와 상시 서버 운영이 필요하므로, 개발 순서상 뒤에 배치하되 이번 프로젝트의 정식 구성요소로 포함한다. 비즈월렛과 이벤트 API(유료 선톡)는 이번 단계에서 호출하지 않는다. 이번 단계가 완료되고 성공한 다음 단계에서 구현한다.

| 구분 | 1차 구현 대상 (웹 대시보드) | 2차 구현 대상 (카카오톡 연동) |
|---|---|---|
| 목표 | 웹 화면 핵심 기능 완성, 중간·최종 발표 시연 | 카카오톡 실제 연동으로 서비스 완결 |
| 주요 기능 | AI 추천, 마을 지도, 주변정보, 운영현황 | 채널 1개·오픈빌더 챗봇(운영자·관광객 공용), 스킬 API |
| 착수 시점 | 즉시 착수 가능 | 신청·승인 절차가 필요해 상대적으로 늦게 착수 |

**③ LLM 정책: 특정 벤더에 종속되지 않는 멀티 LLM 지원**

특정 LLM API에 종속되지 않도록 추상화 계층을 두어, 설정값 변경만으로 Gemini / Claude / GPT 등 주요 LLM을 자유롭게 교체할 수 있도록 설계한다.

**④ 데이터 연동 방식: OpenAPI 실시간 연동**

공공데이터를 한 번 내려받아 고정된 파일로 쓰는 방식 대신, OpenAPI를 통해 항상 최신 정보를 가져오는 방식을 기본 원칙으로 한다. 다만 매 요청마다 외부 API를 직접 호출하면 속도 저하와 트래픽 한도 소진 우려가 있으므로, 일정 주기로 자동 동기화하여 데이터베이스에 캐싱해두고 서비스에서는 이 캐시를 조회하는 방식을 취한다.

**⑤ AI사무장 이중 역할 및 데이터 격리 (멀티테넌시)**

AI사무장은 하나의 제품 안에서 두 가지 역할을 겸한다.

| 역할 | 대상 | 데이터 접근 범위 |
|---|---|---|
| 추천봇 | 관광객(일반 사용자) | 광주·전남 `villages_cache` 전체 읽기(비교·추천). 운영 원장(`bookings`/`reviews`/`contents`) 쓰기 없음 |
| 마을별 AI사무장 | 마을 운영자·체험 담당 (`operators`) | `current_operator.village_id` 1건만. 예약·후기·홍보는 마을 운영자만. 체험 글은 담당자만 고친다 |

공공데이터상 **대표자**(이장·운영협의회 등)는 마을의 법적 운영주체다. 서비스에 접속하는 사람은 **운영자**이고, `operators` 테이블이 그 계정이다. 첫 등록자는 마을 운영자(`role=village`)이고 마을당 1명이다. 이후 등록자는 체험 하나(`role=program`)를 맡으며 체험당 1명이다. `kakao_user_id`는 한 계정당 하나다.

**⑥ 카카오톡: 단일 채널, 예약 확인은 조회**

서비스 사용자는 운영자(사무장)와 일반 사용자(관광객) 두 종류다. 두 사용자군은 채널을 나누지 않고, 하나의 카카오톡 채널·오픈빌더 챗봇으로 처리한다.

예약이 접수되어도 챗봇이 운영자에게 먼저 메시지를 보내지 않는다. 운영자가 같은 챗봇에 `예약 현황`이라고 하면 자기 마을 예약을 안내한다. 관광객은 `내 예약`으로 본인 예약만 확인한다. 이번 단계에서 실시간 푸시를 쓰지 않는 것은 비즈월렛과 이벤트 API를 아직 구현하지 않기 때문이다. 이번 단계가 완료되고 성공한 다음 단계에서 구현한다.

같은 채널의 스킬 요청마다 `userRequest.user.id`를 `operators.kakao_user_id`와 대조한다. 일치하는 행이 없으면 관광객 모드, 있으면 그 `village_id`의 운영자 모드다 (`resolve_kakao_role`).

운영자 등록 블록은 한 문장에 마을명과 코드를 받는다. 지점이름은 문서에서 `villages_cache.village_name`이다. 코드가 그 행의 `registration_code`와 같을 때만 등록된다. 호출자는 아직 `operators`에 없는 사용자이고, 성공한 다음 요청부터 운영자다.

Phase A 오픈빌더 시나리오는 세 개다. 블록은 여섯 개이고, 각각 한 발화와 한 응답으로 끝난다. 마을 추천·후기 조회·예약 현황의 성공 목록과 한 문장 결과·안내·실패는 `simpleText`다. 목록은 최대 5건이고, 더 많으면 앞 5건만 가며 제목에 최근 5건이라고 나온다. 컨텍스트와 Lifespan은 바꾸지 않는다. 트리거와 응답은 TRD 7-0이다.

- `관광객_마을정보`: 마을 추천(관광객), 후기 조회(관광객)
- `운영자_예약관리`: 예약 현황 조회(운영자), 예약승인(운영자), 예약거절(운영자)
- `운영자_등록`: 운영자 등록

기본 시나리오의 웰컴 블록은 체험마을 AI사무장 소개와 사용 예시로 교체했다. 폴백 블록은 Phase A 블록을 떠올릴 수 있는 안내로 교체했다. 탈출 블록은 그대로 둔다.

예약 접수는 이 여섯 블록에 없다. 멀티턴으로 받지 않는다. 방문일과 인원을 한 문장에 넣도록 안내하거나 웹 대시보드 링크로 안내하고, 그 요청에서 끝낸다.

예약승인과 예약거절은 서로 다른 블록이다. `decision` 파라미터는 없다. 승인인지 거절인지는 호출된 블록으로 확정한다. `booking_id`는 `@sys.number`로 추출하고 필수 파라미터가 아니다. 번호가 없으면 안내만 반환하고 상태를 바꾸지 않는다.

멀티턴 대화와 가변 품목 파싱은 Phase B로 보류됨.

---

## 2. 목표 및 성공 기준

### 2-1. 핵심 목표
1. 사용자가 자연어로 질문하면 광주·전남 지역 조건에 맞는 농촌체험마을을 추천받을 수 있다
2. 추천된 마을의 위치를 지도에서 확인할 수 있다
3. 마을 주변의 관광지·맛집 정보를 함께 확인할 수 있다
4. 마을별 예약 현황·후기·신뢰도 점수를 확인할 수 있는 운영 관리 화면이 존재한다
5. 관광객이 카카오톡에서 예약을 신청하면 예약이 저장되고, 운영자는 같은 챗봇에 `예약 현황`이라고 물어 자기 마을 예약을 확인한다
6. 운영자가 카카오톡에서 승인/거절하면 상태가 저장되고, 관광객은 같은 챗봇에 `내 예약`이라고 물어 본인 예약 상태를 확인한다
7. 관광객이 카카오톡으로 후기(사진+텍스트)를 남기면 웹 화면에 자동 반영된다

### 2-2. 성공 기준 (Definition of Done)

| 기준 | 상세 |
|---|---|
| 기능적 완성도 | 위 7가지 목표가 실제로 작동 (초기에는 일부 목업 데이터 허용) |
| 데이터 정확성 | 광주·전남 마을만 정확히 필터링 (신·구 행정명칭 모두 대응) |
| 데모 가능성 | 브라우저 및 카카오톡 대화로 직접 시연 가능 |
| 안정성 | 발표 중 크래시 없음, LLM 전환 시에도 정상 작동, 카카오 스킬 응답시간 제한 준수 |

---

## 3. 대상 사용자 (Persona)

| Persona | 설명 | 웹 화면 접점 | 카카오톡 접점 |
|---|---|---|---|
| 관광객 A | 광주·전남 지역 체험마을을 찾는 30대 부모. 일반 사용자 | AI 추천, 지도, 주변정보 | 예약 신청, 후기 등록 |
| 운영자 B | 광주·전남 체험마을의 마을 운영자 또는 체험 담당 | 마을 운영자는 자기 마을 대시보드. 체험 담당은 예약·홍보 화면 없음 | 마을 운영자는 예약 확인·승인/거절. 체험 담당은 자기 체험 글. 달력은 마을 운영자가 등록하고 같은 마을 운영자가 본다 |
| 심사위원 C | 공모전 심사위원, 서비스 완성도를 판단 | 전체 화면 데모 | 실연동 데모(연동 완료 시) |

관광객과 운영자는 서로 다른 채널이 아니라 동일한 카카오톡 챗봇을 사용한다.

---

## 4. 시스템 아키텍처

### 4-1. 전체 구조

Vercel (FastAPI 서버리스 배포) 안에는 세 종류의 라우터가 있다.

첫째, 웹 대시보드 라우터는 HTML/CSS/JS를 렌더링하며 다음 경로를 처리한다.
- GET  /
- GET  /recommend
- GET  /map
- GET  /nearby
- GET  /dashboard

둘째, 운영자 전용 API 라우터는 인증된 운영자의 `current_operator.village_id` 범위 데이터만 제공한다.
- GET  /api/operator/dashboard

셋째, 카카오 웹훅 라우터는 Skill API 요청을 처리하며 다음 경로를 담당한다.
- POST /kakao/booking
- POST /kakao/review
- POST /kakao/approve

세 라우터는 공통 서비스 레이어를 함께 호출한다. 공통 서비스 레이어에는 다음 모듈이 포함된다.
- recommend (관광객용 AI 추천 — 전체 마을 비교)
- operator_assistant (운영자용 AI사무장 — 단일 `village_id` 컨텍스트)
- auth (운영자 인증, `current_operator` 해석, 테넌트 필터)
- trust_score (신뢰도 점수 계산)
- tourapi (주변 관광정보 호출)
- kakao_client (카카오 스킬 응답 포맷. 이번 단계에서는 이벤트 API를 호출하지 않음)
- public_data_sync (공공데이터 동기화)
- llm_provider (LLM 추상화 계층: Gemini/Claude/GPT)

공통 서비스 레이어는 Supabase(PostgreSQL)에 접근한다. Supabase에는 다음 테이블이 있다.
- villages_cache 테이블 : 공공데이터 캐시(주기 동기화)
- operators 테이블 : 마을 운영자 1명과 체험 담당. `program_notes`는 그 마을 운영자가 읽고, `experience_calendar`는 마을 운영자가 등록하고 체험 담당은 자기 체험만 본다
- bookings 테이블 : 예약 데이터(`village_id` NOT NULL)
- reviews 테이블 : 후기 데이터(`village_id` NOT NULL)
- contents 테이블 : 운영 콘텐츠(`village_id` NOT NULL)
- sync_logs 테이블 : 동기화 이력

villages_cache 테이블은 외부 데이터 원천으로부터 주기적 자동 동기화(Vercel Cron 또는 GitHub Actions)를 통해 채워진다. 외부 데이터 원천은 다음과 같다.
- 공공데이터포털 OpenAPI (전국농어촌체험휴양마을표준데이터)
- 한국관광공사 TourAPI (실시간 호출)

최종적으로 이 시스템에 접근하는 주체는 두 가지다.
- 사용자 브라우저 (관광객, 운영자, 심사위원) → 웹 대시보드 라우터 이용
- 카카오톡 채널/오픈빌더 1개 (관광객·운영자 공용) → 카카오 웹훅 라우터 이용

### 4-2. 폴더 구조

전체 프로젝트는 chonmuseojang 라는 최상위 폴더 아래에 다음과 같이 구성된다.

최상위 파일:
- main.py : FastAPI 앱 진입점, 라우터 등록
- config.py : 지역 필터 목록, LLM 기본값 등 설정값 관리
- .env : API 키 등 환경변수 (커밋 금지)
- vercel.json : Vercel 배포 설정
- pyproject.toml, uv.lock : uv 기반 파이썬 패키지 의존성 (TRD와 동일)

api 폴더:
- index.py : Vercel 서버리스 진입점 (FastAPI app 객체 export)

routers 폴더:
- web.py : 웹 대시보드 화면 라우팅
- operator.py : 운영자 전용 API(인증·대시보드·콘텐츠)
- kakao.py : 카카오 웹훅 엔드포인트

services 폴더:
- llm_provider.py : LLM 추상화 계층 (Gemini/Claude/GPT 통합 인터페이스)
- recommend.py : 관광객용 AI 추천 로직
- operator_assistant.py : 운영자 AI사무장용 프롬프트(단일 village_id)
- auth.py : 운영자 인증, current_operator 해석, 테넌트 필터
- tourapi.py : TourAPI 호출 래퍼 (광주·전남 지역코드 한정)
- trust_score.py : 신뢰도 점수 계산
- booking.py : 예약 생성/조회/상태변경
- kakao_client.py : 카카오 스킬 응답 포맷 (이번 단계에서는 이벤트 API 미호출)
- public_data_sync.py : 공공데이터 OpenAPI 호출 및 캐싱 동기화
- supabase_client.py : Supabase 연결 클라이언트

models 폴더:
- schemas.py : Pydantic 데이터 모델 정의

templates 폴더 (Jinja2 HTML 템플릿):
- base.html
- index.html
- recommend.html
- map.html
- nearby.html
- dashboard.html

static 폴더:
- css/style.css
- js/main.js

---

## 5. 지역 필터링 설계

### 5-1. 문제 정의
공공데이터의 시도명 필드가 아래 중 하나로 표기되어 있을 가능성이 있음:
1. 통합 이전 명칭 그대로: "광주광역시", "전라남도"
2. 통합 이후 명칭으로 갱신: "전남광주통합특별시"
3. 두 표기가 혼재 (일부만 갱신된 과도기 데이터)

### 5-2. 해결 방안: 이중 매칭 필터링

```python
# config.py (설계 개념 예시)

# 1) 시도명 매칭용 (신/구 명칭 모두 포함)
TARGET_SIDO_NAMES = [
    "광주광역시",
    "전라남도",
    "전남광주통합특별시",
    "광주특별시",
]

# 2) 시군구명 매칭용 (행정통합과 무관하게 유지되는 기초자치단체명 - 가장 안전한 기준)
TARGET_SIGUNGU_LIST = [
    "동구", "서구", "남구", "북구", "광산구",
    "목포시", "여수시", "순천시", "나주시", "광양시",
    "담양군", "곡성군", "구례군", "고흥군", "보성군",
    "화순군", "장흥군", "강진군", "해남군", "영암군",
    "무안군", "함평군", "영광군", "장성군", "완도군",
    "진도군", "신안군"
]

def filter_gwangju_jeonnam(df):
    condition = (
        df['sido'].isin(TARGET_SIDO_NAMES) |
        df['sigungu'].isin(TARGET_SIGUNGU_LIST)
    )
    return df[condition]
```

### 5-3. 운영 원칙
- 시군구명(기초자치단체) 기준을 1차 안전장치로 사용 (행정통합과 무관하게 유지되므로 가장 신뢰도 높음)
- 시도명은 보조적으로 사용하되, 신/구 명칭을 모두 리스트에 포함해 이중 체크
- 동기화 과정에서 필터링 전/후 건수를 로그로 남겨 데이터 누락 여부를 즉시 확인
- 목록은 config.py에 분리 보관하여, 추후 전국 확장 시 리스트만 추가하면 되도록 설계

---

## 6. 데이터 연동 및 동기화 설계

### 6-1. 방식 결정
공공데이터를 한 번 내려받는 방식이 아니라, OpenAPI를 통해 최신 정보를 지속적으로 가져오는 방식을 기본 전략으로 한다. 이는 "정보가 방치되지 않고 항상 최신 상태를 유지한다"는 서비스 철학과도 일치한다.

### 6-2. 동기화 전략

| 항목 | 내용 |
|---|---|
| 주 데이터원 | 공공데이터포털 「전국농어촌체험휴양마을표준데이터」 OpenAPI |
| 동기화 주기 | 하루 1회 자동 실행 (Vercel Cron Job 또는 GitHub Actions 스케줄러) |
| 저장 위치 | Supabase의 villages_cache 테이블 |
| 실시간 호출 유지 항목 | 한국관광공사 TourAPI(주변 정보)는 캐싱 없이 사용자 요청 시점에 실시간 호출 |
| 부수 효과 | 주기적인 동기화 작업이 Supabase 무료 플랜의 자동 휴면 정책(장기 미사용 시 발생)을 방지하는 효과도 있음 |

### 6-3. 동기화 처리 흐름 (개념)

```python
# services/public_data_sync.py (설계 개념)

def sync_village_data():
    """
    1. 공공데이터포털 OpenAPI 호출 (전국농어촌체험휴양마을표준데이터)
    2. 광주·전남 지역 필터링 적용 (config.py 기준)
    3. Supabase villages_cache 테이블에 upsert
    4. 동기화 결과(건수, 시각) 로그 기록
    """
    pass
```

---

## 7. LLM 추상화 계층 설계

### 7-1. 설계 원칙
특정 LLM 벤더(Gemini, Claude, GPT 등)에 종속되지 않고, 환경설정 값 변경만으로 자유롭게 전환 가능한 구조로 설계한다.

### 7-2. LLM별 특징 비교 (선정 근거, 100만 토큰당 비용 기준)

| 모델 | 입력 비용 | 출력 비용 | 특징 |
|---|---|---|---|
| Gemini Flash / Flash-Lite (Google) | 낮음 (0.1~0.3 달러 수준) | 낮음~중간 (0.4~2.5 달러 수준) | 3사 중 최저가권, 무료 개발 티어 제공, 긴 컨텍스트 지원 |
| Claude Haiku (Anthropic) | 중간 (0.8~1.0 달러 수준) | 높음 (4~5 달러 수준) | 경량모델 중 상대적으로 비싸지만 한국어 글쓰기 품질 우수 |
| GPT-4o mini (OpenAI) | 낮음 (0.15 달러 수준) | 낮음 (0.6 달러 수준) | 가성비 양호, 생태계·문서 자료 풍부 |

### 7-3. 기본 정책
- 개발/테스트 단계: Gemini Flash 계열을 기본값으로 사용해 비용 최소화
- 발표/데모 단계: 필요 시 Claude로 전환해 글쓰기 품질이 중요한 기능(홍보문구 생성 등)의 완성도 강화
- 코드는 어떤 모델을 쓰든 동일한 인터페이스로 호출되도록 통일

### 7-4. 인터페이스 설계 (개념)

```python
# services/llm_provider.py (설계 개념)

from abc import ABC, abstractmethod
import os

class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> str:
        pass

class GeminiProvider(LLMProvider):
    def generate(self, prompt: str) -> str:
        # Gemini API 호출 구현
        pass

class ClaudeProvider(LLMProvider):
    def generate(self, prompt: str) -> str:
        # Claude API 호출 구현
        pass

class OpenAIProvider(LLMProvider):
    def generate(self, prompt: str) -> str:
        # GPT API 호출 구현
        pass

def get_llm_provider() -> LLMProvider:
    provider_name = os.getenv("LLM_PROVIDER", "gemini")
    providers = {
        "gemini": GeminiProvider,
        "claude": ClaudeProvider,
        "openai": OpenAIProvider,
    }
    return providers[provider_name]()
```

### 7-5. LLM이 담당하는 역할 (이중 프롬프트)

| 기능 | 호출 모듈 | LLM의 역할 | 컨텍스트 범위 |
|---|---|---|---|
| AI 마을 추천 (관광객) | recommend.py | 자연어 질문 이해 → 광주·전남 마을 중 조건에 맞는 곳 선정 → 추천 이유 생성 | **여러 마을** 요약(최대 20건). 운영 원장·개인 식별자 미포함 |
| 운영자 AI사무장 | operator_assistant.py | 홍보문구·운영 안내·후기 요약 등 자기 마을 운영 지원 | **`current_operator.village_id` 마을 1건**만. 다른 마을 정보 절대 미포함 |
| 후기 감성분석 | review 연동 | 후기 텍스트의 긍정/부정 판단 → 신뢰도 점수 반영 | 해당 후기·마을만 |
| 소외마을 콘텐츠 생성 | operator_assistant.py | 운영자가 보낸 짧은 설명과 선택 사진을 소개글·SNS 문구로 확장해 `contents`에 저장한다. 운영자가 확인한 최신 1건만 관광객 마을 화면에 공개한다. 글이 없으면 체험명과 시군구만 보여 준다. 관광객 후기와 섞지 않고, 카카오에는 사진 피드를 만들지 않는다 | 해당 마을 1건만 |

데이터 자체(마을 정보, 위경도 등)는 공공데이터가 담당하고, LLM은 그 데이터를 판단하고 글로 표현하는 역할을 전담한다.

관광객에게 보여줄 홍보는 마을 한 곳의 최신 소개다. 사진, 소개글, SNS 문구가 한 묶음이다. 운영자가 확인하기 전에는 공개하지 않는다. 홍보문구가 없는 마을은 체험명과 시군구만 보여 준다. 관광객 후기와 섞지 않는다. 카카오 후기 조회는 별점과 본문의 `simpleText` 최대 5건이고, 사진 피드는 웹에만 둔다. 화면은 `https://chonmuseojang.vercel.app/village/{village_id}`에 배포되어 있다. `contents.is_public`과 `content-photos` 버킷은 적용되어 있다.

---

## 8. 기능 요구사항

### FR-1. AI 마을 추천 챗봇
| 항목 | 내용 |
|---|---|
| 라우트 | GET /recommend, POST /api/recommend |
| 입력 | 자연어 텍스트 |
| 처리 | Supabase에 캐싱된 광주·전남 마을 데이터를 LLM 프롬프트에 삽입 → llm_provider.generate() 호출 → 조건에 맞는 마을 3~5곳 추출 |
| 출력 | 마을명, 위치, 체험유형, 추천 이유 카드 |
| 카카오 블록 | `관광객_마을정보`의 마을 추천. 관광객용, 단일 턴. 조건은 발화 전체다. 엔티티는 없다. 성공은 `simpleText`로 마을명, 시군구, 한 줄 추천 이유. 최대 5곳. 없으면 `simpleText` 조건 완화 안내 |
| 우선순위 | 최우선 |

### FR-2. 마을 지도 시각화
| 항목 | 내용 |
|---|---|
| 라우트 | GET /map |
| 처리 | 캐싱된 위경도 데이터를 JSON으로 전달 |
| 출력 | Leaflet.js 또는 카카오맵 JS SDK 마커 표시 (초기 중심좌표는 광주·전남 권역) |
| 우선순위 | 최우선 |

### FR-3. 주변 관광정보 연계
| 항목 | 내용 |
|---|---|
| 라우트 | GET /nearby?village_id=xxx |
| 처리 | TourAPI locationBasedList 실시간 호출(반경 5~10km), areaCode를 광주·전남으로 한정 |
| 출력 | 관광지/음식점 카드 |
| 우선순위 | 2순위 |

### FR-4. 운영 현황 대시보드

**공개용 (관광객·심사 시연)**

| 항목 | 내용 |
|---|---|
| 화면 라우트 | GET /dashboard |
| API | GET /api/dashboard/summary |
| 처리 | 광주·전남 전체 마을 요약 통계(마을 수, 신뢰도 순위 등). 운영 원장 상세·개인 식별자 미포함 |
| 출력 | Chart.js 통계, 지역 전체 요약 |
| 우선순위 | 2순위 |

**운영자 전용**

| 항목 | 내용 |
|---|---|
| API | GET /api/operator/dashboard (인증 필수) |
| 처리 | `current_operator.village_id`에 한정된 예약·후기·신뢰도만 집계. 클라이언트가 전달한 `village_id`는 신뢰하지 않음 |
| 출력 | 자기 마을 예약 현황, 후기 목록, 신뢰도 점수 |
| 우선순위 | 2순위 |

### FR-5. 신뢰도 점수 표시
| 항목 | 내용 |
|---|---|
| 계산 로직 | 으뜸촌 등급 + 데이터 갱신 최신성 + 후기 수 조합 |
| 출력 | 배지 UI |
| 우선순위 | 3순위 |

### FR-6. 카카오톡 채널 및 오픈빌더 챗봇 신청
| 항목 | 내용 |
|---|---|
| 설명 | 운영자(사무장)와 일반 사용자(관광객)를 하나의 카카오톡 채널·챗봇으로 받는다 |
| 절차 | 채널 개설(즉시) → 오픈빌더 챗봇 신청(개인 유형, 승인 1~3영업일). 비즈월렛은 이번 단계에서 만들지 않고, 성공 후 다음 단계에서 만든다 |
| 우선순위 | 최우선 (카카오 연동 구간 내) |

### FR-7. 예약 접수 스킬 API
| 항목 | 내용 |
|---|---|
| 라우트 | POST /kakao/booking |
| 요청 | 사용자 발화, 파라미터(날짜, 인원), 사용자 식별자 |
| 처리 | 예약 정보를 Supabase에 저장한다. 운영자에게 먼저 알림을 보내지 않는다. 같은 경로에서 운영자 발화 `예약 현황`은 자기 마을 예약만, 관광객 발화 `내 예약`은 본인 예약만 안내한다. 예약 접수 자체는 Phase A 여섯 블록이 아니다 |
| 단일 턴 | 멀티턴으로 받지 않는다. 방문일과 인원을 한 문장에 넣도록 안내하거나 웹 대시보드 링크로 안내하고, 그 요청에서 끝낸다 |
| 응답 | 5초 이내 Kakao Skill Payload 2.0 규격 JSON |
| 우선순위 | 최우선 |

### FR-8. 예약승인·예약거절
| 항목 | 내용 |
|---|---|
| 라우트 | POST /kakao/approve |
| 블록 | `운영자_예약관리`의 예약승인과 예약거절. 운영자용, 단일 턴. 두 블록은 분리한다. `decision` 파라미터는 없다 |
| 입력 | `booking_id`는 `@sys.number`. 필수 파라미터가 아니다. 숫자가 있는 발화는 `7번 승인`, `7번 승인해줘`, `3번 예약 승인할게요`, `7번 거절`, `7번 거절해줘`, `3번 예약 거절할게요`다. 숫자 없는 발화 `승인할게요`, `거절할게요`도 받는다 |
| 처리 | 호출된 블록이 예약승인이면 `confirmed`, 예약거절이면 `rejected`. `resolve_kakao_role`로 운영자 모드인지 확인한 뒤, 예약의 `village_id`가 담당 마을과 같을 때만 갱신한다. 번호가 없으면 예약승인은 `몇 번 예약을 승인하시겠어요? 예시: 7번 승인`, 예약거절은 `몇 번 예약을 거절하시겠어요? 예시: 7번 거절`만 반환하고 상태를 바꾸지 않는다. 관광객에게 결과를 푸시하지 않는다 |
| 응답 | `simpleText` |
| 우선순위 | 최우선 |

### FR-9. 후기 등록
| 항목 | 내용 |
|---|---|
| 라우트 | POST /kakao/review |
| 처리 | 이미지 저장 → LLM 감성분석 → Supabase 저장 → 신뢰도 재계산 → 웹 화면 자동 반영 |
| 우선순위 | 2순위 |

### FR-9A. 후기 조회
| 항목 | 내용 |
|---|---|
| 블록 | `관광객_마을정보`의 후기 조회. 관광객용, 단일 턴. Phase A 여섯 블록에 포함된다. 후기 등록(FR-9)은 이 목록에 넣지 않는다 |
| 입력 | 스킬 파라미터 `village_id`. 커스텀 엔티티 항목은 `village_name`이고 대표값은 `village_id`다. 필수 아님. 없으면 안내만 하고 종료 |
| 응답 | 성공은 `simpleText`로 평점과 본문 최대 5건. 없으면 `simpleText` 후기 없음 안내 |

### FR-10. 예약 현황 조회 (푸시 미사용)
| 항목 | 내용 |
|---|---|
| 라우트 | POST /kakao/booking |
| 블록 | `운영자_예약관리`의 예약 현황 조회. 운영자용, 단일 턴. 엔티티는 없다. 날짜 범위는 받지 않고 `start_date`, `end_date`는 만들지 않는다 |
| 기능 | 운영자 발화 `예약 현황`이면 자기 마을 예약의 번호, 방문일, 인원, 대기/승인/거절을 `simpleText` 최대 5건으로 안내한다. 예약이 없거나 관광객이면 `simpleText`다. 관광객은 등록 안내만 한다. 본인 상태는 발화 `내 예약`으로만 안내한다. 챗봇이 먼저 메시지를 보내지 않는다 |
| 제약 | 이번 단계의 실시간 푸시·선톡은 범위 밖이다. 비즈월렛과 이벤트 API는 이번 단계가 완료되고 성공한 다음 단계에서 구현한다 |
| 우선순위 | 최우선 |

### FR-15. 운영자 데이터 격리 (멀티테넌시)
| 항목 | 내용 |
|---|---|
| 설명 | 추천봇(전체 마을 읽기)과 마을별 AI사무장(자기 `village_id`만)의 접근 권한을 서버·DB에서 강제 분리 |
| DB | `operators.role`은 `village` 또는 `program`. 마을 운영자는 마을당 1명, 체험 담당은 체험당 1명. `kakao_user_id` UNIQUE. `bookings`/`reviews`/`contents`의 `village_id` NOT NULL FK. `program_notes`·`experience_calendar`는 관광객 API에 넣지 않는다 |
| 서버 | 운영자 API·쿼리에 `WHERE village_id = current_operator.village_id` 강제. 카카오 승인/거절도 동일 |
| LLM | 추천봇=다중 마을 컨텍스트, 운영자 AI사무장=단일 마을 컨텍스트 (TRD 10-4, SRD FR-15 참조) |
| 우선순위 | 필수 |

### FR-16. 카카오 사용자 역할 자동 분기
| 항목 | 내용 |
|---|---|
| 설명 | 하나의 챗봇이 `userRequest.user.id`로 관광객(일반 사용자)과 운영자(사무장)를 가른다 |
| 처리 | `resolve_kakao_role(user_id)`가 `operators.kakao_user_id`와 대조한다. 없으면 관광객. 있으면 `village_id`와 `role`(`village` 또는 `program`)로 나눈다. 예약·홍보는 `village`만 |
| 우선순위 | 필수 (카카오 연동) |

### FR-17. 운영자 자가 등록
| 항목 | 내용 |
|---|---|
| 블록 | `운영자_등록`의 운영자 등록. 단일 턴. 호출자는 아직 `operators`에 없는 사용자다 |
| 설명 | 한 문장에 마을명과 코드를 받아 바로 등록한다. 마을 운영자 예: `예시 갯벌마을 GB-001`. 체험 담당은 코드 뒤에 그 마을 체험 이름을 붙인다. 예: `예시 갯벌마을 GB-001 갯벌체험`. 체험마다 발화를 추가하지 않는다. 지점이름은 `villages_cache.village_name`이다. `branch_name`은 없다 |
| 입력 | `village_id`는 커스텀 `village_name`의 대표값. `registration_code`는 `@sys.number`가 아니다. `program_label`은 `@sys.text`이고 필수 아님. 마을명이나 코드가 없으면 안내만 하고 종료. 오픈빌더 패턴은 `{village_name} {registration_code}`와 `{village_name} {registration_code} {sys.text}`다. 세 번째 칸의 파라미터 이름은 `program_label`이다 |
| 처리 | 마을명과 `registration_code`가 맞을 때만 저장한다. 마을 운영자가 없으면 `role=village`다. 이미 있으면 코드 뒤의 체험 이름이 그 마을 프로그램과 맞고 담당이 없을 때만 `role=program`이다. 체험 이름이 없는데 마을 운영자가 있으면 저장하지 않는다. 이미 마을 운영자인 계정이 체험 이름을 붙이면 등록하지 않는다 |
| 응답 | 성공 또는 실패 안내 `simpleText` |
| 우선순위 | 필수 (카카오 연동) |

### FR-19. 체험 글과 체험 달력
| 항목 | 내용 |
|---|---|
| 설명 | 같은 마을 운영자가 체험 글을 나눠 보고, 마을 운영자가 등록한 단체·인원 일정을 체험별로 본다 |
| 블록 | `운영자_예약관리`의 `체험 글 저장`, `체험 글 조회`, `체험 달력 등록`, `체험 달력 조회`. 스킬은 `POST /kakao/ask`. 목록 응답은 `simpleText`다. `체험 달력 조회`에는 `달력 열기`가 붙고 `/calendar/{token}`을 연다. 주소에 카카오 사용자 ID는 없다 |
| 쓰기 | 체험 담당만 자기 `program_key` 글을 `program_notes`에 저장한다. 마을 운영자만 `experience_calendar`에 체험 이름, 날짜, 단체, 인원을 넣는다. 예: `조개잡이 2026-11-01 광주소등학교 30명`. 체험 담당은 일정 등록·삭제와 예약 승인·거절을 하지 않는다 |
| 읽기 | 그 마을 운영자는 글과 마을 일정을 읽고, 달력에서 그 날짜의 예약을 예약번호와 대기로 보며 승인·거절한다. 체험 담당은 같은 마을 글과 자기 체험 일정·예약만 읽는다. 체험 이름이 없는 예약은 `체험 미정`으로 마을 운영자 달력에만 나온다. 관광객 화면과 `/village/{village_id}`에는 넣지 않는다 |
| 우선순위 | 필수 |

---

## 9. 비기능 요구사항

| 구분 | 요구사항 |
|---|---|
| 성능 | 웹 챗봇 응답 10초 이내 / 카카오 스킬 응답 5초 이내 필수 |
| 알림 | 이번 단계의 예약 확인은 푸시가 아니다. 운영자는 `예약 현황`, 관광객은 `내 예약`으로 확인한다. 이벤트 API는 성공 후 다음 단계다 |
| 지역 정확성 | 광주·전남 외 지역 데이터가 결과에 노출되지 않도록 필터링 검증 필수 |
| LLM 유연성 | 환경설정 값만 변경해도 코드 수정 없이 LLM 전환 가능해야 함 |
| 데이터 최신성 | 공공데이터는 주기적 자동 동기화를 통해 최신 상태 유지 |
| 배포 안정성 | Vercel 서버리스 환경의 상태 비저장(stateless) 특성을 고려해 모든 영속 데이터는 Supabase에 저장 (로컬 파일 저장 방식 지양) |
| 보안 | 복수 LLM API 키 및 Supabase 접속 정보는 환경변수로 관리, 카카오 웹훅 요청 검증 로직 포함 |
| 운영자 데이터 격리 | 운영자 API는 `current_operator.village_id` 기준만 접근. 요청 파라미터의 `village_id` 변조 차단 |
| 유지보수성 | 라우터/서비스/데이터 계층 분리, 함수별 주석 필수 |

---

## 10. 데이터 요구사항

### 10-1. 데이터 소스

| 데이터 | 출처 | 연동 방식 |
|---|---|---|
| 농촌체험마을 정보 | 공공데이터포털 「전국농어촌체험휴양마을표준데이터」(ID: 15013113) | OpenAPI 실시간 호출 + 주기적 캐싱(광주·전남 필터링 적용) |
| 으뜸촌 등급 | 한국농어촌공사_농촌체험휴양마을 으뜸촌 정보 | 캐싱 시 함께 반영 |
| 주변 관광정보 | 한국관광공사 TourAPI | 실시간 호출 (areaCode 광주·전남 한정) |
| 예약/후기 | 카카오 스킬 API 입력 | Supabase 실시간 저장 |
| 카카오 사용자 식별자 | 카카오 스킬 API 요청 payload | 요청 처리 시 활용 |

### 10-2. DB 스키마 (Supabase/PostgreSQL)

TRD 8-2장과 동일. 상세 필드 설명은 [My_Ai_Lab_DDD.md](My_Ai_Lab_DDD.md) 참조.

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

-- 마을 운영자는 마을당 1명, 체험 담당은 체험당 1명. 예약 테이블명은 bookings다.
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

-- 예약 (village_id 필수)
CREATE TABLE bookings (
    booking_id SERIAL PRIMARY KEY,
    village_id TEXT NOT NULL REFERENCES villages_cache(village_id),
    customer_kakao_id TEXT,
    customer_name TEXT,
    visit_date DATE,
    num_people INTEGER,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'rejected')), -- 화면 문구: 대기/승인/거절
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
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_contents_village ON contents(village_id);

-- 체험 글. 관광객 화면에는 넣지 않는다.
CREATE TABLE program_notes (
    village_id TEXT NOT NULL REFERENCES villages_cache(village_id),
    program_key TEXT NOT NULL,
    label TEXT NOT NULL,
    body TEXT NOT NULL,
    updated_by INTEGER REFERENCES operators(operator_id),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (village_id, program_key)
);

-- 체험 달력. 마을 운영자만 등록한다. 체험 담당은 자기 체험만 읽는다.
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

---

## 11. 기술 스택 (최종 확정)

| 영역 | 선택 기술 | 선정 이유 |
|---|---|---|
| 백엔드 | FastAPI | 웹 대시보드 API와 카카오 웹훅을 하나의 서버로 통합 처리 |
| 프론트엔드 | HTML + CSS + JavaScript (Jinja2 템플릿) | 디자인 자유도, Cursor 생성 정확도, 완성도 있는 UI 구현 |
| 지도 | Leaflet.js 또는 카카오맵 JS SDK | 오픈소스/무료, 광주·전남 중심 좌표 설정 |
| 차트 | Chart.js | 운영 현황 시각화 |
| 배포 | Vercel | 기존 사용 계정 활용, FastAPI 네이티브 지원, 무료 한도 내 다수 프로젝트 운영 가능 |
| 데이터 저장 | Supabase (PostgreSQL) | 서버리스 환경에 적합한 외부 DB, 무료 한도 제공 |
| 데이터 동기화 | Vercel Cron 또는 GitHub Actions | 공공데이터 OpenAPI 주기적 자동 호출 및 캐싱 |
| AI 추천 로직 | 멀티 LLM 추상화 계층 (기본값: Gemini, 전환 가능: Claude/GPT) | 비용 효율성과 유연성 확보, 특정 벤더 종속 방지 |
| 외부 API | 공공데이터포털, TourAPI(광주·전남 한정), 카카오 API | - |
| 버전관리 | GitHub | Cursor 연동 |

### 11-1. 배포·데이터 플랫폼 이용조건 참고사항

| 항목 | 내용 |
|---|---|
| Vercel 무료 한도 | 계정당 다수의 프로젝트 생성 가능(비상업적 용도 한정), 서버리스 함수 실행시간 및 월간 트래픽에 한도 존재 |
| Supabase 무료 한도 | 계정당 활성 프로젝트 수 제한 있음(휴면 상태 프로젝트는 한도에서 제외), 장기간 미사용 시 자동 휴면 전환 |
| 한도 초과 시 | 각 서비스의 유료 요금제로 전환 필요 → 지원금 활용계획에 클라우드 서비스 이용료 항목으로 반영 |

---

## 12. 화면/엔드포인트 명세 요약

| 경로 | 메서드 | 설명 |
|---|---|---|
| / | GET | 홈. 카카오 예약 방법, 마을 운영자가 있는 마을의 이름·시군구, 채널 QR. 그 아래 시군·이름 목록 |
| /recommend | GET | AI 추천 화면 |
| /api/recommend | POST | 추천 처리 API |
| /map | GET | 마을 지도 화면 (광주·전남 중심) |
| /nearby | GET | 주변정보 화면 |
| /dashboard | GET | 운영 현황 대시보드 화면 |
| /village/{village_id} | GET | 확인된 최신 소개글·SNS 문구·사진. 글이 없으면 체험명과 시군구 |
| /calendar/{token} | GET | 체험 달력. 토큰의 운영자 마을만. 그 날짜의 예약번호와 대기. 승인과 거절은 마을 운영자만 |
| /api/villages/{village_id}/promo | GET | 마을 홍보 공개 읽기 |
| /api/dashboard/summary | GET | 공개용 전체 마을 요약 통계 API |
| /api/operator/dashboard | GET | 운영자 전용 대시보드 API (인증 필수, 자기 village_id만) |
| /api/operator/contents/publish | POST | 그 마을 최신 소개글·SNS 한 쌍 공개. 다른 마을 번호는 403 |
| /kakao/booking | POST | 카카오 예약 접수, 운영자 `예약 현황`, 관광객 `내 예약` |
| /kakao/approve | POST | 카카오 예약승인 블록과 예약거절 블록. `decision` 없음. 블록으로 구분 |
| /kakao/review | POST | 카카오 후기 등록 웹훅 |

---

## 13. 개발 마일스톤

| 단계 | 목표 | 주요 산출물 |
|---|---|---|
| 사전 준비 | 제안서 제출, 공공데이터·TourAPI 활용 신청, Vercel/Supabase 환경 준비 | 활용신청 완료, 프로젝트 초기 세팅 |
| 1단계 | 데이터·서버 뼈대 구축 | FastAPI 구조, 공공데이터 동기화, 광주·전남 필터링, LLM 추상화, **operators 테이블·테넌트 필터** |
| 2단계 | 핵심 화면 개발 | AI 추천(Gemini 기본), 마을 지도 완성 |
| 중간점검 | 중간발표 시연 | 1~2단계 결과물 데모 |
| 3단계 | 기능 보강 | 주변정보 연동, 운영 현황, 신뢰도 점수 |
| 최종점검 | 최종발표 시연 | 웹 화면 완성본 데모 |
| 4단계 | 카카오톡 연동 착수 | 채널·오픈빌더 신청(단일 채널), 예약 접수/조회/승인 흐름 구현 |
| 5단계 | 통합 및 고도화 | 후기 등록, 예약 현황 조회(pull), 전체 흐름 통합 테스트 |
| 마무리 | 서비스 안정화 | AI성과공유 FESTA 대응, LLM 전환 테스트(Gemini/Claude) |

---

## 14. 리스크 및 대응

| 리스크 | 대응 방안 |
|---|---|
| 행정통합으로 인한 지역 필터링 누락 | 시군구명을 1차 필터, 시도명(신/구 모두 포함)을 보조 필터로 이중 적용, 동기화 시 필터링 전/후 건수 로그 검증 |
| 카카오 스킬 응답 5초 제한 초과 | 추천 로직은 사전에 검증된 프롬프트 활용, 필요 시 폴백 메시지 처리 구조 마련 |
| LLM 벤더별 응답 포맷 차이 | llm_provider.py에서 각 벤더 응답을 표준 포맷으로 변환하는 어댑터 로직 포함 |
| Vercel 서버리스의 상태 비저장 특성 | 모든 영속 데이터를 Supabase에 저장, 로컬 파일 저장 방식 사용하지 않음 |
| Supabase 무료 한도(활성 프로젝트 수, 자동 휴면) | 기존 활성 프로젝트 현황을 사전에 확인, 주기적 동기화 작업으로 자동 휴면 방지, 초과 시 유료 전환 비용을 예산에 반영 |
| 공공데이터 필드 누락/결측치 | 동기화 로직에서 결측치 처리 선반영 |
| 비전문가의 디버깅 어려움 | 에러 메시지를 Cursor에 그대로 전달해 원인 파악, 기능 단위로 작게 커밋 |
| 카카오톡 연동 일정 지연 | 웹 화면만으로도 완결된 데모가 가능하도록 설계되어, 연동이 늦어져도 서비스 자체는 성립 |
| 운영자 타 마을 데이터 접근 | 마을 단위 `WHERE village_id` 강제. 체험 글 쓰기는 자기 `program_key`만. 달력·예약·홍보 쓰기는 마을 운영자만 (FR-15, FR-19) |

---

## 15. 다음 액션 (Cursor 작업 시작 전 체크리스트)

### 공통 준비사항
- [ ] 공공데이터포털 「전국농어촌체험휴양마을표준데이터」 OpenAPI 활용신청
- [ ] 다운로드/호출한 데이터의 시도명 필드가 실제로 어떻게 표기되어 있는지 직접 확인 (필터링 로직 검증용)
- [ ] 한국관광공사 TourAPI 활용신청 및 인증키 발급
- [ ] LLM API 키 발급 (Gemini 우선, Claude는 보조로 함께 발급 권장)
- [ ] Supabase 대시보드에서 기존 활성 프로젝트 개수 확인
- [ ] GitHub 저장소 생성 및 Cursor 연동
- [ ] FastAPI 프로젝트 폴더 구조 초기 세팅 (config.py에 지역 필터 목록 우선 작성)
- [ ] Vercel 프로젝트 신규 생성 및 배포 연결

### 카카오톡 연동 착수 전
- [ ] 카카오톡 채널 개설 (운영자·관광객 공용 1개)
- [ ] 카카오 i 오픈빌더 챗봇 신청
- 개인 비즈월렛·이벤트 API는 이번 단계에서 만들지 않는다. 성공한 다음 단계에서 구현한다. 이번 단계는 운영자 `예약 현황`, 관광객 `내 예약`으로 확인한다
- [ ] Supabase 예약/후기 테이블 실데이터 연동 전환
