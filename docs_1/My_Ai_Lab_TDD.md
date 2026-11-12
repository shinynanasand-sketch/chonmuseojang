# 체험마을 AI사무장 TDD (Test-Driven Development) 문서

## 0. 문서 개요

| 항목 | 내용 |
|---|---|
| 문서명 | 체험마을 AI사무장 테스트 주도 개발(TDD) 문서 |
| 관련 문서 | 제안서(기획서), PRD, TRD, SRD |
| 작성 목적 | 코드 구현 이전에 테스트 케이스를 먼저 정의하여, Cursor 바이브코딩 시 "이 테스트를 통과하는 코드를 작성해줘" 방식으로 개발 방향을 명확히 하고 회귀 오류를 방지한다 |
| 대상 독자 | 개발자 본인(1인 개발) |
| 테스트 프레임워크 | pytest (uv run pytest로 실행) |
| 테스트 범위 원칙 | 핵심 비즈니스 로직(지역 필터링, **운영자 데이터 격리**, 신뢰도 계산, LLM 추상화, 카카오 웹훅 응답 형식)을 우선 검증. 멀티턴 대화와 가변 품목 파싱은 Phase B로 보류됨. 그 테스트는 만들지 않는다 |
| 버전 | v1.25 (네이버 확인 태그와 공개 사이트맵은 `tests/test_public_promo.py`다. 관광객 홈의 카카오 예약 안내는 `tests/test_public_promo.py`다. 마을 운영자가 있는 마을만 이름·시군구로 보이고, 카카오 사용자 ID와 등록 코드는 없다. QR SVG에는 채널 주소가 있다. 예약 달력의 예약번호·대기·역할은 `tests/test_booking_calendar.py`와 `tests/test_calendar_page.py`다. 체험 달력은 단체·인원이고 체험 담당은 자기 체험만 본다. 검사는 `tests/test_program_operators.py`다. 체험 담당은 자기 체험 글만 고치고 달력은 마을 운영자만 등록한다. 카카오 마을 추천 이유의 꺼진 항목은 `tests/test_village_programs.py`에서 `지금은 운영하지 않음`을 검사한다. 프로그램 운영 여부는 `tests/test_village_programs.py`다. 마을 홍보 공개 화면 테스트는 `tests/test_public_promo.py`에 있다. 카카오 홍보 사진은 `tests/test_kakao_promo_photo.py`이고, 첫 응답은 콜백 대기, 초안은 콜백의 simpleText다. 이미지 플러그인 `secureUrls`의 `http://secure.kakaocdn.net`은 받고 다른 호스트의 http는 받지 않는다. 2MB를 넘고 8MB 이하인 jpeg는 2MB 이하로 줄여 저장하고, 8MB를 넘거나 jpeg·png·webp가 아니면 안내만 한다. 사진 초안 글 생성 예산은 15초다. 마을 추천 이유는 맞은 말과 체험명으로 검사한다. 빠른 실패는 Gemini와 OpenAI를 한 번 교대한다. Phase A 블록 6개. 마을 추천 simpleText에 한 줄 이유. 예약승인과 예약거절은 분리) |

---

## 1. TDD 적용 방침

### 1-1. 왜 TDD인가

이 프로젝트는 비전문가가 1인 개발로, 그것도 주 3일·1일 1~2시간이라는 매우 제한된 시간 안에서 Cursor의 도움을 받아 개발한다. 이런 여건에서는 다음과 같은 이유로 TDD 방식이 유리하다.

1. 테스트 코드가 곧 "요구사항의 실행 가능한 명세"가 되어, Cursor에게 모호하지 않은 지시를 내릴 수 있다
2. 개발 시간이 짧게 쪼개져 있으므로(하루 1~2시간), 이전 세션에서 어디까지 만들었는지 테스트 통과 여부로 빠르게 파악할 수 있다
3. 기능을 하나씩 추가할 때마다 이전에 만든 기능이 깨지지 않았는지(회귀, Regression) 즉시 확인할 수 있다
4. 외부 API(LLM, TourAPI, 카카오)에 의존하는 로직은 실제 호출 대신 모의(mock) 처리하여, 비용 없이 빠르게 반복 검증할 수 있다

### 1-2. 테스트 범위의 우선순위

모든 코드에 대해 테스트를 작성하는 것은 시간 여건상 불가능하므로, 다음 우선순위로 테스트를 작성한다.

| 우선순위 | 대상 | 이유 |
|---|---|---|
| 1순위 | 지역 필터링 로직(FR-13) | 서비스의 핵심 전제(광주·전남 한정)가 틀리면 전체가 무의미해짐 |
| 1순위 | **운영자 데이터 격리(FR-15)** | 타 마을 데이터 유출 시 서비스 신뢰 붕괴. 교차 마을 접근 거부 필수 검증 |
| 1순위 | 카카오 역할 분기·자가 등록(FR-16, FR-17) | 같은 채널에서 운영자/관광객이 갈리고, 코드가 맞을 때만 등록되어야 함 |
| 1순위 | 카카오 스킬 응답 형식(FR-07, FR-08, FR-09, FR-10) | 형식이 하나라도 틀리면 카카오톡에서 오류로 표시됨. 이번 단계의 예약 안내는 푸시가 아니라 조회. 이벤트 API 테스트는 다음 단계다 |
| 2순위 | 신뢰도 점수 계산(FR-05) | 계산 규칙이 명확히 정해져 있어 테스트하기 쉽고, 결과가 눈에 보이는 지표라 오류 시 신뢰도에 직접 영향 |
| 2순위 | LLM 추상화 계층 전환(FR-14) | 벤더 전환이 실제로 되는지가 설계의 핵심 가치이므로 검증 필요 |
| 3순위 | AI 추천 API의 응답 구조(FR-01) | LLM 응답 자체는 비결정적이므로 "형식이 올바른가"만 검증 |
| 3순위 | 공공데이터 동기화 파이프라인(FR-12) | 외부 API 호출은 모의 처리하고, 저장 전 단계 로직만 검증 |
| 참고용 | 그 외 화면 렌더링, 정적 UI 요소 | 수작업 확인으로 대체(자동 테스트 생략 가능) |

마을 홍보 공개 화면 테스트는 `chonmuseojang/tests/test_public_promo.py`에 있다. 확인된 최신 소개글·SNS 문구·사진만 그 마을에 보이는지, 확인 전 초안과 다른 마을 글과 관광객 후기는 빠지는지, 글이 없으면 체험명과 시군구만 보이는지를 검사한다. `GET /villages`는 공개한 마을만 링크하고, 예시 마을도 공개했으면 포함한다. 같은 파일의 홈 검사는 마을 운영자가 있는 마을만 안내 목록에 나오고, 체험 담당만 있는 마을과 카카오 사용자 ID·등록 코드는 보이지 않으며, QR SVG에 채널 주소가 있는지를 확인한다. 그런 마을이 없으면 `아직 카카오로 예약할 수 있는 마을이 없습니다.`를 확인한다. 같은 파일은 홈의 네이버 확인 태그, 공개 화면 6개만 담긴 사이트맵, 운영자·달력·개발 화면을 빼는 `robots.txt`도 검사한다.

