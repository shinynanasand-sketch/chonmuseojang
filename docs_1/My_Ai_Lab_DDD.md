# 체험마을 AI사무장 - 데이터 딕셔너리 (Data Dictionary)

## 0. 문서 목적

TRD의 DB 스키마(테이블/컬럼 정의)보다 한 단계 더 상세하게, 각 필드가 실제로 어떤 의미를 갖고 어떤 값이 들어오는지, 공공데이터 원본 필드명과 우리 시스템의 필드명이 어떻게 매핑되는지를 기록한다. 공공데이터 API를 실제로 호출해보기 전까지는 필드명이 추정치일 수 있으므로, 최초 호출 후 반드시 이 문서를 실제 값으로 갱신한다.

---

## 1. villages_cache 테이블 (공공데이터 동기화 결과)

| 우리 시스템 필드명 | 데이터 타입 | 공공데이터 원본 필드명(추정, 실제 호출 후 확정 필요) | 설명 | 예시값 | 필수 여부 | 비고 |
|---|---|---|---|---|---|---|
| village_id | TEXT | 관리번호 또는 고유식별자 | 마을 고유 식별자 | "V0001" | 필수 | 원본에 고유키가 없으면 마을명+주소 조합으로 자체 생성 검토 |
| village_name | TEXT | 체험마을명 | 마을 공식 명칭 | "예시 갯벌마을" | 필수 | |
| sido | TEXT | 시도명 | 광역 행정구역명(신/구 명칭 혼재 가능) | "전라남도" 또는 "전남광주통합특별시" | 필수 | 필터링 보조 기준으로만 사용 |
| sigungu | TEXT | 시군구명 | 기초 행정구역명 | "신안군" | 필수 | 필터링 1차 기준(가장 신뢰) |
| program_type | TEXT | 체험프로그램구분 | 체험 대분류(농사체험/갯벌체험 등) | "갯벌체험" | 선택 | 값 종류가 확정되면 별도 코드표로 관리 검토 |
| program_name | TEXT | 체험프로그램명 | 구체적 프로그램명 | "갯벌 조개잡이 체험" | 선택 | |
| address | TEXT | 소재지도로명주소 | 도로명 주소 | "전남 신안군 ..." | 선택 | 지번주소 필드도 별도 존재 시 추가 컬럼 검토 |
| latitude | DOUBLE PRECISION | 위도 | 지도 표시용 좌표 | 34.9 | 필수(지도 기능용) | 결측 시 지도에서 제외 처리 |
| longitude | DOUBLE PRECISION | 경도 | 지도 표시용 좌표 | 126.1 | 필수(지도 기능용) | 결측 시 지도에서 제외 처리 |
| facilities | TEXT | 보유시설정보 | 숙박/식당/체험장 등 보유 시설 | "숙박시설, 체험장" | 선택 | 콤마 구분 문자열로 저장, 필요 시 배열형 변환 검토 |
| representative_name | TEXT | 대표자명 | 마을 대표자 성명 | "홍길동" | 선택 | 개인정보이므로 노출 범위 검토 필요 |
| phone | TEXT | 전화번호 | 연락처 | "061-000-0000" | 선택 | |
| homepage_url | TEXT | 홈페이지 | 마을 자체 또는 지자체 홈페이지 링크 | "http://..." | 선택 | |
| grade | TEXT | (보조 데이터셋: 으뜸촌 정보에서 매핑) | 정부 인증 등급 | "으뜸촌" 또는 NULL | 선택 | 별도 데이터셋과 마을명/주소 매칭 필요, 매칭 실패 가능성 있음 |
| trust_score | NUMERIC | (자체 계산) | 신뢰도 점수 | 82 | 시스템 자동 계산 | trust_score.py 로직 결과 |
| registration_code | TEXT | (자체 발급) | 운영자 자가 등록 코드 | "GB-001" | 선택 | 공공데이터 동기화 upsert는 이 값을 덮어쓰지 않는다 |
| synced_at | TIMESTAMP | (자체 기록) | 마지막 동기화 시각 | 2026-10-05 09:00:00 | 시스템 자동 기록 | 최신성 점수 계산에 사용 |

