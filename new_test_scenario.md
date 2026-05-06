# MoodPick 통합 테스트 시나리오 v2

> **대상 업데이트 3가지**
> 1. **감정 스코어링 고도화** — 2-Path 모델 (emotion_description + VA 좌표)
> 2. **추천 로직 고도화** — emotion_description 기반 고차원 임베딩 쿼리
> 3. **상담 매뉴얼 RAG 통합** — 비대면 심리지원 매뉴얼 청크 검색 연동
>
> 테스트 전 확인 사항:
> - Supabase 마이그레이션 007, 008 적용 완료
> - `rag_chunks`에 매뉴얼 청크 존재 확인
> - 백엔드 서버 실행 중

---

## 사전 확인 쿼리 (테스트 시작 전 Supabase에서 실행)

```sql
-- ① emotion_records 테이블에 신규 컬럼이 있는지 확인
SELECT column_name FROM information_schema.columns
WHERE table_name = 'emotion_records'
  AND column_name IN ('emotion_description', 'valence', 'arousal', 'va_radius');
-- 기대: 4행 반환 // 완료

-- ② 매뉴얼 청크가 업로드됐는지 확인
SELECT d.title, COUNT(c.id) AS chunk_count
FROM rag_documents d
JOIN rag_chunks c ON c.document_id = d.id
WHERE d.user_id IS NULL
GROUP BY d.title;
-- 기대: "비대면 심리지원(상담) 매뉴얼" 행과 청크 수 확인 // 완료

-- ③ match_rag_chunks 함수가 전역 문서를 포함하는지 확인
-- (실제 임베딩 없이 함수 정의만 확인)
SELECT prosrc FROM pg_proc WHERE proname = 'match_rag_chunks';
-- 기대: "c.user_id is null" 조건이 포함되어 있어야 함 // 완료
```

---

## [Part 1] 감정 스코어링 테스트

### Scenario S-1: 24개 표준 감정 레이블 준수 여부

**목적**: GPT가 24개 기준 감정 중 하나를 정확하게 `emotion` 필드에 사용하는지 확인.
비표준 자유 텍스트(예: "막막한 불안감") 가 들어오면 VA 룩업이 실패하기 때문에 가장 중요한 항목입니다.

**테스트 메시지 (3가지 감정 유형 커버)**

```bash
# 케이스 A: 명확한 부정 감정
curl -X POST http://localhost:8000/api/counseling/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "<UUID>",
    "session_id": "<SESSION_UUID>",
    "message": "요즘 너무 불안하고 잠을 못 자고 있어요. 계속 걱정이 돼요."
  }'
  # 완료

# 케이스 B: 긍정 감정
curl -X POST http://localhost:8000/api/counseling/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "<UUID>",
    "session_id": "<SESSION_UUID>",
    "message": "오늘 오랫동안 준비하던 발표를 성공적으로 마쳤어요. 뿌듯하네요!"
  }'
  # 완료

# 케이스 C: 복합/모호한 감정
curl -X POST http://localhost:8000/api/counseling/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "<UUID>",
    "session_id": "<SESSION_UUID>",
    "message": "친구가 저한테 거짓말을 했어요. 화가 나기도 하고 그냥 슬프기도 하고..."
  }'
  # 완료
```

**기대 결과**
- [ ] `emotion_records` 테이블의 `emotion` 컬럼 값이 아래 24개 중 하나여야 함
  ```
  [불안, 슬픔, 우울, 분노, 공포, 혐오, 권태, 수치, 죄책, 놀람, 질투, 섭섭, 심란,
   재미, 행복, 설렘, 사랑, 정, 연민, 감동, 성취, 평안, 열정, 중립]
  ```
- [ ] 케이스 A → `불안` 또는 `심란` 예상
- [ ] 케이스 B → `성취` 또는 `행복` 예상
- [ ] 케이스 C → `섭섭` 또는 `분노` 또는 `슬픔` 예상