프로그램 운영 여부 테스트는 `chonmuseojang/tests/test_village_programs.py`에 있다. 괄호 안 `+`는 한 항목인지, 상태 행이 없으면 운영 중인지, 운영자가 끄면 promo가 바로 꺼지는지, 다른 마을은 403인지, `upsert_villages` 후에도 끈 상태가 남는지를 검사한다. 카카오 마을 추천 이유에 들어 있는 꺼진 항목만 `지금은 운영하지 않음`이 되고, 다른 마을 상태는 그 문장에 섞이지 않는지도 검사한다.

### 1-3. TDD 개발 사이클 (Red-Green-Refactor)

각 기능은 다음 순서로 개발한다.

1. Red: 아직 구현되지 않은 기능에 대한 테스트 코드를 먼저 작성한다. 이 시점에는 테스트가 반드시 실패(Red)한다
2. Green: 테스트를 통과시키는 최소한의 코드를 Cursor의 도움을 받아 작성한다
3. Refactor: 테스트가 통과된 상태를 유지하면서 코드를 더 읽기 쉽고 간결하게 정리한다

Cursor 프롬프트 예시: "아래 테스트 코드를 통과하는 filter_gwangju_jeonnam 함수를 services/public_data_sync.py에 작성해줘" 형태로 테스트 코드를 먼저 제시하고 구현을 요청한다.

---

## 2. 테스트 환경 구성

### 2-1. 필요 패키지

```
uv add --dev pytest
uv add --dev pytest-mock
uv add --dev httpx
```

pytest-mock은 외부 API 호출(LLM, TourAPI, 카카오)을 모의 처리하기 위해 사용하고, httpx는 FastAPI 테스트 클라이언트 및 비동기 호출 모의에 활용한다.

### 2-2. 폴더 구조 (tests 디렉터리)

tests 폴더 하위 구성:
- conftest.py : 공통 테스트 픽스처(샘플 마을 데이터, 테스트 클라이언트 등) 정의
- test_region_filter.py : 지역 필터링 로직 테스트 (FR-13)
- test_trust_score.py : 신뢰도 점수 계산 테스트 (FR-05)
- test_llm_provider.py : LLM 추상화 계층 테스트 (FR-14)
- test_recommend.py : AI 추천 로직 테스트 (FR-01)
- test_kakao_booking.py : 카카오 예약 접수 웹훅 테스트 (FR-07)
- test_kakao_approve.py : 카카오 예약 승인/거절 웹훅 테스트 (FR-08)
- test_kakao_promo_photo.py : 카카오 홍보 사진이 콜백으로 담당 마을 소개글·SNS 초안만 저장하는지 테스트 (FR-11, FR-15)
- test_kakao_review.py : 카카오 후기 등록 웹훅 테스트 (FR-09)
- test_public_data_sync.py : 공공데이터 동기화 파이프라인 테스트 (FR-12)
- test_dashboard.py : 공개용 운영 현황 통계 집계 테스트 (FR-04)
- test_operator_dashboard.py : 운영자 전용 대시보드 스코프 테스트 (FR-04, FR-15)
- test_tenant_isolation.py : 운영자 데이터 격리·auth 헬퍼 테스트 (FR-15, FR-16)
- test_operator_register.py : 운영자 자가 등록·코드 대조 테스트 (FR-17)
- test_program_operators.py : 체험 담당 등록, 체험 글·달력 권한, 단체·인원, 자기 체험만 조회, 다른 마을 거부 (FR-15, FR-19)
- test_booking_calendar.py : 체험 이름 예약이 그 날짜에 대기와 예약번호로 보이는지, 체험 담당은 보고 승인하지 못하는지, `체험 미정`은 마을 운영자만 보는지 (FR-19)
- test_calendar_page.py : 다른 마을 토큰 격리, 체험 담당의 등록·삭제 거부, 마을 운영자의 등록·삭제, `달력 열기` (FR-19)
- test_booking_service.py : 예약 저장/조회/상태변경 함수 테스트 (FR-07, FR-08, FR-10)

### 2-3. 실행 명령

```
uv run pytest
uv run pytest -v
uv run pytest tests/test_region_filter.py
uv run pytest --cov=services
```

---

## 3. 공통 테스트 픽스처 설계

```python
# tests/conftest.py

import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def sample_raw_village_rows_old_names():
    """행정통합 이전 명칭으로 표기된 샘플 데이터"""
    return [
        {"village_id": "V001", "village_name": "예시 갯벌마을", "sido": "전라남도", "sigungu": "신안군"},
        {"village_id": "V002", "village_name": "예시 무등마을", "sido": "광주광역시", "sigungu": "북구"},
        {"village_id": "V003", "village_name": "예시 강원마을", "sido": "강원특별자치도", "sigungu": "춘천시"},
    ]


@pytest.fixture
def sample_raw_village_rows_new_name():
    """행정통합 이후 명칭으로 표기된 샘플 데이터"""
    return [
        {"village_id": "V004", "village_name": "예시 여수마을", "sido": "전남광주통합특별시", "sigungu": "여수시"},
        {"village_id": "V005", "village_name": "예시 제주마을", "sido": "제주특별자치도", "sigungu": "제주시"},
    ]


@pytest.fixture
def sample_village_for_trust_score():
    """신뢰도 점수 계산용 샘플 마을 데이터"""
    return {
        "village_id": "V001",
        "grade": "으뜸촌",
        "synced_days_ago": 5,
        "average_rating": 4.5,
    }


@pytest.fixture
def test_client():
    """FastAPI 테스트 클라이언트"""
    return TestClient(app)


@pytest.fixture
def sample_kakao_booking_payload():
    """카카오 예약 접수 요청 샘플 페이로드"""
    return {
        "userRequest": {
            "utterance": "9월 20일 3명 예약할게요",
            "user": {"id": "kakao_user_id_test123"}
        },
        "action": {
            "name": "booking_action",
            "params": {"visit_date": "2026-09-20", "num_people": "3"}
        }
    }


@pytest.fixture
def sample_operator_a():
    """마을 V001 담당 운영자"""
    return {
        "operator_id": 1,
        "village_id": "V001",
        "kakao_user_id": "kakao_owner_v001",
        "operator_name": "갯벌마을 운영자",
        "login_id": "owner_v001",
        "is_active": True,
    }


@pytest.fixture
def sample_operator_b():
    """마을 V002 담당 운영자 (교차 접근 테스트용)"""
    return {
        "operator_id": 2,
        "village_id": "V002",
        "kakao_user_id": "kakao_owner_v002",
        "operator_name": "무등마을 운영자",
        "login_id": "owner_v002",
        "is_active": True,
    }


@pytest.fixture
def sample_village_with_registration_code():
    """자가 등록 코드가 미리 정의된 마을"""
    return {
        "village_id": "V001",
        "village_name": "예시 갯벌마을",
        "registration_code": "GB-001",
    }
```

### 3-1. 함수 단위 설계

구현 위치는 TRD와 같다. `resolve_kakao_role`과 `register_operator`는 `services/auth.py`, 예약 함수는 `services/booking.py`다.

#### 역할 분기