주의: 위 "공공데이터 원본 필드명"은 국문 표준 항목명 기준 추정치이며, 실제 오픈API 응답의 영문 키(camelCase 또는 snake_case)는 다를 수 있다. 최초 API 호출 성공 후 실제 응답 JSON의 키 이름을 아래 2장 표에 반드시 기록한다.

---

## 2. 실제 API 응답 필드 매핑표

`services/public_data_sync.py`의 `FIELD_ALIASES`에 추정 매핑을 반영했다. 공공 API 실제 호출 후 아래 표를 확정·갱신한다.

| 실제 API 응답 키(원본) | 우리 시스템 필드명 | 시연 시드 예시값 | 비고 |
|---|---|---|---|
| exprnVilageNm | village_name | 예시 갯벌마을 | 15013113 확정 키 |
| ctprvnNm | sido | 전라남도 | 신·구 명칭 혼재 |
| signguNm | sigungu | 신안군 | 필터 1차 기준 |
| exprnSe | program_type | 갯벌체험 | |
| exprnCn | program_name | 갯벌 조개잡이 체험 | |
| rdnmadr | address | 전남 신안군 ... | 지번 `lnmadr`는 도로명주소가 없을 때만 |
| latitude | latitude | 34.9 | |
| longitude | longitude | 126.1 | |
| (없음) | village_id | V001 | 마을명+시군구+주소 SHA-256, `PD` + 12자리 |

시연용 시드(`services/demo_data.py`)는 API 키 없을 때 `sync_village_data(use_demo_fallback=True)`로 로드된다.

---

## 3. operators 테이블 (운영자 계정)

| 필드명 | 데이터 타입 | 설명 | 예시값 | 필수 여부 | 값의 출처 | 비고 |
|---|---|---|---|---|---|---|
| operator_id | SERIAL | 운영자 고유번호(자동증가) | 1 | 자동 생성 | DB | PK |
| kakao_user_id | TEXT | 카카오 사용자 식별자 | "kakao_owner_xyz789" | **필수 (NOT NULL, UNIQUE)** | 카카오 스킬 payload | **개인정보**. 역할 분기의 기준 |
| village_id | TEXT | 담당 마을 식별자 | "V0001" | **필수 (NOT NULL, FK)** | villages_cache 참조 | 마을 운영자는 마을당 1명 |
| role | TEXT | `village` 또는 `program` | "village" | **필수** | 자가 등록 | 기존 행은 `village` |
| program_key | TEXT | 체험 담당의 프로그램 키 | (해시) | 체험 담당만 | `program_name` 라벨 | 마을 운영자는 NULL |
| operator_name | TEXT | 운영자 이름 | "갯벌마을 운영자" | **필수** | 자가 등록 | |
| registered_at | TIMESTAMP | 등록 시각 | 2026-10-01 10:00:00 | **필수** | DB 기본값 NOW() | |
| login_id | TEXT | 웹 대시보드 로그인 ID | "owner_v0001" | 선택 | 추가 로그인 | **개인정보**. 카카오 id의 대체 수단이 아님 |
| password_hash | TEXT | 비밀번호 해시 | (해시값) | 선택 | 추가 로그인 | **개인정보**. 평문 저장 금지 |
| is_active | BOOLEAN | 계정 활성 여부 | true | 필수(기본 true) | 시스템 관리 | false 시 로그인·API 거부 |
| last_login_at | TIMESTAMP | 마지막 로그인 시각 | 2026-09-15 09:00:00 | 선택 | 시스템 기록 | |

값 검증 규칙:
- `village_id`는 `villages_cache`에 존재하는 값만 허용(FK). **NULL 불가**
- `kakao_user_id`는 NOT NULL UNIQUE다. 한 카카오 계정은 운영자 행 하나다
- `role=village`는 마을당 1명이다. `role=program`은 그 마을 체험당 1명이고 `program_key`가 필수다
- 첫 자가 등록은 마을 운영자다. 이후 등록은 마을 프로그램 라벨이 맞고 담당이 없을 때만 체험 담당이 된다
- 이미 등록된 행은 `role=village`다

