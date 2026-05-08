# 추천 로직 v2.1 테스트 시나리오

> 마이그레이션(`001~003.sql`) 실행 완료 후 아래 시나리오를 순서대로 진행합니다.
> 테스트에 사용할 `user_id`와 `session_id`는 Supabase에 실제 존재하는 값을 사용하세요.

---

## Scenario 1 — 콜드스타트 (좋아요 0개)

**목적**: 좋아요 기록이 없는 신규 사용자도 추천이 정상적으로 동작하는지 확인

**전제 조건**
- `user_taste_vectors` 테이블에 해당 `user_id` 레코드 없음
- `content_feedback` 테이블에 해당 `user_id`의 `like` 기록 없음

**실행 방법**

```bash
# 상담 API 호출 (실제 엔드포인트에 맞게 조정)
curl -X POST http://localhost:8000/api/counseling/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "<신규 사용자 UUID>",
    "session_id": "<세션 UUID>",
    "message": "요즘 너무 불안하고 잠도 잘 못 자고 있어요"
  }'
```

**기대 결과**
- [-] HTTP 200 응답, `recommended_content` 필드에 `video_id`, `title` 존재
- [-] `content_embeddings` 테이블에 추천된 영상의 임베딩 캐시가 생성됨
- [-] `recommendation_log` 테이블에 레코드 1개 삽입됨 (`strategy_version = "v2.1"`)
- [-] `user_taste_vectors` 테이블에는 레코드 **없음** (좋아요 3개 미달)

**Supabase 확인 쿼리**
```sql
SELECT * FROM recommendation_log ORDER BY created_at DESC LIMIT 1;
SELECT * FROM content_embeddings ORDER BY created_at DESC LIMIT 5;
SELECT * FROM user_taste_vectors WHERE user_id = '<사용자 UUID>';  -- 결과 없어야 함
```

---

## Scenario 2 — 좋아요 누적 → 취향 벡터 자동 생성

**목적**: 좋아요 3개 이상이 되는 순간 `user_taste_vectors`가 자동 생성되는지 확인

**전제 조건**
- Scenario 1 이후, 동일 사용자가 추천된 영상에 좋아요를 누름

**실행 방법**

```bash
# Step 1: 좋아요 1개
curl -X POST http://localhost:8000/api/content/feedback \
  -H "Content-Type: application/json" \
  -d '{"user_id": "<UUID>", "content_id": "<video_id_1>", "feedback": "like"}'

# Step 2: 좋아요 2개
curl -X POST http://localhost:8000/api/content/feedback \
  -H "Content-Type: application/json" \
  -d '{"user_id": "<UUID>", "content_id": "<video_id_2>", "feedback": "like"}'

# Step 3: 좋아요 3개 (벡터 생성 기대)
curl -X POST http://localhost:8000/api/content/feedback \
  -H "Content-Type: application/json" \
  -d '{"user_id": "<UUID>", "content_id": "<video_id_3>", "feedback": "like"}'
```

**기대 결과**
- [-] 3번째 `like` API 호출 후 수 초 내에 `user_taste_vectors` 테이블에 레코드 생성
- [-] `source_count = 3`, `strategy = "time_weighted_avg"` 값 확인
- [-] `embedding` 컬럼이 1536차원 벡터로 채워짐

**Supabase 확인 쿼리**
```sql
SELECT user_id, source_count, strategy, updated_at
FROM user_taste_vectors
WHERE user_id = '<사용자 UUID>';
```

---

## Scenario 3 — 취향 반영 추천 (사용자별 다른 결과)

**목적**: 좋아요 취향이 다른 두 사용자가 동일한 감정 메시지를 보냈을 때, 다른 영상을 추천받는지 확인

**전제 조건**
- 사용자 A: 잔잔한 피아노/클래식 영상에 좋아요 3개 이상
- 사용자 B: 신나는 EDM/팝 영상에 좋아요 3개 이상

**실행 방법**

