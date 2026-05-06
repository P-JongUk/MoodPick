# MoodPick 추천 로직 고도화 계획 v2.1 — 하이브리드 임베딩 + 감정 궤적 기반

> v1(`recommendation_plan.md`)과 별도로 진행되는 **임베딩 기반 하이브리드 아키텍처** 계획.
> v1의 Phase 1-B(GPT 재랭킹)와 같은 자리(검색 후 재랭킹)에 들어가지만,
> GPT 호출 대신 **벡터 유사도**로 재랭킹하는 구조.
>
> v1이 "빠르게 효과 검증"이라면, v2는 "장기적으로 정답 아키텍처".
> 두 plan은 배타적이지 않다 — v1의 인터페이스 추상화(옵션 C)에 따라
> v1 → v2로 매끄럽게 전환 가능하도록 설계한다.

---

## A. 설계 Q&A

### Q1. 감정은 저장 전에 추천에 넘기나요, 저장 후에 넘기나요?

**저장 후**입니다.

```
Counselor Agent
  └─ save_emotion_record → DB 저장 ✔
        ↓
Content Recommender Agent
  └─ emotion_records에서 최근 3개 fetch → trend 계산 후 쿼리 생성 GPT에 전달
```

Recommender는 DB에서 최근 N개 기록을 조회하므로 "현재 감정 포함 이력" 전체를 얻습니다.
저장 전에 넘기면 "이번 한 건"만 존재하여 trend 계산이 불가능합니다.

### Q2. 멘토 피드백: "사용자 정보와 대화를 전부 임베딩하면 추천 성능이 좋아진다"