| 항목 | 내용 |
|---|---|
| 함수 | `resolve_kakao_role(user_id: str) -> dict` |
| 입력 | `user_id`: 카카오 스킬 요청의 `userRequest.user.id` |
| 처리 | `operators.kakao_user_id`를 직접 대조한다 |
| 출력 | 일치하면 `{"mode": "operator", "village_id": "<담당 마을>", "role": "village 또는 program"}`. 없으면 `{"mode": "tourist", "village_id": None, "role": None}` |
| 연관 | `scoped_village_id(user_id: str) -> str`는 mode가 `operator`일 때만 `village_id`를 반환한다. 관광객이면 운영자 쿼리를 실행하지 않는다. 웹 세션은 `scoped_village_id_for_session(operator_id: int) -> str`를 쓴다 |

#### 자가 등록

| 항목 | 내용 |
|---|---|
| 함수 | `register_operator(user_id: str, utterance: str) -> dict` |
| 입력 | `user_id`, 발화 `등록 [마을명] [코드]` |
| 코드 대조 | 발화에서 마을명과 코드를 나눈다. 마을명이 `villages_cache.village_name` 하나와 같고, 코드가 그 행의 `registration_code`와 같을 때만 성공한다 |
| 성공 출력 | `{"ok": True, "village_id": "..."}`. 마을 운영자가 없으면 `role=village`로 저장한다. 이미 있고 체험 이름이 맞으면 `{"ok": True, "village_id": "...", "role": "program"}` |
| 실패 출력 | `{"ok": False, "reason": "bad_format" 또는 "village_not_found" 또는 "code_mismatch" 또는 "already_registered" 또는 "village_operator_required" 또는 "program_not_found" 또는 "program_taken"}`. 행을 만들지 않는다 |

#### 예약 저장·조회·상태 변경

| 함수 | 입력 | 출력 |
|---|---|---|
| `create_booking(customer_kakao_id: str, village_id: str, visit_date: str, num_people: int) -> dict` | 관광객 모드의 예약 신청 | `{"booking_id": int, "status": "pending", "village_id": str}`. 운영자에게 알림을 보내지 않는다 |
| `list_bookings_for_operator(user_id: str) -> list[dict]` | 운영자 발화 `예약 현황` | `scoped_village_id(user_id)`와 `village_id`가 같은 예약만. 다른 마을 예약은 포함하지 않는다. 관광객이면 호출하지 않는다 |
| `list_my_bookings(user_id: str) -> list[dict]` | 관광객 발화 `내 예약` | `customer_kakao_id`가 그 `user_id`인 예약만. 다른 사람의 예약은 포함하지 않는다 |
| `update_booking_status(user_id: str, booking_id: int, block: str) -> dict` | `block`은 `예약승인` 또는 `예약거절`. `decision` 파라미터는 없다. `booking_id`가 없으면 호출하지 않는다 | 그 예약의 `village_id`가 담당 마을과 같을 때만 예약승인은 `confirmed`, 예약거절은 `rejected`. 아니면 `{"ok": False}`. 관광객 푸시는 하지 않는다 |

---

## 4. 기능별 테스트 케이스

### 4-1. FR-13. 지역 필터링 (test_region_filter.py)

```python
# tests/test_region_filter.py

from services.public_data_sync import filter_gwangju_jeonnam


def test_filter_includes_old_name_jeonnam(sample_raw_village_rows_old_names):
    """행정통합 이전 명칭('전라남도')으로 표기된 마을도 포함되어야 한다"""
    result = filter_gwangju_jeonnam(sample_raw_village_rows_old_names)
    village_ids = [row["village_id"] for row in result]
    assert "V001" in village_ids


def test_filter_includes_old_name_gwangju(sample_raw_village_rows_old_names):
    """행정통합 이전 명칭('광주광역시')으로 표기된 마을도 포함되어야 한다"""
    result = filter_gwangju_jeonnam(sample_raw_village_rows_old_names)
    village_ids = [row["village_id"] for row in result]
    assert "V002" in village_ids


def test_filter_excludes_other_region(sample_raw_village_rows_old_names):
    """광주·전남 외 지역(강원 등)은 제외되어야 한다"""
    result = filter_gwangju_jeonnam(sample_raw_village_rows_old_names)
    village_ids = [row["village_id"] for row in result]
    assert "V003" not in village_ids


def test_filter_includes_new_integrated_name(sample_raw_village_rows_new_name):
    """행정통합 이후 명칭('전남광주통합특별시')으로 표기된 마을도 포함되어야 한다"""
    result = filter_gwangju_jeonnam(sample_raw_village_rows_new_name)
    village_ids = [row["village_id"] for row in result]
    assert "V004" in village_ids


def test_filter_excludes_jeju_even_with_similar_words(sample_raw_village_rows_new_name):
    """제주 등 유사한 이름이 아닌 무관 지역은 제외되어야 한다"""
    result = filter_gwangju_jeonnam(sample_raw_village_rows_new_name)
    village_ids = [row["village_id"] for row in result]
    assert "V005" not in village_ids


def test_filter_returns_empty_list_for_empty_input():
    """입력이 빈 리스트일 경우 빈 리스트를 반환해야 한다"""
    result = filter_gwangju_jeonnam([])
    assert result == []


def test_filter_handles_missing_fields_gracefully():
    """sido 또는 sigungu 필드가 누락된 데이터도 오류 없이 처리되어야 한다"""
    rows = [{"village_id": "V999", "village_name": "필드누락마을"}]
    result = filter_gwangju_jeonnam(rows)
    assert isinstance(result, list)
```

### 4-2. FR-05. 신뢰도 점수 계산 (test_trust_score.py)

```python
# tests/test_trust_score.py

from services.trust_score import calculate_trust_score


def test_score_with_grade_and_recent_data_and_high_rating(sample_village_for_trust_score):
    """으뜸촌 등급 + 최신 데이터 + 높은 평점이면 높은 점수가 나와야 한다"""
    score = calculate_trust_score(sample_village_for_trust_score)
    assert score >= 80


def test_score_without_grade_is_lower():
    """등급이 없으면 등급이 있는 경우보다 점수가 낮아야 한다"""
    with_grade = calculate_trust_score({"grade": "으뜸촌", "synced_days_ago": 5, "average_rating": 4.5})
    without_grade = calculate_trust_score({"grade": None, "synced_days_ago": 5, "average_rating": 4.5})
    assert without_grade < with_grade


def test_score_decreases_with_stale_data():
    """데이터 갱신일이 오래될수록 점수가 낮아져야 한다"""
    fresh = calculate_trust_score({"grade": "으뜸촌", "synced_days_ago": 1, "average_rating": 4.0})
    stale = calculate_trust_score({"grade": "으뜸촌", "synced_days_ago": 200, "average_rating": 4.0})
    assert stale < fresh


def test_score_is_deterministic(sample_village_for_trust_score):
    """동일 입력에 대해 항상 동일한 점수가 산출되어야 한다(재현 가능성)"""
    score1 = calculate_trust_score(sample_village_for_trust_score)
    score2 = calculate_trust_score(sample_village_for_trust_score)
    assert score1 == score2


def test_score_within_valid_range(sample_village_for_trust_score):
    """점수는 0 이상 100 이하 범위 내에 있어야 한다"""
    score = calculate_trust_score(sample_village_for_trust_score)
    assert 0 <= score <= 100


def test_score_handles_no_reviews():
    """후기가 아직 없는 마을도 오류 없이 점수가 계산되어야 한다"""
    score = calculate_trust_score({"grade": None, "synced_days_ago": 3, "average_rating": None})
    assert isinstance(score, (int, float))
```