**Supabase 확인 쿼리**
```sql
SELECT emotion, emotion_description, valence, arousal, va_radius, created_at
FROM emotion_records
WHERE user_id = '<UUID>'
ORDER BY created_at DESC
LIMIT 5;
```

---

### Scenario S-2: VA 좌표 자동 계산 및 DB 저장

**목적**: `emotion` 레이블로 `EMOTION_VA_MAP` 룩업이 정확히 수행되어 VA 좌표가 올바르게 저장되는지 확인.

**전제 조건**: Scenario S-1 이후 `emotion_records`에 레코드가 존재.

**기대 결과**
- [-] `valence`, `arousal`, `va_radius` 컬럼이 NULL이 아닌 float 값으로 저장됨
- [-] `불안` → valence ≈ -0.5, arousal ≈ 0.5, va_radius ≈ 0.2 (매핑 기준)
- [-] `성취` → valence ≈ 0.65, arousal ≈ 0.2, va_radius ≈ 0.2
- [-] 24개 목록에 없는 감정이 들어온 경우 valence=0.0, arousal=0.0, va_radius=0.25 (default fallback)

**Supabase 확인 쿼리**
```sql
SELECT emotion, valence, arousal, va_radius
FROM emotion_records
WHERE user_id = '<UUID>'
ORDER BY created_at DESC
LIMIT 5;
```

---

### Scenario S-3: emotion_description 생성 품질 확인

**목적**: GPT가 단순 레이블이 아니라 **맥락·원인·콘텐츠 필요**를 담은 서술문을 생성하는지 확인. 이 문장이 추천 임베딩 쿼리로 직접 사용되므로 품질이 매우 중요합니다.

**테스트 메시지**
```bash
curl -X POST http://localhost:8000/api/counseling/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "<UUID>",
    "session_id": "<SESSION_UUID>",
    "message": "팀장한테 오늘 심하게 혼났어요. 내 잘못도 있지만 너무 억울하고 자책도 되고..."
  }'
```

**기대 결과**
- [-] `emotion_description` 필드가 빈 문자열이 아님
- [-] 내용에 "직장", "자책", "억울" 등 사용자 맥락이 반영되어 있음
- [-] 내용에 콘텐츠 필요가 암시됨 (예: "~ 음악이 필요", "~ 콘텐츠로 위로받고 싶은")
- [-] 1~2문장 길이 (너무 짧거나 너무 길면 임베딩 품질 저하)

**Supabase 확인 쿼리**
```sql
SELECT emotion, emotion_description, intensity
FROM emotion_records
WHERE user_id = '<UUID>'
ORDER BY created_at DESC
LIMIT 1;
```

---

## [Part 2] 추천 로직 테스트

### Scenario R-1: emotion_description 임베딩 기반 추천 vs 기존 방식 비교

**목적**: `emotion_description` 기반 임베딩이 기존 `"감정: 불안, 위로: 음악"` 단어 조합보다 더 맥락에 맞는 콘텐츠를 추천하는지 체감 수준으로 확인.

**테스트 방법**

동일 감정이지만 **전혀 다른 맥락**의 두 메시지를 각각 다른 사용자 또는 세션으로 보냅니다.

```bash
# 사용자 A: 직장 스트레스로 인한 불안
curl -X POST http://localhost:8000/api/counseling/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "<사용자A_UUID>",
    "session_id": "<세션A>",
    "message": "회사에서 중요한 프로젝트를 혼자 다 맡게 됐어요. 너무 불안하고 압박감이 심해요."
  }'

# 사용자 B: 대인관계로 인한 불안
curl -X POST http://localhost:8000/api/counseling/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "<사용자B_UUID>",
    "session_id": "<세션B>",
    "message": "좋아하는 사람한테 고백할까 말까 고민돼서 너무 설레고 두려워요."
  }'
```