**방향은 맞지만, '전부 다'는 과합니다.** 자세한 분석은 [섹션 13](#13-멘토-피드백-검토)을 참고하세요.

---

## 0. 왜 임베딩 기반인가

### v1(텍스트 기반)의 한계
1. **프롬프트 비대화**: 사용자가 좋아요 100개 누르면 텍스트로 다 넣을 수 없음. 윈도우 상한(최근 N개)으로 임시 해결하지만 누적된 장기 선호는 반영 안 됨.
2. **GPT 호출 비용**: 매 추천마다 1~2회 GPT. 사용자 증가 시 비용 선형 증가.
3. **키워드 의존 매칭**: "차분한 피아노"와 "잔잔한 어쿠스틱"이 의미적으로 비슷해도 GPT가 매번 새로 매칭. 학습 X.
4. **응답 지연**: GPT 호출이 곧 지연. 5초 이상.

### 임베딩 기반의 장점
- **상수 토큰**: 사용자 누적 좋아요 100개여도 user_vector 하나(1536차원). 프롬프트 사이즈 무관.
- **의미적 매칭**: "차분한 피아노" 임베딩과 "잔잔한 어쿠스틱" 임베딩은 가까움. 자연스럽게 매칭.
- **저비용 추론**: 임베딩 호출은 GPT 대비 약 1/100 가격. 재랭킹 단계에서 GPT 호출 제거.
- **빠름**: 코사인 유사도는 밀리초.
- **누적되는 자산**: 한번 임베딩한 영상은 계속 재사용. 시간이 갈수록 캐시 적중률↑.

### 단점·트레이드오프 (정직하게)
- **콜드스타트 더 심함**: 좋아요 0개면 user_vector 못 만듦.
- **"왜 추천?" 설명 어려움**: 점수만 있고 이유가 없음. 후처리로 보완 필요.
- **단일 벡터의 lossy 문제**: 다양한 취향(재즈+EDM)을 평균하면 흐릿한 벡터가 됨.
- **임베딩 모델 의존**: 모델 바뀌면 벡터 호환성 깨짐. 버전 관리 필요.
- **현재 감정 반영이 어려움**: user_vector는 누적 선호. "지금 슬프니까 위로 음악"은 별도 신호로 합쳐야 함.

이 단점들을 다 해결한 게 **하이브리드 설계**.

---

## 1. 하이브리드 아키텍처 개요

```
[사용자 메시지 + 이전 대화]
        ↓
   Counselor Agent (감정 분석, 응답 생성)
        │  └─ save_emotion_record → DB 저장 ✔  (추천보다 먼저)
        ↓ needs_recommendation == true
   Content Recommender Agent
        ├─ ① 감정 궤적(Trend) 조회             ← 신규 (GPT 호출 없음)
        │     emotion_records에서 최근 3개 fetch
        │     trend = "worsening" | "stable" | "recovering"
        │
        ├─ ② 검색 쿼리 생성 (GPT) [GPT 호출 1회]
        │     현재 감정 + 강도 + trend + comfort_style 반영
        │     예: "comforting lofi music for worsening anxiety"
        │
        ├─ ③ YouTube 검색 (MCP)
        │     watched_ids 제외, 10~15개 후보 풀
        │
        ├─ ④ 후보 임베딩 (OpenAI embeddings)
        │     각 후보(title + description) 임베딩
        │     content_embeddings 캐시 우선 조회 → miss 시 호출
        │
        ├─ ⑤ 사용자 취향 벡터 조회
        │     user_taste_vectors 테이블에서 user_id로 조회
        │     없으면 콜드스타트 모드로 폴백
        │
        ├─ ⑥ 하이브리드 점수 계산 (동적 가중치)  ← 업데이트
        │     intensity + trend로 w_taste / w_emotion 자동 조정
        │     score = w_taste · sim(user_vec, cand_vec)
        │           + w_emotion · sim(emotion_vec, cand_vec)
        │           - diversity_penalty - dislike_penalty
        │
        ├─ ⑦ 1개 선정 + 추천 이유 후처리
        │     Phase 1: 템플릿 기반 (GPT 호출 없음)
        │     Phase 2: LLM 1문장 생성 (GPT 호출 1회, 선택)
        │
        └─ ⑧ 비동기 작업
              - 후보 임베딩을 content_embeddings에 저장
              - 추천 결과를 recommendation_log에 저장

[사용자 피드백 (like/dislike)]
        ↓
   user_taste_vector 갱신 (debounced async)
```

### 각 단계의 역할 분담

| 단계 | 누가 | GPT 호출 | 이유 |
|---|---|---|---|
| ① 감정 궤적 조회 | DB fetch | 없음 | 이미 저장된 기록 단순 조회 |
| ② 검색 쿼리 생성 | GPT | **1회** | 자연어 맥락·trend 반영은 LLM이 최적 |
| ③ YouTube 검색 | MCP | 없음 | 외부 API |
| ④ 후보 임베딩 | OpenAI embedding API | 없음 | GPT 아님, 임베딩 전용 API |
| ⑤ 취향 벡터 조회 | DB fetch | 없음 | 사전 계산된 사용자 표현 |
| ⑥ 하이브리드 점수 계산 | 코사인 유사도 | 없음 | 밀리초, 결정적 |
| ⑦ 선정 + 이유 생성 | 템플릿 (Phase 1) | 없음 | Phase 2부터 GPT 1회 선택 |
| ⑧ 비동기 저장 | DB insert | 없음 | 백그라운드 |

**추천 1건 GPT 호출 합계: 1회** (쿼리 생성만). v1 대비 재랭킹 GPT 제거.

---

## 2. 데이터 모델

### 2-1. `content_embeddings` (신규)
영상별 임베딩 캐시. 한번 임베딩한 영상은 재사용.

```sql
create table public.content_embeddings (
  content_id     text primary key,        -- YouTube video_id
  source_text    text not null,           -- 임베딩 입력 (title + description 일부)
  embedding      vector(1536) not null,   -- OpenAI text-embedding-3-small
  embedding_model text not null default 'text-embedding-3-small',
  metadata       jsonb,                   -- channel_id, duration, view_count 등
  created_at     timestamptz not null default now()
);

create index idx_content_emb_model on public.content_embeddings (embedding_model);
-- pgvector hnsw 인덱스
create index idx_content_emb_vec on public.content_embeddings
  using hnsw (embedding vector_cosine_ops);
```

### 2-2. `user_taste_vectors` (신규)
사용자별 취향 벡터. 좋아요 영상들로부터 derived.

```sql
create table public.user_taste_vectors (
  user_id        uuid primary key references auth.users(id),
  embedding      vector(1536) not null,
  embedding_model text not null default 'text-embedding-3-small',
  source_count   int not null,            -- 몇 개 좋아요로 만들었는지
  strategy       text not null,           -- "time_weighted_avg" | "centroid" | ...
  updated_at     timestamptz not null default now()
);
```

> **단일 벡터로 시작**. Phase 3에서 다중 벡터(centroids)로 진화 가능.

### 2-3. `recommendation_log` (v1 1-D 통합)
v1에서 Phase 3로 미뤘던 것을 v2 Phase 1에서 같이 만든다.
이유: 임베딩 기반은 피드백 루프와 본질적으로 결합됨.

```sql
create table public.recommendation_log (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid not null references auth.users(id),
  session_id     uuid not null references public.counseling_sessions(id),
  search_query   text not null,
  video_id       text,
  video_title    text,
  reason         text,
  emotion        text,
  intensity      real,
  candidate_pool jsonb,                   -- 5~10개 후보의 video_id + score
  selected_score real,                    -- 선정된 영상의 하이브리드 점수
  strategy_version text,                  -- "v2.1" 등
  created_at     timestamptz not null default now(),
  watched_at     timestamptz,
  feedback       text                     -- "like" | "dislike" | null
);

create index idx_reclog_user_session on public.recommendation_log (user_id, session_id);
create index idx_reclog_user_created on public.recommendation_log (user_id, created_at desc);
```

---

## 3. 사용자 취향 벡터 계산 전략

### 3-1. 단일 벡터 (Phase 1)

가장 단순. **시간 가중 평균**.

```python
def compute_user_taste_vector(user_id: str) -> tuple[list[float], int] | None:
    """
    좋아요 영상들의 임베딩을 시간 가중 평균.
    오래된 좋아요는 가중치 감소 (반감기 90일).

    Returns: (vector, source_count) or None if not enough data.
    """
    liked = supabase.table("content_feedback") \
        .select("content_id, created_at") \
        .eq("user_id", user_id).eq("feedback", "like") \
        .execute().data

    if len(liked) < MIN_LIKES_FOR_VECTOR:  # 예: 3개
        return None

    embeddings = []
    weights = []
    now = datetime.utcnow()
    HALF_LIFE_DAYS = 90

    for row in liked:
        emb = get_or_compute_content_embedding(row["content_id"])
        if emb is None:
            continue
        age_days = (now - parse(row["created_at"])).days
        weight = 0.5 ** (age_days / HALF_LIFE_DAYS)
        embeddings.append(emb)
        weights.append(weight)

    if not embeddings:
        return None

    # 가중 평균 + L2 정규화
    weighted = np.average(embeddings, axis=0, weights=weights)
    normalized = weighted / np.linalg.norm(weighted)
    return normalized.tolist(), len(embeddings)
```

### 3-2. 다중 벡터 / centroids (Phase 3 — 옵션)

다양한 취향(재즈+EDM)을 평균하면 흐릿해짐. 해결: 좋아요 영상들을 k-means로 2~3개 클러스터로 나누고 각 centroid 저장.

추천 시 후보의 점수 = **max(similarity to each centroid)**.

```python
# Phase 3에서 도입. Phase 1은 단일 벡터만.
def compute_user_taste_centroids(user_id: str, k: int = 3) -> list[list[float]]:
    ...
```

### 3-3. 갱신 전략

- **Eager (즉시)**: 사용자가 좋아요 누를 때마다 user_taste_vector 다시 계산. 단순하지만 빈번한 like 시 비용↑.
- **Debounced**: 좋아요 누른 뒤 5분 idle 후 1회 계산. 권장.
- **Nightly batch**: 매일 자정 모든 사용자 재계산. 가장 저렴하지만 실시간 반응 X.

**권장**: Phase 1에서 debounced (5분 윈도우), Phase 3에서 nightly batch와 병행.

---

## 4. 콜드스타트 전략

좋아요 < 3 → user_taste_vector 만들 수 없음. 다음 단계 폴백:

### 4-1. 즉시 폴백 (좋아요 0개)
- v1의 GPT 재랭킹으로 폴백 (옵션 C 인터페이스 활용)
- 또는 콜드스타트 시드 풀 (`ai/seeds/coldstart_pool.json`, v1 Phase 2-C와 공유)

### 4-2. 약한 신호 (좋아요 1~2개)
- 좋아요 영상의 raw 임베딩 1~2개 직접 사용 (평균 X)
- "유사 영상" 같은 의미. 신뢰도 낮음을 나타내기 위해 점수 weight 감소.

### 4-3. 온보딩 정보 활용 (좋아요 0개일 때 보조)
- `user_profiles.onboarding_profile`의 concerns + comfort_style 텍스트를 임베딩 → 임시 user_vector
  ```
  source_text = "고민: 불안, 직장 스트레스. 위로 방식 선호: 음악, 잔잔한 영상"
  ```
- 정확하진 않지만 0개보다 낫고, 좋아요 누적되면 자연스럽게 교체됨.

### 졸업 조건
- 좋아요 ≥ 3 → 자동으로 정식 user_taste_vector로 전환.
- 매 추천 후 좋아요 카운트 체크 → MIN_LIKES_FOR_VECTOR 도달 시 첫 user_taste_vector 생성 트리거.

---

## 5. 점수 계산 (하이브리드 스코어 — 동적 가중치)

### 5-1. 감정 궤적 계산

```python
def compute_emotion_trend(emotion_records: list[dict]) -> dict:
    """
    최근 3개 감정 기록으로 trend 방향 계산.
    DB에서 fetch한 emotion_records (시간 오름차순)를 받는다.

    Returns: {"trend": "worsening"|"stable"|"recovering", "direction": float}
    """
    if len(emotion_records) < 2:
        return {"trend": "stable", "direction": 0.0}

    records = sorted(emotion_records, key=lambda r: r["created_at"])[-3:]
    intensities = [r["intensity"] for r in records]
    delta = intensities[-1] - intensities[0]  # 양수=악화, 음수=회복

    if delta > 0.15:
        return {"trend": "worsening", "direction": delta}
    elif delta < -0.15:
        return {"trend": "recovering", "direction": delta}
    else:
        return {"trend": "stable", "direction": delta}
```

### 5-2. 하이브리드 스코어 (동적 가중치)

핵심 아이디어:
- **감정 강도(intensity)가 높을수록** → 취향보다 "지금 감정에 맞는" 영상이 중요
- **감정이 악화 중(worsening)일수록** → 위로형 콘텐츠 매칭 가중치를 추가 증폭
- 두 가중치의 합을 정규화하여 총합이 일정하게 유지

```python
def hybrid_score(candidate_emb, ctx) -> float:
    """
    candidate_emb: 후보 영상의 임베딩 벡터
    ctx: {
        user_vec:           사용자 취향 벡터 (None 가능),
        onboarding_vec:     콜드스타트 임시 벡터 (None 가능),
        emotion_vec:        현재 감정 임베딩,
        intensity:          현재 감정 강도 (0.0~1.0),
        trend:              "worsening" | "stable" | "recovering",
        recent_dislikes:    최근 싫어요 영상 임베딩 리스트,
        recent_recommended: 최근 추천 영상 임베딩 리스트 (다양성용),
    }
    """
    score = 0.0
    intensity = ctx.get("intensity", 0.5)
    trend = ctx.get("trend", "stable")

    # ─── 동적 가중치 계산 ──────────────────────────────────────────────
    # intensity 0.0 → w_taste=0.75, w_emotion=0.25
    # intensity 1.0 → w_taste=0.40, w_emotion=0.60 (감정 적합성 우선)
    trend_multiplier = {"worsening": 1.3, "stable": 1.0, "recovering": 0.8}.get(trend, 1.0)
    w_taste   = 0.75 - 0.35 * intensity
    w_emotion = (0.25 + 0.35 * intensity) * trend_multiplier

    # 합산이 1.0을 벗어나지 않도록 정규화
    total = w_taste + w_emotion
    w_taste   /= total
    w_emotion /= total

    # ① 사용자 취향 매칭 (동적 가중치)
    if ctx.get("user_vec") is not None:
        score += w_taste * cosine(candidate_emb, ctx["user_vec"])
    else:
        # 콜드스타트: 온보딩 임시 벡터 (신뢰도 낮으므로 절반 가중치)
        onb = ctx.get("onboarding_vec")
        score += (w_taste * 0.5) * cosine(candidate_emb, onb) if onb else 0

    # ② 현재 감정 반영 (동적 가중치)
    if ctx.get("emotion_vec") is not None:
        score += w_emotion * cosine(candidate_emb, ctx["emotion_vec"])

    # ③ 다양성 페널티 (최근 추천 영상과 너무 비슷하면 감점)
    if ctx.get("recent_recommended"):
        max_sim = max(cosine(candidate_emb, r) for r in ctx["recent_recommended"])
        score -= 0.15 * max_sim

    # ④ 싫어요 페널티 (강화: 0.25 → 0.30)
    if ctx.get("recent_dislikes"):
        max_dislike_sim = max(cosine(candidate_emb, d) for d in ctx["recent_dislikes"])
        score -= 0.30 * max_dislike_sim

    return score
```

**가중치 예시 (intensity별)**

| intensity | trend | w_taste | w_emotion | 해석 |
|---|---|---|---|---|
| 0.3 | stable | 0.68 | 0.32 | 취향 우선, 편안한 상태 |
| 0.7 | stable | 0.52 | 0.48 | 균형 |
| 0.9 | worsening | 0.36 | 0.64 | 감정 적합성 최우선, 위기에 가까움 |
| 0.9 | recovering | 0.44 | 0.56 | 감정 여전히 중요하나 완화 중 |

---

## 6. 단계별 구현 계획

### Phase 1 — 골격 구축 (1주)

> 목표: 임베딩 기반 재랭킹이 동작하는 최소 시스템.
> 콜드스타트는 v1 GPT 재랭킹으로 폴백 (옵션 C 인터페이스).

#### 1-1. 마이그레이션 (~30분)
- `db/migrations/00X_content_embeddings.sql`
- `db/migrations/00Y_user_taste_vectors.sql`
- `db/migrations/00Z_recommendation_log.sql`
- 인덱스 포함

#### 1-2. 임베딩 도구 (~3시간)
**신규** `ai/tools/embedding_service.py`:
```python
async def embed_text(text: str) -> list[float]:
    """OpenAI embedding API. text-embedding-3-small."""

async def get_or_compute_content_embedding(
    content_id: str,
    source_text: str | None = None,
    metadata: dict | None = None,
) -> list[float]:
    """캐시 우선 조회 → miss 시 임베딩 + insert."""

async def batch_embed_contents(items: list[dict]) -> dict[str, list[float]]:
    """여러 후보를 병렬 임베딩 (캐시 활용)."""
```

#### 1-3. 사용자 취향 벡터 도구 (~3시간)
**신규** `ai/tools/user_taste.py`:
```python
async def get_user_taste_vector(user_id: str) -> dict | None:
    """user_taste_vectors 테이블에서 조회."""

async def compute_user_taste_vector(user_id: str) -> dict | None:
    """좋아요 영상들로 시간 가중 평균 계산. None이면 콜드스타트."""

async def refresh_user_taste_vector(user_id: str) -> None:
    """compute → upsert. 좋아요 이벤트에서 호출."""

async def get_onboarding_vector(user_id: str) -> list[float] | None:
    """콜드스타트 폴백: 온보딩 정보 임베딩."""
```

#### 1-4. 하이브리드 재랭킹 함수 (~4시간)
**신규** `ai/agents/reranker.py`:
```python
async def hybrid_rerank(
    candidates: list[dict],          # YouTube 검색 결과 N개
    user_id: str,
    session_id: str,
    emotion: str,
    intensity: float,
) -> list[dict]:
    """
    1. 후보들 일괄 임베딩 (캐시 활용)
    2. user_taste_vector 조회 (없으면 콜드스타트 처리)
    3. 컨텍스트 구성 (emotion_vec, recent_dislikes 등)
    4. 각 후보의 hybrid_score 계산
    5. 점수 내림차순 정렬
    Returns: [{...candidate, score, reason_hint}]
    """
```

#### 1-5. content_recommender 통합 (~2시간)
**수정** `ai/agents/content_recommender.py`:
```python
async def content_recommender_agent(state):
    # ① 쿼리 생성 (기존 그대로)
    search_query = ...

    # ② MCP YouTube 검색 (max_results 5 → 10으로 확대)
    videos = await mcp_search(search_query, watched_ids, max_results=10)

    # ③ 하이브리드 재랭킹 (NEW)
    if user_taste_exists or onboarding_available:
        ranked = await hybrid_rerank(videos, ...)
    else:
        # 완전 콜드스타트 → v1 GPT 재랭킹 폴백 또는 첫 영상
        ranked = await gpt_rerank(videos, ...) if FALLBACK_GPT else videos

    video = ranked[0] if ranked else None

    # ④ 추천 이유 생성 (NEW: 임베딩 기반 후처리)
    reason = await build_recommendation_reason(video, user_id)

    state.recommended_content = {...}
```

#### 1-6. 피드백 트리거 (~2시간)
**수정** `backend/app/routers/content.py` `submit_feedback`:
```python
# 좋아요/싫어요 저장 후
if feedback == "like":
    # debounced refresh (background task)
    background_tasks.add_task(refresh_user_taste_vector, user_id)
```

#### 1-7. 추천 로그 저장 (~1시간)
**수정** `ai/pipeline.py`:
- 추천 후 recommendation_log insert (candidate_pool, selected_score 포함)

#### 1-8. 검증 (~3시간)
- 좋아요 0개 사용자 → 콜드스타트 폴백 동작 확인
- 좋아요 5개 만든 후 → user_taste_vector 자동 생성 확인
- 같은 사용자 다른 감정 → 점수 분포가 달라지는지
- 같은 후보 풀에서 사용자 다르면 다른 영상 선정되는지

**Phase 1 합격 기준**:
- [ ] 후보 임베딩 캐시 hit rate ≥ 50% (테스트 시 같은 영상 반복 호출 시)
- [ ] user_taste_vector가 좋아요 누적에 따라 자동 갱신
- [ ] 콜드스타트(좋아요 0개) 사용자도 정상 추천 반환
- [ ] 같은 후보 풀에서 사용자별 다른 1위 영상 선정되는 케이스 실재
- [ ] 응답 지연 v1 대비 +1초 이내 (캐시 적중 시)

#### Phase 1 예상 총 소요: **5~7일**

---

### Phase 2 — 품질 향상 (1주)

#### 2-1. 후보 풀 확대 + 다중 쿼리
- MCP에 `search_youtube_multi(queries, max_each)` 추가
- 메인 쿼리 + 백업 쿼리(comfort_style 기반) 병렬 → 합쳐서 15~20개
- 임베딩 비용 늘지만 캐시로 상쇄

#### 2-2. 채널 다양성 보정
- 후보 중 같은 channel_id 2개 이상이면 1위만 살리고 나머지 점수 감점

#### 2-3. 추천 이유 개선 (LLM 후처리)
- 선정된 영상 + "가장 가까운 좋아요 영상" 1개를 GPT에 던져 1문장 생성
  ```
  "당신이 좋아하셨던 '○○ 피아노'와 비슷한 잔잔한 분위기로,
   지금 느끼시는 불안에 도움이 될 것 같아요."
  ```
- 임베딩이 점수만 주는 단점을 메움

#### 2-4. 가중치 튜닝
- 추천 후 7일 like-through-rate 측정
- 가중치 조합 A/B 비교 (예: user_vec 0.5 vs 0.7)

#### Phase 2 예상 소요: **3~5일**

---

### Phase 3 — 진화 (선택, 2~3주)

#### 3-1. 다중 벡터 (centroids)
- 좋아요 ≥ 10개 사용자에 한해 k-means(k=2~3)
- 점수 = max(sim to each centroid)
- 다양한 취향 사용자에게 효과

#### 3-2. Nightly 일괄 재계산
- 매일 자정 모든 user_taste_vector 재계산
- 시간 가중치 자연 감쇠

#### 3-3. 추천 전략 A/B
- recommendation_log.strategy_version 활용
- 사용자 그룹(user_id 해시)별 다른 가중치

#### 3-4. Feedback 강화 학습 요소
- 추천된 영상 → 사용자 like → user_vec 업데이트
- 추천된 영상 → 사용자 dislike → 그 영상 임베딩을 negative anchor로 저장
- 다음 추천 시 negative anchor와의 거리도 점수에 반영

---

### Phase 4 — Spotify·다중 모달

v1 Phase 4-B와 동일. MCP 서버 추가, content_embeddings는 그대로 활용 가능 (제목+설명만 같은 임베딩 모델로 처리).

---

## 7. 비용 분석

### 임베딩 호출 비용
OpenAI `text-embedding-3-small`: $0.02 / 1M tokens
- 1 영상 임베딩 ≈ 100 tokens ≈ $0.000002
- 1 추천(10 후보): 10 × $0.000002 = $0.00002
- 캐시 적중률 50% 가정: 실제 $0.00001
- 1만 추천 → $0.10

### v1 vs v2 1추천당 비용 비교
| 항목 | v1 (Phase 1-B 적용) | v2 (Phase 1) |
|---|---|---|
| Orchestrator GPT | 1회 ~$0.0001 | 1회 ~$0.0001 |
| Counselor GPT | 1회 ~$0.0005 | 1회 ~$0.0005 |
| 검색 쿼리 GPT | 1회 ~$0.0002 | 1회 ~$0.0002 |
| 재랭킹 | GPT 1회 ~$0.0003 | **임베딩 10개 ~$0.00001** |
| YouTube API | 1 unit | 1 unit |
| **추천 1건 합계** | **~$0.0011** | **~$0.0008** |

**1추천당 약 27% 저렴**. 사용자 1만 명, 일평균 2추천 = 월 ~$240 절감 (단순 GPT 재랭킹 대비).

### 사용자 취향 벡터 계산 비용
- 좋아요 1개 추가될 때 1회 재계산
- 평균 좋아요 10개 → 10 × 임베딩(이미 캐시) + numpy 평균 ≈ 무료
- 신규 영상 임베딩만 새로 호출. 평균 매우 저렴.

---

## 8. v1과의 관계 / 마이그레이션

### 두 plan 중 하나를 선택하는 게 아니다
- **v1**은 즉시 효과(3시간 작업) — 단기 개선
- **v2**는 장기 정답 아키텍처 (1주~) — 단계적 도입

### 권장 진행 시나리오 (선택)

#### 시나리오 A: v1 1-B → v2 Phase 1 순차
1. v1 1-B(GPT 재랭킹) 3시간 만에 구현, 효과 측정
2. 효과 확인되면 사용자 좋아요 데이터 30개 이상 누적까지 v1으로 운영
3. 데이터 쌓이면 v2 Phase 1 시작, `_rerank` 함수 본체만 임베딩 버전으로 교체
4. v1 코드는 콜드스타트 폴백으로 살아남음

**장점**: 즉시 효과 + 점진 진화. **단점**: v2 시작 시점 판단 필요.

#### 시나리오 B: v2로 직행
1. v1 건너뛰고 v2 Phase 1 (1주) 바로 구현
2. 콜드스타트 폴백은 시드 풀로 처리

**장점**: 코드 낭비 없음. **단점**: 효과 보기까지 1주, 그동안 사용자 추천 품질 정체.

### 인터페이스 추상화 (시나리오 A 권장 시)
v1 1-B 구현 시 다음 인터페이스로 작성하면 v2로 교체가 매끄러움:

```python
# ai/agents/content_recommender.py
async def _rerank(candidates, ctx) -> list[dict]:
    # v1 단계: GPT 호출
    return await gpt_rerank(candidates, ctx)
    # v2 단계로 교체 시:
    # return await hybrid_rerank(candidates, ctx)
```

---

## 9. 리스크 및 완화

| 리스크 | 가능성 | 영향 | 완화 |
|---|---|---|---|
| 임베딩 모델 변경 시 호환성 깨짐 | 낮음 | 큼 | `embedding_model` 컬럼 + 버전 관리. 마이그레이션 시 일괄 재임베딩. |
| pgvector 인덱스 성능 (수십만 행) | 중간 | 중간 | hnsw 인덱스 사용. 사용자 수 10만 넘으면 외부 벡터 DB(예: Pinecone) 고려. |
| 단일 벡터의 lossy | 중간 | 중간 | Phase 3에서 다중 벡터로 진화 |
| 콜드스타트 사용자 경험 | 높음 | 중간 | 온보딩 임시 벡터 + 시드 풀 + GPT 폴백 3중 안전망 |
| OpenAI 임베딩 API quota | 낮음 | 큼 | 캐시 + retry. 임베딩은 GPT보다 quota 여유 큼. |
| 가중치 튜닝의 정성성 | 높음 | 중간 | recommendation_log 기반 like-through-rate 측정. A/B로 정량화. |

---

## 10. Phase별 신규/수정 파일 요약

### Phase 1 신규
```
db/migrations/00X_content_embeddings.sql
db/migrations/00Y_user_taste_vectors.sql
db/migrations/00Z_recommendation_log.sql
ai/tools/embedding_service.py
ai/tools/user_taste.py
ai/agents/reranker.py
```

### Phase 1 수정
```
ai/agents/content_recommender.py        ← hybrid_rerank 호출
ai/pipeline.py                           ← recommendation_log insert
backend/app/routers/content.py           ← like 시 user_taste 갱신 트리거
mcp_servers/server.py                    ← max_results 기본 10으로
```

### Phase 2~4
별도.

---

## 11. 의존성

추가 필요:
```
# backend/requirements.txt
numpy>=1.26
```

OpenAI 임베딩은 기존 openai 패키지로 가능. pgvector는 Supabase에 이미 있음(RAG에서 사용 중).

---

## 12. 진행 결정 체크포인트

이 plan을 시작하기 전 다음을 확인:

- [ ] v1 1-B를 먼저 할지, v2로 직행할지 결정 (시나리오 A vs B)
- [ ] 콜드스타트 시드 풀의 자료 수집 누가 할지 (팀원과 RAG 자료와 같이?)
- [ ] 가중치 튜닝 기간 동안 like-through-rate 모니터링 어떻게 할지
- [ ] Phase 3 다중 벡터 도입 시점 기준 (좋아요 평균 N개 이상?)

---

## 13. GPT 호출 예산 분석

### 추천 1건 기준 GPT 호출 수

| 단계 | v1 (현재) | v2.1 (이 plan) |
|---|---|---|
| Orchestrator | 1회 | 1회 |
| Counselor (tool loop) | 2~3회 | 2~3회 |
| 쿼리 생성 | 1회 | 1회 |
| 재랭킹 | 1회 (GPT) | **0회** (임베딩) |
| 추천 이유 | 0회 (쿼리에 포함) | 0회 (Phase 1 템플릿) |
| **합계** | **5~6회** | **4~5회** |

> Phase 2에서 추천 이유 LLM 생성 옵션 켜면 +1회, 총 5~6회. 그래도 재랭킹 GPT 제거 효과로 품질 향상.

### 비용 비교 (재랭킹 단계)

| 항목 | v1 재랭킹 | v2.1 재랭킹 |
|---|---|---|
| 방식 | GPT 1회 ~$0.0003 | 임베딩 10개 ~$0.00002 |
| 속도 | +2~3초 | +50ms |
| 학습 여부 | 매번 새로 판단 | 누적 취향 벡터 재활용 |

---

## 14. 멘토 피드백 검토

> "사용자 정보와 대화 등 관련 내용을 전부 다 임베딩해서 넣으면 자연스럽게 추천 성능이 좋아질 것이다"

### 방향은 맞다

임베딩이 의미 공간에서 유사도를 측정하므로, 사용자에 관한 정보를 임베딩하면 더 개인화된 추천이 가능하다는 직관은 정확합니다.

### 그러나 "전부 다"는 세 가지 문제가 있다

1. **노이즈**: 대화 원문에는 인사말, 잡담, 맥락 없는 단어가 섞여 있습니다. 이를 통째로 임베딩하면 신호보다 노이즈가 커질 수 있습니다.
2. **매칭 대상 불명확**: 임베딩은 "무엇과 유사한지" 비교해야 합니다. 대화 원문 벡터를 영상 벡터와 직접 비교하는 것은 의미 공간의 도메인이 달라 매칭 정밀도가 낮습니다.
3. **갱신 비용**: 매 대화 후 새 벡터를 생성하면 임베딩 API 호출이 급증합니다.

### 더 효과적인 해석 방법

| 신호 | 임베딩 대상 | 매칭 대상 | 효과 |
|---|---|---|---|
| 좋아요한 영상 | title + description | 후보 영상 벡터 | ✅ 높음 (도메인 일치) |
| 현재 감정 기록 | "emotion: 불안, intensity: 0.8" | 후보 영상 벡터 | ✅ 높음 |
| 온보딩 프로필 | concerns + comfort_style | 후보 영상 벡터 | 🟡 중간 (콜드스타트용) |
| 대화 원문 전체 | raw text | 후보 영상 벡터 | ❌ 낮음 (도메인 불일치, 노이즈) |
| GPT 추출 선호 키워드 | "조용한 음악, 피아노 선호" | 후보 영상 벡터 | ✅ 높음 (Phase 3 옵션) |

### 결론

멘토 피드백의 핵심은 "구조화된 사용자 신호를 임베딩으로 표현하라"로 해석하는 것이 맞습니다.
이 plan의 `user_taste_vector`(좋아요 임베딩 평균) + `emotion_vec`(감정 임베딩) 조합이 그 구체적 구현입니다.
대화 원문 임베딩은 Phase 3에서 GPT로 핵심 선호 키워드를 먼저 추출한 뒤 임베딩하는 방식으로 도입하는 것을 권장합니다.