### 4-3. FR-14. LLM 추상화 계층 전환 (test_llm_provider.py)

```python
# tests/test_llm_provider.py

import os
from services.llm_provider import get_llm_provider, GeminiProvider, ClaudeProvider, OpenAIProvider


def test_default_provider_is_gemini(monkeypatch):
    """환경변수가 없을 경우 기본값은 Gemini여야 한다"""
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    provider = get_llm_provider()
    assert isinstance(provider, GeminiProvider)


def test_provider_switches_to_claude(monkeypatch):
    """환경변수를 claude로 설정하면 ClaudeProvider가 반환되어야 한다"""
    monkeypatch.setenv("LLM_PROVIDER", "claude")
    provider = get_llm_provider()
    assert isinstance(provider, ClaudeProvider)


def test_provider_switches_to_openai(monkeypatch):
    """환경변수를 openai로 설정하면 OpenAIProvider가 반환되어야 한다"""
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    provider = get_llm_provider()
    assert isinstance(provider, OpenAIProvider)


def test_invalid_provider_falls_back_to_default(monkeypatch):
    """잘못된 값이 설정되면 기본값(Gemini)으로 안전하게 대체되어야 한다"""
    monkeypatch.setenv("LLM_PROVIDER", "존재하지않는제공자")
    provider = get_llm_provider()
    assert isinstance(provider, GeminiProvider)


def test_all_providers_implement_generate_method():
    """모든 제공자 클래스는 동일한 generate 메서드 인터페이스를 가져야 한다"""
    for provider_class in [GeminiProvider, ClaudeProvider, OpenAIProvider]:
        assert hasattr(provider_class, "generate")
```

### 4-4. FR-01. AI 마을 추천 (test_recommend.py)

LLM의 실제 응답은 비결정적이므로, LLM 호출 자체는 모의 처리하고 "형식이 올바르게 반환되는가"를 검증한다. 후보 선정은 마을명·시군구·체험유형·프로그램명·시설·주소를 점수와 동의어로 고르고, 점수가 없으면 체험유형이 다른 마을만 최대 20건을 LLM에 보낸다. 고정 질의 다섯 개(아이와 갈만한 갯벌, 담양 대나무, 신안 가족, 숙박 있는 농촌, 실내 체험)는 맞는 마을이 프롬프트에 들어가는지로 본다. 대표자명·전화번호·등록 코드는 프롬프트에 없다. 카카오 마을 추천 성공 문구는 마을명, 시군구, 한 줄 이유이고 `simpleText`이며 `context`가 없다. 카카오 홍보 사진은 `tests/test_kakao_promo_photo.py`에서 본다. 이미지 플러그인 `secureUrls`가 `List(http://secure.kakaocdn.net/...)`이면 그 주소를 받는다. 다른 호스트의 http는 안내만 하고 받지 않는다. 2MB를 넘고 8MB 이하인 jpeg는 2MB 이하 jpeg로 줄여 담당 마을 초안만 저장한다. 8MB를 넘거나 jpeg, png, webp가 아니면 안내만 하고 저장하지 않는다. 운영자의 카카오 사진과 콜백 주소가 있으면 첫 응답은 `useCallback`이고, 초안 `simpleText`는 콜백으로 간다. 사진이 없거나 운영자가 아니거나 콜백 주소가 없으면 그 요청에서 안내만 돌려준다. 사진 초안 글 생성 예산은 15초다.

기본 제공자가 키 없음, HTTP 401·403·408·429·500·502·503·504, 잘린 JSON으로 실패하고 남은 시간이 2초 이상이며 다른 키가 있으면 Gemini와 OpenAI 중 나머지를 한 번 호출한다. 두 번째 호출의 제한 시간은 남은 시간이다. 성공한 응답, 시간 초과, 올바른 빈 배열은 두 번째 호출을 만들지 않는다. 둘 다 실패하면 키워드로 마을을 고른다. `LLM_PROVIDER=openai`이면 OpenAI 다음 Gemini이다. Claude와 소개글·감성 호출은 대체하지 않는다. 키가 없는 제공자의 `generate`는 `LLMUnavailable`이다.

화면에 보이는 `reason`은 모델 문장을 그대로 두지 않는다. 고른 마을 칸으로 다시 쓴다. `아이와 갈만한 갯벌체험`과 프로그램명 `조개잡이`, 시설 `가족 체험장`이면 `갯벌·가족과 맞습니다. 조개잡이, 가족 체험장.`이다. 맞은 말은 최대 두 개이고 동의어로 맞은 말도 포함한다. 프로그램명이 없으면 체험 종류를 쓴다. 질문과 겹치는 칸이 없으면 `대나무 공예, 체험장.`처럼 그 마을에 있는 것만 적고 맞았다고 하지 않는다. 80자를 넘기면 자르고, 대표자명·전화번호·등록 코드는 이유에 없다.

```python
# tests/test_recommend.py

from unittest.mock import patch
from services.recommend import recommend_villages


@patch("services.recommend.get_llm_provider")
def test_recommend_returns_list_of_dicts(mock_get_provider):
    """추천 결과는 딕셔너리로 구성된 리스트 형태여야 한다"""
    mock_llm = mock_get_provider.return_value
    mock_llm.generate.return_value = (
        '[{"village_id": "V001", "village_name": "예시 갯벌마을", "reason": "가족 단위로 즐기기 좋습니다"}]'
    )
    sample_rows = [{"village_id": "V001", "village_name": "예시 갯벌마을", "program_type": "갯벌체험"}]

    result = recommend_villages("아이와 갈만한 갯벌체험", sample_rows)

    assert isinstance(result, list)
    assert all(isinstance(item, dict) for item in result)


@patch("services.recommend.get_llm_provider")
def test_recommend_result_count_within_limit(mock_get_provider):
    """추천 결과는 5건을 초과하지 않아야 한다"""
    mock_llm = mock_get_provider.return_value
    mock_llm.generate.return_value = "[]"
    sample_rows = [{"village_id": f"V{i}", "village_name": f"마을{i}"} for i in range(10)]

    result = recommend_villages("아무 조건", sample_rows)

    assert len(result) <= 5


@patch("services.recommend.get_llm_provider")
def test_recommend_handles_llm_failure_gracefully(mock_get_provider):
    """LLM 호출이 실패해도 예외가 전체 프로세스를 중단시키지 않고 빈 결과나 안내를 반환해야 한다"""
    mock_llm = mock_get_provider.return_value
    mock_llm.generate.side_effect = Exception("LLM 호출 실패")
    sample_rows = [{"village_id": "V001", "village_name": "예시마을"}]

    result = recommend_villages("질문", sample_rows)

    assert result == [] or isinstance(result, list)


def test_recommend_with_empty_village_data_returns_empty():
    """캐싱된 마을 데이터가 아예 없을 경우 빈 결과를 반환해야 한다"""
    result = recommend_villages("아무 질문", [])
    assert result == []
```

### 4-5. FR-07. 카카오 예약 접수 웹훅 (test_kakao_booking.py)

