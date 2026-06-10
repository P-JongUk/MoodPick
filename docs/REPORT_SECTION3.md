# 3. 이론적 계산 및 Simulation

## 3.1 연구 범위

본 프로젝트(MoodPick)는 **웹·API 기반 심리 상담 지원 시스템**이다. **기구해석, 유한요소법(FEA), 유체·열 등 전통적 CAE(Computer Aided Engineering) 시뮬레이션은 구현되어 있지 않다.**

본 절에서는 코드베이스에 실제로 구현된 **정량 규칙·산술 연산(이론적 계산)** 과 **고차원 벡터 공간에서의 유사도 기반 검색(RAG)** 을 정리한다.

---

## 3.2 문진 척도 변환 및 세션별 변화량(Delta)

### 3.2.1 이모지 응답 → 수치 점수

사전·사후 문진에서 선택한 이모지 값을 **1~5 리커트형 척도**로 변환하여 `survey_responses.score`에 저장한다.

| emoji_value | score |
|-------------|-------|
| great       | 5     |
| good        | 4     |
| neutral     | 3     |
| low         | 2     |
| bad         | 1     |

- 정의: `backend/app/routers/survey.py` — `MOOD_EMOJI_MAP`
- 저장 시 알 수 없는 값은 **기본값 3** (`MOOD_EMOJI_MAP.get(payload.emoji_value, 3)`)

프론트엔드에도 동일 척도가 상수로 존재하나, **서버 저장 로직이 기준**이다.

- 참고: `frontend/lib/sessionData.ts` — `moodScoreMap`

### 3.2.2 문항별 변화량 및 “개선” 판정

동일 `session_id` 내에서 `question_key`별로 사전(`pre`)·사후(`post`) 점수를 짝지어 차이를 계산한다.

- **문항별 변화량**: \(\Delta_k = s_{\text{post},k} - s_{\text{pre},k}\)
- **평균 변화량**: \(\overline{\Delta} = \frac{1}{|K|}\sum_{k \in K} \Delta_k\)
- **개선 여부**: `improved = (\overline{\Delta} > 0)` (엄밀한 통계 검정 아님, 규칙 기반)

- 구현: `backend/app/routers/survey.py` — `GET /survey/delta/{session_id}` (`get_survey_delta`)

---

## 3.3 감정 기록 요약 및 추이(Trend)

### 3.3.1 데이터 및 평균

- 대상: 해당 사용자의 상담 세션에 연결된 `survey_responses` 중, 최근 \(N\)일(기본 7일) 구간의 `mood_general` 응답을 세션별 대표값으로 정리한 뒤 계산
- **평균 점수**: 산술평균, 반환 시 소수 둘째 자리 반올림
- 대표값 규칙: 같은 세션에 pre/post가 모두 있으면 `post`를 우선하고, 없으면 `pre`를 사용함

- 구현: `backend/app/routers/emotion.py` — `GET /emotion/summary/{user_id}`

### 3.3.2 추이 분류 규칙

`created_at` 내림차순으로 정렬된 `scores`에 대해:

- `recent` = 앞에서 **3개** (`scores[:3]`)
- `earlier` = 그다음 **3개** (`scores[3:6]`)

두 집합이 모두 존재할 때만:

- `recent_avg > earlier_avg + 0.5` → `trend = "improving"`
- `recent_avg < earlier_avg - 0.5` → `trend = "declining"`
- 그 외 → `trend = "stable"`

세션이 없거나 응답이 없으면 `average_score = 3.0`, `trend = "stable"` 등 **기본값**을 반환한다.

> 참고: 이 규칙은 전반적 분위기를 빠르게 보여주기 위한 휴리스틱이며, 통계적 유의성 검정은 아니다.

- 구현: `backend/app/routers/emotion.py` — `get_emotion_summary`

---

## 3.4 텍스트 기반 감정 분석(규칙 기반 모델)

`POST /emotion/analyze`는 **학습된 회귀·분류 모델이 아니라**, 입력 문자열에 **한국어 키워드 포함 여부**를 검사하는 규칙 엔진이다.

- 입력과 키워드를 소문자화한 뒤 부분 문자열 매칭
- **첫 번째로 매칭된 키워드**에 대응하는 감정 라벨과 추천 목록을 선택함
- 매칭 실패 시 `emotion = "neutral"`과 기본 추천 목록을 반환함
- 현재 API 응답 스키마는 `emotion`과 `recommendations`만 포함하며, `intensity`는 내부 계산값으로만 사용됨

- 구현: `backend/app/routers/emotion.py` — `analyze_emotion`

---

## 3.5 RAG: 임베딩 유사도 검색

### 3.5.1 DB 함수 `match_rag_chunks`

- 질의 벡터: `vector(1536)` (pgvector)
- 각 청크에 대해:

  \[
  \text{similarity} = 1 - (c.\text{embedding} \Leftrightarrow \text{query\_embedding})
  \]

  여기서 `\Leftrightarrow`는 **코사인 거리** 연산(pgvector)이다.

- **정렬**: 코사인 거리 **오름차순** (가까울수록 우선)
- **반환 개수**: `limit greatest(match_count, 1)`
- 선택적 필터: `filter_user_id`가 주어지면 해당 `user_id` 청크만

- 구현: `db/migrations/002_vector_tables.sql` — `public.match_rag_chunks`
- 인덱스: `rag_chunks.embedding`에 `ivfflat` + `vector_cosine_ops`

### 3.5.2 백엔드 API

- `POST /rag/search`: 클라이언트가 넘긴 `query_embedding` 길이가 설정값(`rag_embedding_dimensions`, 기본 **1536**)과 일치하는지 검증한 뒤, 현재 로그인 사용자 범위로 RPC 호출
- `POST /rag/search-by-text`: 텍스트 → 임베딩 생성 후 동일 검색
- `user_id`는 선택 입력이지만, 서버는 항상 인증된 현재 사용자 기준으로 검색 범위를 고정한다.

- 구현: `backend/app/routers/rag.py`, 차원 기본값 `backend/app/config.py`

---

## 3.6 UI 표시용 점수 구간 매핑

대시보드에서 **같은 숫자 점수**를 이모지·라벨·캘린더 색으로 바꿀 때 **고정 임계값**을 사용한다 (물리 방정식이 아닌 **시각 인코딩 규칙**).

| 함수 | 임계값 (이상) | 용도 |
|------|----------------|------|
| `scoreToEmoji` / `scoreToLabel` | 4.5, 3.5, 2.5, 1.5 | 이모지·텍스트 라벨 |
| `scoreToCalendarColor` | 4, 3 | 캘린더 셀 배경 구간 |

- 구현: `frontend/components/moodpick-dashboard.tsx`

---

## 3.7 소결

| 구분 | 내용 |
|------|------|
| CAE / 구조·물리 시뮬레이션 | **해당 없음** |
| 이론적 계산 | 문진 **척도 매핑**, **Δ·평균**, **임계값 기반 trend**, **키워드 규칙 기반 감정 분석** |
| Simulation (정보 검색 관점) | **1536차원 임베딩 공간**에서 **코사인 거리 기반** 근접 청크 탐색(RAG) |

---

## 참고 파일 목록

- `backend/app/routers/survey.py`
- `backend/app/routers/emotion.py`
- `backend/app/routers/rag.py`
- `backend/app/config.py`
- `db/migrations/002_vector_tables.sql`
- `frontend/lib/sessionData.ts`
- `frontend/components/moodpick-dashboard.tsx`