```bash
# 사용자 A 상담 요청
curl -X POST http://localhost:8000/api/counseling/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "<사용자A UUID>", "session_id": "<세션A>", "message": "오늘 기분이 우울하네요"}'

# 사용자 B 상담 요청
curl -X POST http://localhost:8000/api/counseling/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "<사용자B UUID>", "session_id": "<세션B>", "message": "오늘 기분이 우울하네요"}'
```

**기대 결과**
- [-] 사용자 A와 사용자 B가 받은 `video_id`가 **다름**
- [-] `recommendation_log`에서 두 레코드의 `selected_score`와 `candidate_pool` 비교 시, 동일 후보라도 점수 순위가 다름
- [-] 두 사용자 모두 자기 좋아요 톤(장르/스타일)이 `search_query` 와 상위 영상에 반영되고, 그 위에 현재 감정 강도에 맞는 형용사(예: 강도 ≥0.7 이면 `chill`/`calm`, 0.4~0.7 이면 `feel-good`/`uplifting`)가 가미됨

> **참고**: 검색 쿼리 생성은 "역할 분담" 모델을 따른다. liked_hints가 장르를 결정하고, 감정·강도가 형용사를 결정한다. 따라서 강도가 높으면 양쪽 모두 차분한 형용사로 수렴할 수 있으나, 장르(EDM vs 클래식 등)는 사용자별로 보존되어야 한다. 자세한 규칙은 [content_recommender_prompt.md](prompts/content_recommender_prompt.md) 의 규칙 #2 참고.

**Supabase 확인 쿼리**

```sql
-- 1) 전제 조건: 두 사용자 모두 취향 벡터가 생성돼 있는지 확인
SELECT user_id, source_count, strategy, vector_dims(embedding) AS dim
FROM user_taste_vectors
WHERE user_id IN ('<사용자A UUID>', '<사용자B UUID>');
-- 기대: 둘 다 source_count >= 3, dim = 1536

-- 2) 사용자별 최신 추천 1건씩 비교 (DISTINCT ON 으로 user_id별 최신 1건 보장)
SELECT DISTINCT ON (user_id)
  user_id,
  video_id,
  video_title,
  emotion,
  intensity,
  selected_score,
  candidate_pool,
  created_at
FROM recommendation_log
WHERE user_id IN ('<사용자A UUID>', '<사용자B UUID>')
ORDER BY user_id, created_at DESC;
-- 기대: 두 행의 video_id가 서로 다름, emotion/intensity는 비슷(같은 메시지였으므로)

-- 3) 후보 풀 상위 5개만 추출해 점수 순위 비교
--    (candidate_pool 스키마는 recommendation_log 작성 코드 기준 [{video_id, score, ...}] 형태 가정)
SELECT
  user_id,
  jsonb_path_query_array(
    candidate_pool,
    '$[0 to 4] ? (@.score != null)'
  ) AS top5
FROM recommendation_log
WHERE user_id IN ('<사용자A UUID>', '<사용자B UUID>')
ORDER BY user_id, created_at DESC;
```

---

## Scenario 4 — 감정 궤적(Trend) 반영

**목적**: 감정이 악화 중(`worsening`)일 때와 안정(`stable`)일 때 추천 결과가 달라지는지 확인

**전제 조건**
- 동일 사용자가 동일 세션에서 여러 번 대화를 나눔
- 감정 강도가 회차에 따라 상승 (0.3 → 0.5 → 0.8 순으로)

**실행 방법**

```bash
# Turn 1 (강도 낮음 - stable 예상)
curl -X POST http://localhost:8000/api/counseling/chat \
  -d '{"user_id": "<UUID>", "session_id": "<세션>", "message": "요즘 조금 무기력한 것 같아요"}'

# Turn 2 (강도 중간)
curl -X POST http://localhost:8000/api/counseling/chat \
  -d '{"user_id": "<UUID>", "session_id": "<세션>", "message": "사실 점점 더 힘들어지고 있어요. 아무것도 하기 싫고..."}'

# Turn 3 (강도 높음 - worsening 예상 → 추천 발동)
curl -X POST http://localhost:8000/api/counseling/chat \
  -d '{"user_id": "<UUID>", "session_id": "<세션>", "message": "너무 지쳐서 눈물이 날 것 같아요. 잠깐 음악 추천해 주실 수 있나요?"}'
```