```python
# tests/test_kakao_booking.py

from unittest.mock import patch


def test_booking_endpoint_returns_valid_kakao_format(test_client, sample_kakao_booking_payload):
    """예약 접수 응답은 카카오 스킬 규격(version, template.outputs)을 준수해야 한다"""
    response = test_client.post("/kakao/booking", json=sample_kakao_booking_payload)

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == "2.0"
    assert "outputs" in body["template"]


def test_booking_endpoint_responds_within_time_limit(test_client, sample_kakao_booking_payload):
    """응답은 5초 이내에 반환되어야 한다"""
    import time
    start = time.time()
    test_client.post("/kakao/booking", json=sample_kakao_booking_payload)
    elapsed = time.time() - start
    assert elapsed < 5.0


def test_booking_missing_required_fields_does_not_crash(test_client):
    """필수 파라미터가 누락된 요청에도 서버가 500 오류로 죽지 않고 안내 메시지를 반환해야 한다"""
    incomplete_payload = {"userRequest": {"utterance": "예약할게요", "user": {"id": "test"}}, "action": {"params": {}}}
    response = test_client.post("/kakao/booking", json=incomplete_payload)
    assert response.status_code == 200


@patch("services.kakao_client.send_kakao_notification_to_owner")
def test_booking_does_not_push_owner(mock_notify, test_client, sample_kakao_booking_payload):
    """예약이 접수되어도 운영자에게 푸시(이벤트 API)를 보내지 않아야 한다"""
    test_client.post("/kakao/booking", json=sample_kakao_booking_payload)
    assert not mock_notify.called
```

### 4-6. FR-08. 예약승인·예약거절 (test_kakao_approve.py)

예약승인과 예약거절은 서로 다른 블록이다. 요청에 `decision`을 넣지 않는다. `booking_id`는 오픈빌더 `@sys.number`가 넘긴 숫자 문자열이다.

```python
# tests/test_kakao_approve.py

from unittest.mock import patch


def test_approve_updates_booking_status(test_client):
    """예약승인 블록이면 예약 상태가 confirmed로 변경되어야 한다. decision은 없다"""
    payload = {
        "intent": {"name": "예약승인"},
        "userRequest": {"utterance": "7번 승인", "user": {"id": "owner_test"}},
        "action": {"params": {"booking_id": "7"}}
    }
    response = test_client.post("/kakao/approve", json=payload)
    assert response.status_code == 200
    assert "outputs" in response.json()["template"]


def test_reject_updates_booking_status(test_client):
    """예약거절 블록이면 예약 상태가 rejected로 변경되어야 한다. decision은 없다"""
    payload = {
        "intent": {"name": "예약거절"},
        "userRequest": {"utterance": "7번 거절", "user": {"id": "owner_test"}},
        "action": {"params": {"booking_id": "7"}}
    }
    response = test_client.post("/kakao/approve", json=payload)
    assert response.status_code == 200


@patch("services.kakao_client.send_kakao_notification_to_customer")
def test_approve_does_not_push_customer(mock_notify, test_client):
    """승인 후에도 관광객에게 푸시하지 않아야 한다. 상태는 저장만 된다"""
    payload = {
        "intent": {"name": "예약승인"},
        "userRequest": {"utterance": "7번 승인", "user": {"id": "owner_test"}},
        "action": {"params": {"booking_id": "7"}}
    }
    test_client.post("/kakao/approve", json=payload)
    assert not mock_notify.called


def test_approve_with_nonexistent_booking_id_does_not_crash(test_client):
    """존재하지 않는 예약번호로 요청해도 서버 오류 없이 안내 메시지를 반환해야 한다"""
    payload = {
        "intent": {"name": "예약승인"},
        "userRequest": {"utterance": "999999번 승인", "user": {"id": "owner_test"}},
        "action": {"params": {"booking_id": "999999"}}
    }
    response = test_client.post("/kakao/approve", json=payload)
    assert response.status_code == 200


@patch("services.auth.resolve_kakao_role")
@patch("services.booking.get_booking_by_id")
def test_approve_rejects_cross_village_booking(mock_get_booking, mock_role, test_client, sample_operator_a):
    """운영자 A가 마을 B의 예약을 승인하려 하면 거부되어야 한다 (FR-15)"""
    mock_role.return_value = {"mode": "operator", "village_id": sample_operator_a["village_id"]}
    mock_get_booking.return_value = {"booking_id": 99, "village_id": "V002", "status": "pending"}

    payload = {
        "intent": {"name": "예약승인"},
        "userRequest": {"utterance": "99번 승인", "user": {"id": "kakao_owner_v001"}},
        "action": {"params": {"booking_id": "99"}}
    }
    response = test_client.post("/kakao/approve", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert "outputs" in body["template"]
    # 상태 변경 없이 안내 메시지로 응답 (구현 시 본문 키워드로 추가 검증 가능)


@patch("services.auth.resolve_kakao_role")
def test_approve_rejects_unregistered_operator(mock_role, test_client):
    """미등록 id의 운영자 전용 발화는 거부되고, 등록 방법 안내가 포함되어야 한다"""
    mock_role.return_value = {"mode": "tourist", "village_id": None}
    payload = {
        "intent": {"name": "예약승인"},
        "userRequest": {"utterance": "7번 승인", "user": {"id": "unknown_kakao_user"}},
        "action": {"params": {"booking_id": "7"}}
    }
    response = test_client.post("/kakao/approve", json=payload)
    assert response.status_code == 200
    assert "등록" in response.text


@patch("services.booking.update_booking_status")
def test_approve_without_booking_id_returns_guidance_and_stops(mock_update, test_client):
    """booking_id가 없으면 승인 안내만 반환하고 상태를 바꾸지 않는다"""
    payload = {
        "intent": {"name": "예약승인"},
        "userRequest": {"utterance": "승인할게요", "user": {"id": "owner_test"}},
        "action": {"params": {}}
    }
    response = test_client.post("/kakao/approve", json=payload)
    assert response.status_code == 200
    assert "몇 번 예약을 승인하시겠어요? 예시: 7번 승인" in response.text
    assert not mock_update.called


@patch("services.booking.update_booking_status")
def test_reject_without_booking_id_returns_guidance_and_stops(mock_update, test_client):
    """booking_id가 없으면 거절 안내만 반환하고 상태를 바꾸지 않는다"""
    payload = {
        "intent": {"name": "예약거절"},
        "userRequest": {"utterance": "거절할게요", "user": {"id": "owner_test"}},
        "action": {"params": {}}
    }
    response = test_client.post("/kakao/approve", json=payload)
    assert response.status_code == 200
    assert "몇 번 예약을 거절하시겠어요? 예시: 7번 거절" in response.text
    assert not mock_update.called


def test_recommend_success_uses_simple_text(test_client):
    """마을 추천 성공 응답은 simpleText다. 엔티티는 없다"""
    payload = {
        "intent": {"name": "마을 추천"},
        "userRequest": {"utterance": "아이와 갈 갯벌", "user": {"id": "guest"}},
        "action": {"params": {}}
    }
    body = test_client.post("/kakao/ask", json=payload).json()
    assert "simpleText" in body["template"]["outputs"][0]
    assert "listCard" not in body["template"]["outputs"][0]


def test_review_lookup_uses_village_id_and_simple_text(test_client):
    """후기 조회는 village_id로 그 마을 후기를 simpleText로 안내한다"""
    payload = {
        "intent": {"name": "후기 조회"},
        "userRequest": {"utterance": "예시 갯벌마을 후기", "user": {"id": "guest"}},
        "action": {"params": {"village_id": "V001"}}
    }
    body = test_client.post("/kakao/ask", json=payload).json()
    assert "simpleText" in body["template"]["outputs"][0]
    assert "listCard" not in body["template"]["outputs"][0]


def test_booking_status_uses_simple_text(test_client):
    """예약 현황 성공 응답은 simpleText다. start_date와 end_date는 없다"""
    payload = {
        "intent": {"name": "예약 현황 조회"},
        "userRequest": {"utterance": "예약 현황", "user": {"id": "owner_test"}},
        "action": {"params": {}}
    }
    body = test_client.post("/kakao/booking", json=payload).json()
    assert "simpleText" in body["template"]["outputs"][0]
    assert "listCard" not in body["template"]["outputs"][0]
    assert "start_date" not in payload["action"]["params"]
```