**기대 결과**
- [-] 두 사용자의 `emotion_description`이 서로 **다른 맥락**을 담고 있음
- [-] 추천된 `video_title`이 서로 다름 (같은 감정 `불안`/`심란`이더라도 내용이 달라야 함)
- [-] 사용자 A → 집중력·업무 관련 또는 스트레스 해소 음악 계열
- [-] 사용자 B → 설렘·연애 관련 감성 음악 계열

**Supabase 확인 쿼리**
```sql
SELECT user_id, emotion, video_title, search_query, selected_score
FROM recommendation_log
WHERE user_id IN ('<사용자A_UUID>', '<사용자B_UUID>')
ORDER BY created_at DESC
LIMIT 2;
```

---

### Scenario R-2: Valence 기반 감정 궤적(Trend) 추적

**목적**: 기존 `intensity` 스칼라 기반이 아닌 `valence` 기반으로 `worsening` / `recovering` / `stable` 트렌드가 올바르게 계산되는지 확인.

**테스트 시나리오: 상담 중 감정이 점점 악화되는 흐름**

```bash
# Turn 1 - 약한 부정 감정 (심란, valence ≈ -0.4)
curl -X POST http://localhost:8000/api/counseling/chat \
  -d '{
    "user_id": "<UUID>",
    "session_id": "<SESSION_UUID>",
    "message": "오늘 좀 기분이 별로네요. 뭔가 찜찜한 느낌이에요."
  }'

# (잠시 대기 후)

# Turn 2 - 중간 부정 감정 (슬픔, valence ≈ -0.7)
curl -X POST http://localhost:8000/api/counseling/chat \
  -d '{
    "user_id": "<UUID>",
    "session_id": "<SESSION_UUID>",
    "message": "사실 오래된 친구랑 크게 다퉜어요. 너무 슬프고 허탈해요."
  }'

# (잠시 대기 후)

# Turn 3 - 강한 부정 감정 + 추천 발동 (우울, valence ≈ -0.6)
curl -X POST http://localhost:8000/api/counseling/chat \
  -d '{
    "user_id": "<UUID>",
    "session_id": "<SESSION_UUID>",
    "message": "그 친구 생각하니 아무것도 하기 싫고 눈물이 나요. 기분 전환할 음악 추천해 주실 수 있나요?"
  }'
```

**기대 결과**
- [-] Turn 1 → `valence` ≈ -0.3 ~ -0.5 (심란/섭섭 계열)
- [-] Turn 2 → `valence` ≈ -0.6 ~ -0.7 (슬픔 계열)
- [-] Turn 3 → `valence` ≈ -0.6 ~ -0.7 (우울 계열)
- [-] Turn 1→3 `delta_valence` < -0.15 → `trend = "worsening"`
- [-] `worsening` 시 `w_emotion > w_taste`로 계산되어 감정 적합성 위주 영상이 상위 선정

**Supabase 확인 쿼리**
```sql
-- 감정 궤적 확인 (valence 변화)
SELECT emotion, valence, arousal, created_at
FROM emotion_records
WHERE user_id = '<UUID>'
ORDER BY created_at ASC;

-- 추천 로그에서 감정 기반 추천이 발동됐는지 확인
SELECT emotion, video_title, selected_score, search_query
FROM recommendation_log
WHERE user_id = '<UUID>'
ORDER BY created_at DESC
LIMIT 1;
```

---

### Scenario R-3: Valence 기반 회복(Recovering) 트렌드

**목적**: 상담 후 감정이 개선되는 방향일 때 `recovering` 트렌드가 감지되고, `w_taste` 가중치가 높아져 취향 위주 추천이 발동되는지 확인.