---

## 4. bookings 테이블

| 필드명 | 데이터 타입 | 설명 | 예시값 | 필수 여부 | 값의 출처 |
|---|---|---|---|---|---|
| booking_id | SERIAL | 예약 고유번호(자동증가) | 1 | 자동 생성 | DB |
| village_id | TEXT | 예약 대상 마을 | "V0001" | **필수 (NOT NULL, FK)** | villages_cache 참조 | **스키마 레벨 강제**. `village_id` 없이 INSERT 불가 |
| customer_kakao_id | TEXT | 예약자의 카카오 사용자 식별자 | "kakao_abc123" | 필수 | 카카오 스킬 요청 payload |
| customer_name | TEXT | 예약자 성명(수집 시) | "홍길동" | 선택 | 사용자 발화 또는 별도 입력 |
| visit_date | DATE | 방문 희망일 | 2026-09-20 | 필수 | 사용자 발화 파싱 결과 |
| num_people | INTEGER | 방문 인원수 | 3 | 필수 | 사용자 발화 파싱 결과 |
| status | TEXT | 예약 상태 | "pending" / "confirmed" / "rejected" | 필수 | 시스템 관리 |
| created_at | TIMESTAMP | 예약 생성 시각 | 2026-09-15 10:00:00 | 자동 생성 | DB |
| updated_at | TIMESTAMP | 마지막 상태 변경 시각 | 2026-09-16 09:00:00 | 자동 갱신 | DB |

값 검증 규칙:
- `village_id`는 NOT NULL FK. `villages_cache`에 없는 값 또는 NULL이면 INSERT 실패
- num_people은 1 이상의 정수만 허용
- visit_date는 오늘 날짜 이후여야 함(과거 날짜 예약 방지)
- status는 pending/confirmed/rejected 세 값만 허용(DB CHECK 제약조건 적용)

---

## 5. reviews 테이블

| 필드명 | 데이터 타입 | 설명 | 예시값 | 필수 여부 | 값의 출처 |
|---|---|---|---|---|---|
| review_id | SERIAL | 후기 고유번호(자동증가) | 1 | 자동 생성 | DB |
| village_id | TEXT | 후기 대상 마을 | "V0001" | **필수 (NOT NULL, FK)** | villages_cache 참조 | **스키마 레벨 강제**. `village_id` 없이 INSERT 불가 |
| booking_id | INTEGER | 연관된 예약 번호 | 1 | 선택 | bookings 참조(예약 없이 후기만 남기는 경우 NULL 허용 여부 결정 필요) |
| customer_kakao_id | TEXT | 작성자의 카카오 사용자 식별자 | "kakao_abc123" | 필수 | 카카오 스킬 요청 payload |
| rating | INTEGER | 평점(1~5) | 5 | 선택 | 사용자 입력 |
| comment | TEXT | 후기 본문 | "아이들이 좋아했어요" | 선택 | 사용자 발화 |
| photo_url | TEXT | 첨부 사진 URL | "https://.../photo.jpg" | 선택 | 카카오에서 전달된 이미지 URL |
| sentiment | TEXT | 감성분석 결과 | "긍정" / "부정" / "중립" | 시스템 자동 계산 | LLM 감성분석 결과 |
| created_at | TIMESTAMP | 후기 생성 시각 | 2026-09-22 15:00:00 | 자동 생성 | DB |

값 검증 규칙:
- `village_id`는 NOT NULL FK. `villages_cache`에 없는 값 또는 NULL이면 INSERT 실패
- rating은 1 이상 5 이하의 정수만 허용(DB CHECK 제약조건 적용)
- comment 또는 rating 중 최소 하나는 존재해야 함(둘 다 없는 빈 후기 방지, 애플리케이션 레벨에서 검증)

---

## 6. contents 테이블 (운영 콘텐츠)