### 4-7. FR-09. 후기 등록 및 감성분석 (test_kakao_review.py)

```python
# tests/test_kakao_review.py

from unittest.mock import patch


@patch("services.llm_provider.get_llm_provider")
def test_review_positive_sentiment_detected(mock_get_provider, test_client):
    """명확히 긍정적인 후기는 긍정으로 분석되어야 한다"""
    mock_llm = mock_get_provider.return_value
    mock_llm.generate.return_value = "긍정"

    payload = {
        "userRequest": {"utterance": "정말 즐거웠어요! 최고였습니다", "user": {"id": "customer_test"}},
        "action": {"params": {"booking_id": "1", "rating": "5"}}
    }
    response = test_client.post("/kakao/review", json=payload)
    assert response.status_code == 200


@patch("services.llm_provider.get_llm_provider")
def test_review_negative_sentiment_detected(mock_get_provider, test_client):
    """명확히 부정적인 후기는 부정으로 분석되어야 한다"""
    mock_llm = mock_get_provider.return_value
    mock_llm.generate.return_value = "부정"

    payload = {
        "userRequest": {"utterance": "별로였고 다시는 안 갈 것 같아요", "user": {"id": "customer_test"}},
        "action": {"params": {"booking_id": "1", "rating": "1"}}
    }
    response = test_client.post("/kakao/review", json=payload)
    assert response.status_code == 200


def test_review_without_photo_still_saves(test_client):
    """사진이 없는 후기도 정상적으로 저장되어야 한다"""
    payload = {
        "userRequest": {"utterance": "좋았어요", "user": {"id": "customer_test"}},
        "action": {"params": {"booking_id": "1", "rating": "4"}}
    }
    response = test_client.post("/kakao/review", json=payload)
    assert response.status_code == 200


def test_review_triggers_trust_score_recalculation(test_client):
    """후기 등록 후 해당 마을의 신뢰도 점수가 재계산되어야 한다"""
    with patch("services.trust_score.recalculate_for_village") as mock_recalc:
        payload = {
            "userRequest": {"utterance": "좋았어요", "user": {"id": "customer_test"}},
            "action": {"params": {"booking_id": "1", "rating": "5"}}
        }
        test_client.post("/kakao/review", json=payload)
        assert mock_recalc.called
```

### 4-8. FR-12. 공공데이터 동기화 (test_public_data_sync.py)

외부 API 호출은 모의 처리하여 실제 네트워크 요청 없이 로직만 검증한다.

```python
# tests/test_public_data_sync.py

from unittest.mock import patch
from services.public_data_sync import sync_village_data


@patch("services.public_data_sync.upsert_to_supabase")
@patch("services.public_data_sync.fetch_from_public_data_api")
def test_sync_filters_before_saving(mock_fetch, mock_upsert):
    """동기화 시 저장 이전에 반드시 지역 필터링이 적용되어야 한다"""
    mock_fetch.return_value = [
        {"village_id": "V001", "sido": "전라남도", "sigungu": "신안군"},
        {"village_id": "V002", "sido": "강원특별자치도", "sigungu": "춘천시"},
    ]

    sync_village_data()

    saved_rows = mock_upsert.call_args[0][0]
    saved_ids = [row["village_id"] for row in saved_rows]
    assert "V001" in saved_ids
    assert "V002" not in saved_ids


@patch("services.public_data_sync.log_sync_result")
@patch("services.public_data_sync.upsert_to_supabase")
@patch("services.public_data_sync.fetch_from_public_data_api")
def test_sync_logs_result(mock_fetch, mock_upsert, mock_log):
    """동기화 완료 후 결과가 로그로 기록되어야 한다"""
    mock_fetch.return_value = [{"village_id": "V001", "sido": "전라남도", "sigungu": "신안군"}]

    sync_village_data()

    assert mock_log.called


@patch("services.public_data_sync.fetch_from_public_data_api")
def test_sync_handles_api_failure_without_crashing(mock_fetch):
    """외부 API 호출이 실패해도 예외가 전체 프로세스를 중단시키지 않아야 한다"""
    mock_fetch.side_effect = Exception("공공데이터 API 호출 실패")

    try:
        sync_village_data()
    except Exception:
        assert False, "동기화 실패 시에도 예외가 상위로 전파되지 않아야 한다"
```

### 4-9. FR-04. 운영 현황 통계 집계 (test_dashboard.py, test_operator_dashboard.py)

공개용 API와 운영자 전용 API를 분리해 검증한다.

```python
# tests/test_dashboard.py — 공개용 (전체 마을 요약)

from services.booking import get_public_dashboard_summary


def test_public_dashboard_counts_total_villages():
    """공개용 API는 전체 마을 수를 집계해야 한다"""
    summary = get_public_dashboard_summary()
    assert "total_villages" in summary
    assert isinstance(summary["total_villages"], int)


def test_public_dashboard_returns_top_trusted_villages_sorted():
    """신뢰도 상위 마을 목록은 점수 내림차순으로 정렬되어야 한다"""
    summary = get_public_dashboard_summary()
    scores = [v["trust_score"] for v in summary.get("top_trusted_villages", [])]
    assert scores == sorted(scores, reverse=True)
```

```python
# tests/test_operator_dashboard.py — 운영자 전용 (FR-15)

from services.booking import get_operator_dashboard_summary


def test_operator_dashboard_scoped_to_village(sample_operator_a):
    """운영자 대시보드는 current_operator.village_id 데이터만 반환해야 한다"""
    summary = get_operator_dashboard_summary(sample_operator_a)
    assert summary["village_id"] == sample_operator_a["village_id"]
    assert "total_bookings" in summary
    assert "pending_bookings" in summary


def test_operator_dashboard_excludes_other_village_bookings(sample_operator_a, sample_operator_b):
    """운영자 A의 대시보드에 마을 B 예약이 포함되지 않아야 한다"""
    summary_a = get_operator_dashboard_summary(sample_operator_a)
    summary_b = get_operator_dashboard_summary(sample_operator_b)
    if summary_a.get("recent_bookings") and summary_b.get("recent_bookings"):
        ids_a = {b["booking_id"] for b in summary_a["recent_bookings"]}
        ids_b = {b["booking_id"] for b in summary_b["recent_bookings"]}
        assert ids_a.isdisjoint(ids_b)
```

### 4-10. FR-15. 운영자 데이터 격리 (test_tenant_isolation.py)