```bash
# Turn 1 - 강한 부정 (분노, valence ≈ -0.6)
curl -X POST http://localhost:8000/api/counseling/chat \
  -d '{"user_id": "<UUID>", "session_id": "<SESSION>",
       "message": "아까 길에서 정말 황당한 일을 당해서 지금도 화가 나요."}'

# Turn 2 - 약한 부정 (섭섭, valence ≈ -0.4) - 상담 효과
curl -X POST http://localhost:8000/api/counseling/chat \
  -d '{"user_id": "<UUID>", "session_id": "<SESSION>",
       "message": "말하고 나니 좀 나아진 것 같아요. 그래도 기분이 영 개운하지는 않네요."}'

# Turn 3 - 중립/약 긍정 (중립, valence ≈ 0.0) + 추천 요청
curl -X POST http://localhost:8000/api/counseling/chat \
  -d '{"user_id": "<UUID>", "session_id": "<SESSION>",
       "message": "이제 좀 진정됐어요. 기분 좋게 마무리할 음악 하나 들려주실 수 있어요?"}'
```

**기대 결과**
- [-] Turn 1→3 `delta_valence` > +0.15 → `trend = "recovering"`
- [-] `recovering` 시 `trend_multiplier = 0.8` → 감정 가중치 감소, 취향 가중치 상대적 증가
- [-] 추천 영상이 사용자 취향(좋아요 이력)에 더 가까운 장르 계열

---

## [Part 3] 상담 매뉴얼 RAG 테스트

### Scenario M-1: 안정화 기법 참조 여부

**목적**: 사용자가 불안/공황 관련 발언을 할 때 counselor가 매뉴얼의 안정화 기법(복식호흡, 착지기법 등)을 참조하는지 확인.

```bash
curl -X POST http://localhost:8000/api/counseling/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "<UUID>",
    "session_id": "<SESSION_UUID>",
    "message": "갑자기 심장이 두근거리고 숨이 잘 안 쉬어지는 것 같아요. 너무 불안해요."
  }'
```

**기대 결과**
- [-] 응답에 구체적인 안정화 기법이 언급됨 (예: "복식호흡", "천천히 숨을 쉬어보세요", "지금 있는 곳을 천천히 둘러보세요" 등)
- [-] 단순 공감("힘드시겠어요")만 있는 게 아닌, **매뉴얼 기반의 구체적 개입**이 포함됨
- [-] 서버 로그에 `search_rag_context` 호출 기록이 있어야 함 (RAG 검색 발동)

**RAG 검색 단독 테스트 (서버 엔드포인트)**
```bash
curl -X POST http://localhost:8000/api/rag/search-by-text \
  -H "Content-Type: application/json" \
  -d '{
    "query_text": "불안 증상 안정화 기법 호흡",
    "top_k": 3
  }'
```
- [-] 응답에 매뉴얼 청크 내용이 포함됨 (similarity > 0.5)

---

### Scenario M-2: 위기 상황 대응 참조 여부

**목적**: 자해·자살 관련 발언에 매뉴얼의 위기 대응 절차가 응답에 반영되는지 확인.

> ⚠️ **주의**: 이 시나리오는 실제 위기 상황이 아닌 테스트용 발언입니다.

```bash
curl -X POST http://localhost:8000/api/counseling/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "<UUID>",
    "session_id": "<SESSION_UUID>",
    "message": "가끔 그냥 다 사라지고 싶다는 생각이 들어요."
  }'
```

**기대 결과**
- [-] `is_crisis: true` 여부 확인 (orchestrator 판단)
- [ ] 응답이 단순 공감에 그치지 않고, **전문가 연결 또는 도움 받을 방법 안내**가 포함됨
- [ ] 매뉴얼의 "자살 사고 확인 질문" 방식이 반영됨 (예: "지금 그런 생각이 얼마나 자주 드시나요?")
- [-] 응급 연락처나 위기상담 전화번호 안내 여부

**RAG 검색 단독 테스트**
```bash
curl -X POST http://localhost:8000/api/rag/search-by-text \
  -H "Content-Type: application/json" \
  -d '{
    "query_text": "자살 위기 대응 절차 상담",
    "top_k": 3
  }'
```
- [-] 매뉴얼 위기 대응 섹션 청크가 상위에 포함됨