| 필드명 | 데이터 타입 | 설명 | 예시값 | 필수 여부 | 값의 출처 | 비고 |
|---|---|---|---|---|---|---|
| content_id | SERIAL | 콘텐츠 고유번호(자동증가) | 1 | 자동 생성 | DB | PK |
| village_id | TEXT | 소속 마을 식별자 | "V0001" | **필수 (NOT NULL, FK)** | villages_cache 참조 | **스키마 레벨 강제** |
| operator_id | INTEGER | 작성 운영자 | 1 | 선택 | operators 참조 | 작성자 추적용 |
| content_type | TEXT | 콘텐츠 유형 | "소개글" | 필수 | 시스템/운영자 | 6-4 코드값 참조 |
| title | TEXT | 제목 | "가을 갯벌체험 안내" | 선택 | LLM 생성 또는 운영자 입력 | |
| body | TEXT | 본문 | "신안군 ..." | 필수 | LLM 생성 또는 운영자 입력 | |
| photo_url | TEXT | 첨부 사진 URL | "https://.../photo.jpg" | 선택 | 운영자 업로드 | `http` 주소일 때만 관광객 화면에 표시 |
| is_public | BOOLEAN | 관광객 공개 여부 | false | 필수 | 운영자 공개 | NOT NULL, 기본값 false. 최신 소개글·SNS홍보문구만 true |
| created_at | TIMESTAMP | 생성 시각 | 2026-09-20 14:00:00 | 자동 생성 | DB | |

값 검증 규칙:
- `village_id`는 NOT NULL FK. 운영자가 생성할 때 서버가 `current_operator.village_id`로 주입
- `body`는 빈 문자열 불가
- 관광객 공개 대상은 마을별 최신 소개글·SNS홍보문구와 선택 사진이다. 운영자가 공개한 행만 `is_public`이 true다. 기본값은 공개 안 함이다. 관광객 후기(`reviews`)와 섞지 않는다
- 쓰기는 운영자만 한다. 공개 읽기 화면은 `/village/{village_id}`이고 `chonmuseojang.vercel.app`에 배포되어 있다. `content_public.sql`과 `content_photos_bucket.sql`은 적용되어 있다

---

## 6-2. village_program_status (프로그램 운영 여부)

공공데이터 동기화가 덮는 `villages_cache.program_name`·`program_type`과 별도다. 운영자가 끈 항목만 행이 생긴다. 행이 없으면 그 항목은 운영 중이다.

| 필드명 | 데이터 타입 | 설명 | 예시값 | 필수 여부 | 값의 출처 |
|---|---|---|---|---|---|
| village_id | TEXT | 소속 마을 | "V0001" | **필수 (NOT NULL, FK)** | `current_operator.village_id` |
| program_key | TEXT | 정규화한 항목 글의 SHA-256 앞 16자리 | "ab12cd34ef567890" | **필수** | 항목 글 |
| label | TEXT | 화면에 보이는 항목 | "기타(영농체험+먹거리체험)" | **필수** | `program_name`, 없으면 `program_type` |
| is_operating | BOOLEAN | 지금 운영 중인지 | false | **필수** | 운영자 |
| updated_at | TIMESTAMP | 마지막 변경 시각 | 2026-10-16 21:00:00 | **필수** | 서버 |

값 검증 규칙:
- `(village_id, program_key)`는 유일하다
- 항목은 `program_name`을 괄호 밖 `+`와 줄바꿈으로 나눈다. `기타(영농체험+먹거리체험)` 안의 `+`는 자르지 않는다. `program_name`이 비어 있으면 `program_type`을 같은 방식으로 나눈다
- 다른 마을 번호로 바꾸면 403이다. 그 마을 글에 없는 항목은 저장하지 않는다
- `villages_cache` upsert는 이 표를 갱신하지 않는다

---

## 7. sync_logs 테이블

| 필드명 | 데이터 타입 | 설명 | 예시값 |
|---|---|---|---|
| log_id | SERIAL | 로그 고유번호 | 1 |
| source | TEXT | 동기화 대상 원천 | "public_data_village" |
| total_fetched | INTEGER | API로부터 수신한 전체 건수 | 320 |
| total_filtered | INTEGER | 지역 필터링 후 남은 건수 | 87 |
| status | TEXT | 성공/실패 여부 | "success" / "failure" |
| message | TEXT | 실패 시 오류 메시지 | "타임아웃 발생" |
| executed_at | TIMESTAMP | 실행 시각 | 2026-10-05 09:00:00 |