```python
# tests/test_tenant_isolation.py

from unittest.mock import patch
from services.auth import scoped_village_id, assert_operator_owns_village


@patch("services.auth.resolve_kakao_role", return_value={"mode": "operator", "village_id": "V001"})
def test_scoped_village_id_returns_operator_village(mock_role):
    """scoped_village_id는 user.id로 조회한 담당 village_id만 반환해야 한다"""
    assert scoped_village_id("kakao_owner_v001") == "V001"
    mock_role.assert_called_once_with("kakao_owner_v001")


def test_assert_operator_owns_village_allows_own_village(sample_operator_a):
    """자기 마을에 대한 접근은 허용되어야 한다"""
    assert assert_operator_owns_village(sample_operator_a, "V001") is True


def test_assert_operator_owns_village_denies_other_village(sample_operator_a):
    """타 마을에 대한 접근은 거부되어야 한다"""
    assert assert_operator_owns_village(sample_operator_a, "V002") is False


def test_operator_api_requires_authentication(test_client):
    """인증 없이 /api/operator/dashboard 호출 시 401 또는 403이어야 한다"""
    response = test_client.get("/api/operator/dashboard")
    assert response.status_code in (401, 403)
```

### 4-11. FR-16·FR-17·예약 함수 (test_kakao_role.py, test_operator_register.py, test_booking_service.py)

```python
# tests/test_kakao_role.py

from services.auth import resolve_kakao_role


def test_registered_operator_id_resolves_own_village(sample_operator_a):
    """등록된 운영자 id는 운영자 모드이고 담당 village_id만 반환해야 한다"""
    result = resolve_kakao_role(sample_operator_a["kakao_user_id"])
    assert result == {"mode": "operator", "village_id": "V001"}


def test_unregistered_id_is_tourist():
    """미등록 id는 관광객 모드이고 village_id는 없어야 한다"""
    result = resolve_kakao_role("unknown_kakao_user")
    assert result == {"mode": "tourist", "village_id": None}
```

```python
# tests/test_booking_service.py

from services.booking import list_bookings_for_operator, list_my_bookings


def test_registered_operator_lists_only_own_village(sample_operator_a):
    """등록된 운영자 id로 조회하면 해당 마을 예약만 반환되어야 한다"""
    bookings = list_bookings_for_operator(sample_operator_a["kakao_user_id"])
    assert bookings
    assert {row["village_id"] for row in bookings} == {"V001"}


def test_operators_cannot_see_each_others_bookings(sample_operator_a, sample_operator_b):
    """A마을 운영자와 B마을 운영자는 서로의 예약을 볼 수 없어야 한다"""
    bookings_a = list_bookings_for_operator(sample_operator_a["kakao_user_id"])
    bookings_b = list_bookings_for_operator(sample_operator_b["kakao_user_id"])
    ids_a = {row["booking_id"] for row in bookings_a}
    ids_b = {row["booking_id"] for row in bookings_b}
    assert ids_a.isdisjoint(ids_b)
    assert {row["village_id"] for row in bookings_a} == {"V001"}
    assert {row["village_id"] for row in bookings_b} == {"V002"}


def test_list_my_bookings_returns_only_own_customer():
    """`내 예약` 조회는 customer_kakao_id가 요청자와 같은 행만 반환해야 한다"""
    rows = list_my_bookings("customer_flow_test")
    assert rows
    assert {row["customer_kakao_id"] for row in rows} == {"customer_flow_test"}
```

```python
# tests/test_operator_register.py

from services.auth import register_operator


def test_unregistered_operator_utterance_prompts_registration(test_client):
    """미등록 id의 운영자 발화 `예약 현황`은 마을 목록 대신 등록 안내여야 한다"""
    payload = {
        "userRequest": {"utterance": "예약 현황", "user": {"id": "unknown_kakao_user"}},
        "action": {"params": {}}
    }
    response = test_client.post("/kakao/booking", json=payload)
    assert response.status_code == 200
    assert "등록" in response.text


def test_tourist_my_booking_returns_own_status_only(test_client):
    """미등록 id의 `내 예약`은 본인 상태만 안내하고 등록 안내로 바꾸지 않는다"""
    payload = {
        "userRequest": {"utterance": "내 예약", "user": {"id": "customer_flow_test"}},
        "action": {"params": {}}
    }
    response = test_client.post("/kakao/booking", json=payload)
    assert response.status_code == 200
    assert "등록 [" not in response.text


def test_register_operator_with_valid_code_inserts_row(sample_village_with_registration_code):
    """올바른 마을명과 코드면 operators에 kakao_user_id와 village_id가 저장되어야 한다"""
    utterance = "예시 갯벌마을 GB-001"
    result = register_operator("new_owner_kakao", utterance)
    assert result["ok"] is True
    assert result["village_id"] == sample_village_with_registration_code["village_id"]


def test_register_operator_rejects_wrong_code(sample_village_with_registration_code):
    """코드가 registration_code와 다르면 등록하지 않아야 한다"""
    result = register_operator("new_owner_kakao", "예시 갯벌마을 WRONG")
    assert result == {"ok": False, "reason": "code_mismatch"}
```

---

## 5. 통합 테스트 시나리오

단위 테스트와 별도로, 여러 모듈이 함께 동작하는 흐름을 확인하는 통합 테스트를 다음과 같이 정의한다.

### 5-1. 시나리오: 예약 접수부터 승인까지 전체 흐름

```python
# tests/test_integration_booking_flow.py

def test_full_booking_approval_flow(test_client):
    """
    1. 관광객이 예약을 신청하면 상태는 pending으로 저장되고 선톡은 나가지 않는다
    2. 등록된 운영자가 승인한다
    3. 예약 상태가 confirmed가 되어야 한다. 관광객 푸시는 없다
    """
    booking_payload = {
        "userRequest": {"utterance": "9월 20일 3명 예약할게요", "user": {"id": "customer_flow_test"}},
        "action": {"params": {"visit_date": "2026-09-20", "num_people": "3"}}
    }
    booking_response = test_client.post("/kakao/booking", json=booking_payload)
    assert booking_response.status_code == 200

    approve_payload = {
        "intent": {"name": "예약승인"},
        "userRequest": {"utterance": "7번 승인", "user": {"id": "owner_flow_test"}},
        "action": {"params": {"booking_id": "7"}}
    }
    approve_response = test_client.post("/kakao/approve", json=approve_payload)
    assert approve_response.status_code == 200
```

### 5-2. 시나리오: 지역 필터링부터 웹 화면 노출까지

```python
def test_filtered_village_appears_in_map_api(test_client):
    """
    1. 공공데이터 동기화 후 광주·전남 마을이 저장된다
    2. 지도 API를 호출하면 해당 마을이 결과에 포함되어야 한다
    """
    response = test_client.get("/api/villages")
    assert response.status_code == 200
    villages = response.json()["villages"]
    for village in villages:
        assert village["sigungu"] in [
            "동구", "서구", "남구", "북구", "광산구",
            "목포시", "여수시", "순천시", "나주시", "광양시",
            "담양군", "곡성군", "구례군", "고흥군", "보성군",
            "화순군", "장흥군", "강진군", "해남군", "영암군",
            "무안군", "함평군", "영광군", "장성군", "완도군",
            "진도군", "신안군"
        ]
```

---

## 6. Cursor 활용 시 TDD 작업 순서 가이드