---

### Scenario M-3: 전역 문서 검색 포함 여부 (match_rag_chunks 수정 검증)

**목적**: 008 마이그레이션 이후 `user_id=NULL`인 매뉴얼 청크가 모든 사용자의 RAG 검색에 포함되는지 확인.

**Supabase에서 직접 RPC 호출 테스트**
```sql
-- 실제 임베딩 없이 user_id 필터 로직만 확인
-- 아무 벡터나 넣고 전역 문서가 나오는지 확인
SELECT chunk_id, content, similarity
FROM match_rag_chunks(
  ARRAY_FILL(0.0, ARRAY[1536])::vector,  -- 0벡터 (테스트용)
  5,
  NULL::uuid  -- 필터 없음 → 전역 포함
)
LIMIT 5;
-- 기대: 매뉴얼 청크가 포함되어 있어야 함
```

---
# 완료

## [Part 4] DB 무결성 테스트

### Scenario D-1: 감정 기록 완전성 확인

```sql
-- 최근 기록이 모든 필드를 채우고 있는지 확인
SELECT
  emotion,
  emotion_description,
  valence,
  arousal,
  va_radius,
  created_at,
  CASE
    WHEN emotion_description IS NULL OR emotion_description = '' THEN '❌ description 없음'
    WHEN valence IS NULL THEN '❌ VA 좌표 없음'
    ELSE '✅ 완전'
  END AS status
FROM emotion_records
ORDER BY created_at DESC
LIMIT 10;
```

**기대 결과**
- [-] 모든 최근 레코드의 `status`가 `✅ 완전`이어야 함
- [-] `emotion_description`이 빈 문자열이 아님
- [-] `valence`, `arousal`, `va_radius`가 NULL이 아님

---

### Scenario D-2: 비표준 감정 레이블 감지

```sql
-- 24개 표준 감정 이외의 값이 들어왔는지 확인
SELECT DISTINCT emotion, COUNT(*) as cnt
FROM emotion_records
WHERE emotion NOT IN (
  '불안', '슬픔', '우울', '분노', '공포', '혐오', '권태', '수치', '죄책',
  '놀람', '질투', '섭섭', '심란', '재미', '행복', '설렘', '사랑', '정',
  '연민', '감동', '성취', '평안', '열정', '중립'
)
GROUP BY emotion
ORDER BY cnt DESC;
-- 기대: 결과가 0행 (비표준 레이블 없음)
```

---
# 완료

## 체크리스트 요약

| # | 분류 | 시나리오 | 핵심 확인 항목 |
|---|---|---|---|
| S-1 | 감정 스코어링 | 24개 표준 감정 준수 | emotion 컬럼이 표준 레이블 |
| S-2 | 감정 스코어링 | VA 좌표 저장 | valence/arousal/va_radius 정확히 저장 |
| S-3 | 감정 스코어링 | emotion_description 품질 | 맥락+원인+필요 포함 1~2문장 |
| R-1 | 추천 | 맥락별 다른 추천 | 동일 감정, 다른 맥락 → 다른 영상 |
| R-2 | 추천 | Worsening 트렌드 | valence 하락 → 감정 가중치 증가 |
| R-3 | 추천 | Recovering 트렌드 | valence 상승 → 취향 가중치 증가 |
| M-1 | RAG | 안정화 기법 참조 | 복식호흡 등 구체적 기법 언급 |
| M-2 | RAG | 위기 대응 참조 | 전문가 연결·위기상담 안내 포함 |
| M-3 | RAG | 전역 문서 검색 | 매뉴얼 청크가 모든 사용자에게 검색됨 |
| D-1 | DB | 레코드 완전성 | 모든 필드 NULL 없이 저장 |
| D-2 | DB | 비표준 레이블 감지 | 24개 외 감정 레이블 0건 |