**기대 결과**
- [-] `emotion_records` 테이블에 3개의 기록이 순서대로 생성됨
- [-] 3번째 대화에서 `recommendation_log`의 기록 확인 시 `emotion`에 높은 강도 감정, `intensity`가 0.7 이상
- [-] (디버그 로그 확인) `reranker.py`의 `compute_emotion_trend`가 `"worsening"` 반환
- [-] `w_emotion`이 `w_taste`보다 높은 값으로 계산되어 감정 적합성 위주 영상 선정

> **Note (intensity 의미)**: `emotion_records`는 마이그레이션 009 이후 `intensity` 컬럼을 제거하고 `valence`/`arousal`/`va_radius` 만 사용합니다. `recommendation_log.intensity` 컬럼은 그대로 유지하지만 적재되는 값은 `va_radius = √(V² + A²)` 입니다(0~1). 즉 두 테이블의 "강도" 비교는 `emotion_records.va_radius` ↔ `recommendation_log.intensity` 로 봐야 합니다.

**Supabase 확인 쿼리**
```sql
-- 감정 기록 순서 확인 (VA 모델 기준)
SELECT emotion, emotion_description, valence, arousal, va_radius, created_at
FROM emotion_records
WHERE user_id = '<UUID>'
ORDER BY created_at ASC;

-- 추천 로그에서 감정 강도 확인 (intensity = va_radius)
SELECT emotion, intensity, video_title, selected_score
FROM recommendation_log
WHERE user_id = '<UUID>'
ORDER BY created_at DESC
LIMIT 1;

-- 두 테이블 강도 정합성 교차 확인
SELECT
  rl.created_at AS rec_at,
  rl.intensity  AS rec_intensity,
  er.va_radius  AS er_va_radius,
  er.created_at AS er_at
FROM recommendation_log rl
JOIN emotion_records er
  ON er.user_id = rl.user_id AND er.session_id = rl.session_id
WHERE rl.user_id = '<UUID>'
ORDER BY rl.created_at DESC, er.created_at DESC
LIMIT 5;
```

---

## Scenario 5 — 임베딩 캐시 동작

**목적**: 동일 영상이 두 번 추천 후보에 포함될 때 캐시에서 조회되는지 확인 (API 호출 최소화)

**실행 방법**

1. Scenario 1을 실행하여 첫 번째 추천 발동 → `content_embeddings` 캐시 생성
2. 동일 사용자 혹은 다른 사용자로 유사한 감정 키워드로 재요청
3. 서버 로그 또는 `content_embeddings` 테이블의 `created_at` 확인

**기대 결과**
- [-] 두 번째 추천 시 `content_embeddings` 테이블의 기존 레코드 `created_at`이 변경되지 않음 (캐시 히트)
- [-] 서버 응답 시간이 첫 번째보다 빠름 (임베딩 API 호출 없음)

**Supabase 확인 쿼리**
```sql
-- 캐시된 영상 수 및 최근 생성 시각 확인
SELECT content_id, created_at FROM content_embeddings ORDER BY created_at DESC LIMIT 10;
```

---

## 체크리스트 요약

| # | 시나리오 | 핵심 확인 항목 |
|---|---|---|
| 1 | 콜드스타트 | 추천 정상 동작 + 로그 저장 |
| 2 | 좋아요 누적 | `user_taste_vectors` 자동 생성 |
| 3 | 사용자별 다른 추천 | 동일 메시지 → 다른 영상 |
| 4 | 감정 궤적 반영 | worsening 시 감정 가중치 증가 |
| 5 | 임베딩 캐시 | 재요청 시 DB 캐시 재사용 |