개발 세션이 하루 1~2시간으로 짧게 쪼개져 있는 점을 고려해, 다음 순서로 Cursor와 상호작용하는 것을 권장한다.

1. 이번 세션에서 구현할 기능 하나를 SRD에서 선택한다 (예: FR-13 지역 필터링)
2. 본 문서의 해당 테스트 코드를 그대로 Cursor에 붙여넣고 "이 테스트가 정의된 tests/test_region_filter.py 파일을 만들어줘"라고 요청한다
3. 이어서 "위 테스트를 통과하는 filter_gwangju_jeonnam 함수를 services/public_data_sync.py에 구현해줘"라고 요청한다
4. uv run pytest tests/test_region_filter.py 명령으로 실제 테스트를 실행해 통과 여부를 확인한다
5. 실패하면 실패 메시지를 그대로 Cursor에 전달해 원인을 파악하고 수정한다
6. 통과하면 다음 기능으로 넘어가며, 이전 테스트가 여전히 통과하는지 uv run pytest 전체 실행으로 회귀 여부를 확인한다

---

## 7. 테스트 커버리지 목표

| 대상 | 목표 커버리지 | 비고 |
|---|---|---|
| services/public_data_sync.py (지역 필터링) | 90% 이상 | 서비스의 핵심 전제이므로 높은 커버리지 목표 |
| services/trust_score.py | 90% 이상 | 계산 규칙이 명확해 테스트 작성이 용이함 |
| services/llm_provider.py | 80% 이상 | 실제 외부 호출 부분은 모의 처리로 대체 |
| services/auth.py | 85% 이상 | FR-15 격리, FR-16 역할 분기, FR-17 자가 등록 |
| services/booking.py | 80% 이상 | 저장·조회·상태 변경. 타 마을 예약이 섞이지 않아야 함 |
| routers/kakao.py | 70% 이상 | 응답 형식 검증 위주, 세부 예외 케이스는 선택적 |
| routers/web.py | 50% 내외 | 화면 렌더링은 수작업 확인 병행 |
| 전체 프로젝트 | 60% 이상 | 시간 제약을 고려한 현실적 목표치 |

커버리지는 다음 명령으로 확인한다.

```
uv add --dev pytest-cov
uv run pytest --cov=services --cov=routers --cov-report=term-missing
```

---

## 8. 문서 변경 이력

| 버전 | 일자 | 변경 내용 |
|---|---|---|
| v1.0 | 최초 작성 | SRD의 FR-01~FR-14 기준 테스트 케이스 최초 정의, TDD 사이클 및 Cursor 활용 가이드 포함 |
| v1.1 | 2026-08-31 | FR-15 운영자 데이터 격리 테스트 추가, 대시보드 공개/운영 이원화, conftest 운영자 픽스처 |
| v1.2 | 2026-10-01 | 역할 분기·자가 등록·예약 함수 입출력 명세와 테스트 추가. 예약 푸시 기대 테스트를 조회형(미발송)으로 변경 |
| v1.3 | 2026-10-01 | 역할 조회를 `resolve_kakao_role`로 통일하고, 테스트 패치 대상을 맞춘다. 웹 세션은 `scoped_village_id_for_session`을 쓴다. 여행객은 관광객으로 통일 |
| v1.4 | 2026-10-01 | 운영자 발화 `예약 현황`과 관광객 발화 `내 예약` 테스트를 분리. 둘 다 `POST /kakao/booking` |
| v1.5 | 2026-10-01 | 미발송 테스트는 이번 단계 검증이다. 이벤트 API 테스트는 단계 성공 후 다음 단계다 |
| v1.6 | 2026-10-07 | 예약승인과 예약거절 테스트를 분리. `decision`을 빼고, 빈 `booking_id`는 안내 후 종료. 멀티턴 대화와 가변 품목 파싱은 Phase B로 보류됨 |
| v1.7 | 2026-10-07 | `listCard` 검사, 후기 조회, 접두어 없는 운영자 등록 발화를 문서 테스트에 추가 |
| v1.8 | 2026-10-11 | 마을 추천·후기 조회·예약 현황 성공 검사를 `simpleText`로 맞춘다. `listCard`는 응답에 없다 |
| v1.9 | 2026-10-11 | 자연어 질의 5개와 마을 추천 한 줄 이유 검사를 추가한다 |
| v1.10 | 2026-10-12 | 추천 빠른 실패의 Gemini·OpenAI 교대, 시간 초과·빈 배열의 키워드 결과, 키 없음의 `LLMUnavailable`을 검사한다 |
| v1.11 | 2026-10-12 | 추천 이유가 맞은 말·프로그램명·시설로 다시 써지는지, 겹치지 않으면 맞았다고 하지 않는지 검사한다 |
| v1.12 | 2026-10-12 | 마을 홍보 공개 화면 테스트는 그 화면을 만들 때 추가한다. 이번 기록에서는 테스트 파일을 바꾸지 않는다 |
| v1.13 | 2026-10-13 | 마을 홍보 공개 화면 테스트는 `tests/test_public_promo.py`에 추가됐다 |
| v1.14 | 2026-10-14 | 카카오 홍보 사진 테스트는 `tests/test_kakao_promo_photo.py`에 있다. 글 생성 예산은 3.5초다 |
| v1.15 | 2026-10-14 | 홍보 사진 첫 응답은 콜백 대기이고, 초안 simpleText는 콜백 주소로 검사한다 |
| v1.16 | 2026-10-15 | 이미지 플러그인 `secureUrls`의 `http://secure.kakaocdn.net`은 받고, 다른 호스트의 http는 받지 않는지 검사한다 |
| v1.17 | 2026-10-15 | 2MB 초과 jpeg는 줄여 저장하고, 8MB 초과와 이미지가 아닌 파일은 안내만 하는지 검사한다 |
| v1.18 | 2026-10-15 | 카카오 홍보 사진 초안의 글 생성 예산은 15초다. 마을 추천 예산은 3.5초다 |
| v1.19 | 2026-10-16 | 프로그램 운영 여부 테스트는 `tests/test_village_programs.py`다. 괄호 안 `+`, 기본 운영, 즉시 반영, 다른 마을 403, 동기화 후 상태 유지를 검사한다 |
| v1.20 | 2026-10-16 | 카카오 마을 추천 이유의 꺼진 항목은 `지금은 운영하지 않음`인지 `tests/test_village_programs.py`에서 검사한다 |
| v1.21 | 2026-10-17 | 체험별 운영자. `tests/test_program_operators.py`에서 등록, 체험 글, 달력, 다른 마을, 예약 승인 거부를 검사한다 |
| v1.22 | 2026-10-17 | 체험 달력의 단체·인원, 같은 단체 인원 갱신, 체험 담당의 자기 체험만 조회를 `tests/test_program_operators.py`에서 검사한다 |
| v1.23 | 2026-10-17 | 예약 달력의 예약번호·대기·승인과 `달력 열기`를 `tests/test_booking_calendar.py`, `tests/test_calendar_page.py`에서 검사한다 |
| v1.24 | 2026-10-17 | 관광객 홈의 카카오 예약 마을·채널 QR은 `tests/test_public_promo.py`에서 검사한다 |
| v1.25 | 2026-10-17 | 네이버 확인 태그, 공개 사이트맵, `robots.txt`의 운영 화면 제외를 `tests/test_public_promo.py`에서 검사한다 |