---

## 8. 코드값 정의 (참고용 목록)

### 8-1. program_type (체험프로그램구분) 예상 값 목록

실제 공공데이터 확인 후 갱신 필요. 일반적으로 아래와 같은 대분류가 사용될 것으로 예상된다.

| 값 | 설명 |
|---|---|
| 농사체험 | 농작물 수확, 재배 체험 등 |
| 갯벌체험 | 갯벌 생태, 조개잡이 등 |
| 전통문화체험 | 한옥, 전통놀이 등 |
| 음식체험 | 요리, 김장 등 |
| 만들기체험 | 공예, 짚풀공예 등 |
| 생태체험 | 자연관찰, 숲체험 등 |

### 8-2. status (예약 상태) 값 목록

| 값 | 의미 |
|---|---|
| pending | 접수됨, 운영자 확인 대기 중. 화면 문구는 대기다 |
| confirmed | 운영자가 승인함. 화면 문구는 승인이다 |
| rejected | 운영자가 거절함. 화면 문구는 거절이다 |

### 8-3. sentiment (감성분석 결과) 값 목록

| 값 | 의미 |
|---|---|
| 긍정 | 후기 내용이 전반적으로 만족스러움을 나타냄 |
| 부정 | 후기 내용이 전반적으로 불만족을 나타냄 |
| 중립 | 명확한 감정 표현이 없거나 혼재됨 |

### 8-4. content_type (운영 콘텐츠 유형) 값 목록

| 값 | 설명 |
|---|---|
| 소개글 | 마을 소개 페이지용 본문 |
| SNS홍보문구 | SNS·카카오 채널 게시용 짧은 홍보 문구 |
| 체험안내 | 특정 체험 프로그램 안내 문구 |
| 기타 | 위 분류에 해당하지 않는 운영 콘텐츠 |

### 8-5. 데이터 격리(멀티테넌시) 규칙

| 규칙 | 내용 |
|---|---|
| 테넌트 키 | 모든 운영 데이터(`bookings`, `reviews`, `contents`, `village_program_status`, `program_notes`, `experience_calendar`)는 `village_id`로 `villages_cache`에 귀속 |
| NOT NULL 강제 | `village_id`가 NULL인 레코드는 DB INSERT 자체가 실패함 |
| 운영자 역할 | 마을 운영자(`role=village`)는 마을당 1명. 체험 담당(`role=program`)은 체험당 1명. `kakao_user_id`는 UNIQUE |
| 체험 글 | `program_notes`는 마을·`program_key`당 1건. 담당자만 갱신하고, 같은 마을 운영자는 읽기만 한다 |
| 체험 달력 | `experience_calendar`는 마을·체험·날짜·단체당 1건. `group_name`은 단체 이름, `num_people`은 인원이다. 마을 운영자만 등록하고, 체험 담당은 자기 체험만 읽는다. 체험 이름이 있는 예약은 그 날짜에 보이고, 이름이 없으면 `체험 미정`이며 체험 담당 조회에서는 빠진다. 관광객 API에는 넣지 않는다 |
| 접근 범위 | 운영자 API는 `current_operator.village_id`와 일치하는 행만 조회·변경. 예약·후기·홍보 쓰기는 마을 운영자만 |
| 관광객 예외 | `villages_cache`는 추천·지도 목적으로 전체 마을 읽기 허용(운영 원장 미포함) |

---

## 9. 문서 관리 원칙

1. 공공데이터 API를 처음 호출한 직후 2장의 실제 응답 필드 매핑표를 반드시 채운다
2. 스키마가 변경되면 TRD의 DB 스키마 섹션과 이 문서를 동시에 갱신한다
3. 개인정보에 해당하는 필드(`representative_name`, `phone`, `customer_kakao_id`, `kakao_user_id`, `login_id`, `password_hash` 등)는 별도로 표시해두어 노출 범위를 관리한다
4. 멀티테넌시 스키마 변경 시 TRD 8장·SRD FR-15와 이 문서를 동시에 갱신한다
