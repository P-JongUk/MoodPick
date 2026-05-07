# MoodPick Emotion Scoring Plan

## 개요

이 문서는 MoodPick의 감정 스코어링 시스템을 고도화하기 위한 구현 계획서입니다.
참조 논문 4편과 현재 코드베이스 분석을 바탕으로 설계되었습니다.

**참조 논문 목록 (artifacts/papers_text/):**
- P1: `러셀_모델_기반_좌표계를_활용한_감정_척도에_대한_연구.txt` (박선호 외, 2022)
- P2: `러셀_모델의_확장을_통한_감정차원_모델링_방법_연구.txt` (한의환·차형태, 2017)
- P3: `각성_축의_특성을_고려한_감정차원에_관한_연구.txt` (한의환·차형태, 2014)
- P4: `한국어_감정_디지털_온톨로지_구축에_관한_연구.txt` (이유미 외, 2020)

---

## 현재 시스템 분석

### 현재 감정 스코어링 구조

```
counselor.py (GPT)
  └── save_emotion_record(
        emotion="불안",     # GPT 자유 생성 텍스트 (비표준)
        intensity=0.7       # 0.0~1.0 강도 스칼라
      )

reranker.py
  └── emotion_text = f"감정: {emotion}, 위로: {comfort_style}"
      emotion_vec = embed_text(emotion_text)  # → 1,536차원 임베딩
      # 이 벡터로 콘텐츠 임베딩과 cosine similarity 계산

compute_emotion_trend()
  └── delta = intensities[-1] - intensities[0]
      # intensity 스칼라 변화만으로 트렌드 판단 (심리학적 근거 부족)
```

### 현재 시스템의 문제점

1. **비표준 감정 레이블**: `emotion` 필드가 GPT 자유 생성 → "막막한 불안감", "우울과 분노의 혼합" 등 비일관적 데이터 축적
2. **임베딩 정보 빈약**: `"감정: 불안, 위로: 음악"` 이라는 짧은 텍스트만 임베딩 → 실제 감정 맥락이 대부분 손실됨
3. **트렌드 계산 단순**: `intensity` 스칼라 하나로만 "나아짐/악화" 판단 → 심리학적으로 검증되지 않은 방식

---

## 제안 아키텍처: 2-Path 모델

사용자 메시지 처리 시 두 개의 독립 경로로 감정 정보를 분기합니다.

```
사용자 메시지
      │
      ▼
counselor.py (GPT) - save_emotion_record 호출 시 3가지 생성
      │
      ├─── [Path A] emotion_description (문장)
      │         └─► embed_text() → 1,536차원 → 추천 매칭
      │
      └─── [Path B] emotion (레이블) + intensity
                └─► EMOTION_VA_MAP 룩업 → valence/arousal → DB 저장
                                                               └─► 감정 궤적 추적
```

---

## Path A: 감정 서술문 임베딩 (추천 품질 개선)

### 설계 근거

직접 사용자 원문을 임베딩하지 않는 이유:
- 콘텐츠 임베딩은 YouTube 영상 제목+설명 텍스트로 생성됨 (`embedding_service.py L108`)
- 사용자 원문("팀장한테 혼났어요")과 콘텐츠("잔잔한 피아노 힐링 음악")는 의미 공간이 달라 cosine similarity가 감정 적합성을 반영하지 못함
- GPT가 생성한 감정 서술문이 두 공간을 의미적으로 연결하는 "번역자" 역할을 함

### 구현 변경 사항

#### 1. `counselor.py` — save_emotion_record 툴 파라미터 확장

`_TOOL_DEFINITIONS` 내 `save_emotion_record` function의 `parameters`에 아래 필드 추가:

```python
"emotion_description": {
    "type": "string",
    "description": (
        "사용자의 현재 감정 상태를 1~2문장으로 서술. "
        "단순 레이블이 아닌 맥락·원인·필요를 포함할 것. "
        "예: '직장 스트레스와 자책감으로 지쳐 있으며, 조용히 마음을 달래줄 콘텐츠가 필요한 상태' "
        "이 문장은 콘텐츠 추천 임베딩 쿼리로 직접 사용됨."
    ),
}
```

`required` 리스트에 `"emotion_description"` 추가.

`_TOOL_FUNCTIONS`의 `save_emotion_record` 람다도 `emotion_description` 전달하도록 수정:

```python
"save_emotion_record": lambda args: save_emotion_record(
    user_id=args["user_id"],
    session_id=args["session_id"],
    emotion=args["emotion"],
    intensity=args["intensity"],
    emotion_description=args.get("emotion_description", ""),
),
```

`counselor_agent` 함수 내 `emotion_score` 캐시 부분도 `emotion_description` 포함:

```python
if tool_call.function.name == "save_emotion_record":
    try:
        args = json.loads(tool_call.function.arguments)
        state.emotion_score = {
            "emotion": args.get("emotion", ""),
            "intensity": args.get("intensity", 0.0),
            "emotion_description": args.get("emotion_description", ""),
        }
    except (json.JSONDecodeError, TypeError):
        pass
```

#### 2. `ai/prompts/system_prompt.md` — Module 4 Expected Output 수정

현재:
```
(내부 동작) 도구 호출: save_emotion_record(emotion="상세 감정", intensity=수치)
```

수정 후:
```
(내부 동작) 도구 호출: save_emotion_record(
  emotion="24개 기준 감정 중 하나",
  intensity=수치,
  emotion_description="사용자 감정 상태를 맥락·원인·콘텐츠 필요를 담아 1~2문장으로 서술"
)
```

Module 3 Task Instruction 3번 항목도 아래와 같이 수정:

```
3. **Analytical Reasoning & Tool Call**: 사용자의 현재 감정 강도(intensity, 0.0~1.0)를 판단하십시오.
   이후 `save_emotion_record` 도구를 호출할 때:
   - `emotion`: 아래 24개 기준 감정 중 가장 가까운 것 하나를 선택하십시오.
     [불안, 슬픔, 우울, 분노, 공포, 혐오, 권태, 수치, 죄책, 놀람, 질투, 섭섭, 심란,
      재미, 행복, 설렘, 사랑, 정, 연민, 감동, 성취, 평안, 열정, 중립]
   - `emotion_description`: 사용자의 감정 상태를 맥락·원인·필요를 담아 1~2문장으로 서술하십시오.
     이 문장은 콘텐츠 추천 시스템의 임베딩 쿼리로 직접 사용됩니다.
     예시: "이별 후 혼자 남겨진 듯한 외로움과 슬픔을 느끼고 있으며, 조용히 감정을 달래줄 음악이 필요한 상태"
```

**논문 근거 (P4 - 한국어 감정 디지털 온톨로지):**
이유미 외(2020)에서 구축한 24개 한국어 기준 감정 목록을 채택.
긍정 10개(재미, 행복, 설렘, 사랑, 정, 연민, 감동, 성취, 평안, 열정),
부정 13개(불안, 슬픔, 우울, 분노, 공포, 혐오, 권태, 수치, 죄책, 놀람, 질투, 섭섭, 심란),
중립 1개. 해당 논문의 감정 간 상관관계 분석에서 슬픔·놀람, 질투·우울이 강한 부적 상관을 가짐을 확인.

#### 3. `reranker.py` — emotion_vec 생성 로직 개선

현재 (`hybrid_rerank` 함수 내):
```python
emotion_text = f"감정: {emotion}, 위로: {comfort_style}"
emotion_vec = await embed_text(emotion_text)
```

수정 후:
```python
# emotion_description이 있으면 우선 사용, 없으면 fallback
emotion_description = ctx_extra.get("emotion_description", "")
if emotion_description:
    emotion_text = f"{emotion_description} | 선호: {comfort_style}"
else:
    emotion_text = f"감정: {emotion}, 위로: {comfort_style}"
emotion_vec = await embed_text(emotion_text)
```

`hybrid_rerank` 함수 시그니처에 `emotion_description: str = ""` 파라미터 추가.

`content_recommender.py`에서 `hybrid_rerank` 호출 시 `emotion_description` 전달:
```python
emotion_description = state.emotion_score.get("emotion_description", "")

ranked_videos = await hybrid_rerank(
    formatted_cands,
    state.user_id,
    state.session_id,
    emotion,
    intensity,
    emotion_records,
    comfort_style,
    emotion_description=emotion_description,   # 추가
)
```

#### 4. `tools/emotion_record.py` — DB 저장 필드 추가

`save_emotion_record` 함수 파라미터에 `emotion_description` 추가:

```python
def save_emotion_record(
    user_id: str,
    session_id: str,
    emotion: str,
    intensity: float,
    emotion_description: str = "",
    raw_message: str | None = None,
) -> dict:
```

DB insert에 `emotion_description` 포함:
```python
supabase.table("emotion_records").insert({
    "user_id": user_id,
    "session_id": session_id,
    "emotion": emotion,
    "intensity": intensity,
    "emotion_description": emotion_description,
    "raw_message": raw_message,
}).execute()
```

#### 5. DB 마이그레이션 (emotion_records 테이블)

```sql
ALTER TABLE emotion_records
ADD COLUMN emotion_description TEXT;
```

---

## Path B: VA 2D 좌표 (감정 궤적 추적)

### 설계 근거

**논문 근거 (P1, P2, P3):**

- P1 (박선호 외, 2022): Russell의 2D 좌표계(Valence × Arousal)를 감정 스코어링에 활용.
  Valence(정서가)는 감정의 긍정/부정 방향, Arousal(각성)은 활성화/침잠 정도를 나타냄.
- P2 (한의환·차형태, 2017): 단일 점 표현의 한계를 지적하고 타원 영역으로 확장.
  감정에 `confidence_radius`를 부여해 불확실성을 표현. 복합 감정은 intensity 가중 평균으로 합산.
- P3 (한의환·차형태, 2014): Arousal 축의 Active/Inactive 요소가 상호 배타적 특성을 가짐을
  실험으로 검증. 중간 Arousal 값은 불확실한 상태를 의미 → confidence_radius로 반영.

**VA 2D의 역할:**
추천 매칭(Path A)에는 사용하지 않음. 오직 아래 목적으로만 사용:
- 세션 내 감정 변화 추적: `delta_valence`로 "상담 후 기분이 나아졌는가?" 측정
- 기존 `compute_emotion_trend`의 intensity 기반 계산을 valence 기반으로 개선

### EMOTION_VA_MAP 룩업 테이블

새 파일 `ai/tools/emotion_va_map.py` 생성:

```python
"""
ai/tools/emotion_va_map.py

Russell Circumplex Model 기반 한국어 24개 기준 감정의 VA 좌표 룩업 테이블.

좌표 기준:
- Valence: -1.0 (매우 부정) ~ +1.0 (매우 긍정)
- Arousal: -1.0 (매우 침잠) ~ +1.0 (매우 활성화)
- confidence_radius: 감정의 분포 불확실성 반경 (P2, P3 논문의 타원 영역 개념 단순화)

논문 근거:
- P1: 러셀 모델 기반 좌표계 연구 (박선호 외, 2022)
- P2: 러셀 모델 확장 연구 (한의환·차형태, 2017) - 14개 감정 단어 VA 실험 데이터
- P3: 각성 축 특성 연구 (한의환·차형태, 2014) - Arousal의 Active/Inactive 상호 배타성
- P4: 한국어 감정 온톨로지 (이유미 외, 2020) - 24개 기준 감정 목록 및 감정 간 상관관계
"""

# (valence, arousal, confidence_radius)
EMOTION_VA_MAP: dict[str, tuple[float, float, float]] = {
    # ── 긍정 감정 (Valence 양수) ──────────────────────────────
    "행복":  ( 0.80,  0.40, 0.15),
    "재미":  ( 0.60,  0.50, 0.20),
    "열정":  ( 0.70,  0.70, 0.20),
    "설렘":  ( 0.65,  0.60, 0.25),
    "성취":  ( 0.65,  0.20, 0.20),
    "감동":  ( 0.50,  0.30, 0.30),  # P4: 감동-분노 정적 상관 → 넓은 반경
    "사랑":  ( 0.75,  0.20, 0.25),
    "정":    ( 0.70,  0.10, 0.20),
    "평안":  ( 0.60, -0.50, 0.15),
    "연민":  ( 0.10,  0.10, 0.30),  # P4: 긍정-부정 복합 특성
    # ── 중립 ─────────────────────────────────────────────────
    "중립":  ( 0.00,  0.00, 0.25),
    # ── 부정 감정 (Valence 음수) ──────────────────────────────
    "놀람":  ( 0.00,  0.60, 0.30),  # P4: 평가자 일치성 높음 (2.08)
    "심란":  (-0.40,  0.40, 0.20),  # P4: 불안과 강한 정적 상관(0.31)
    "불안":  (-0.50,  0.50, 0.20),
    "공포":  (-0.70,  0.70, 0.20),
    "분노":  (-0.60,  0.80, 0.20),  # P2: 실험 데이터 기반
    "혐오":  (-0.75,  0.30, 0.20),
    "질투":  (-0.40,  0.50, 0.30),  # P4: 유순/악의적 질투 혼재 → 넓은 반경
    "슬픔":  (-0.70, -0.20, 0.20),  # P2: 실험 데이터 기반
    "우울":  (-0.60, -0.40, 0.20),  # P4: 슬픔과 강한 정적 상관(0.36)
    "섭섭":  (-0.40, -0.10, 0.25),
    "수치":  (-0.50,  0.20, 0.25),
    "죄책":  (-0.55,  0.10, 0.25),
    "권태":  (-0.30, -0.60, 0.20),  # P4: 설렘과 강한 부적 상관(-0.42)
}


def compute_va_score(emotions: list[dict]) -> dict:
    """
    복합 감정의 VA 좌표를 intensity 가중 평균으로 계산.

    논문 근거 (P2): 복합 감정은 각 감정의 분포를 intensity 비율로 합산.
    논문 근거 (P3): Arousal 축은 Active/Inactive가 상호 배타적이므로
                    복합 감정 수가 많을수록 불확실성(radius) 증가.

    Args:
        emotions: [{"label": "불안", "intensity": 4}, {"label": "슬픔", "intensity": 2}]
                  intensity는 1~5 척도 (P4 논문 기준)

    Returns:
        {"valence": float, "arousal": float, "radius": float}
    """
    valid = [e for e in emotions if e.get("label") in EMOTION_VA_MAP]
    if not valid:
        return {"valence": 0.0, "arousal": 0.0, "radius": 0.25}

    total_intensity = sum(e["intensity"] for e in valid)
    if total_intensity == 0:
        return {"valence": 0.0, "arousal": 0.0, "radius": 0.25}

    valence = sum(
        EMOTION_VA_MAP[e["label"]][0] * e["intensity"] for e in valid
    ) / total_intensity

    arousal = sum(
        EMOTION_VA_MAP[e["label"]][1] * e["intensity"] for e in valid
    ) / total_intensity

    base_radius = sum(
        EMOTION_VA_MAP[e["label"]][2] * e["intensity"] for e in valid
    ) / total_intensity

    # 복합 감정일수록 Arousal 불확실성 증가 (P3 근거)
    radius = base_radius * (1 + 0.15 * (len(valid) - 1))
    radius = min(radius, 0.5)

    return {
        "valence": round(valence, 3),
        "arousal": round(arousal, 3),
        "radius": round(radius, 3),
    }
```

### VA 좌표 DB 저장

`tools/emotion_record.py` 수정:

```python
from ai.tools.emotion_va_map import EMOTION_VA_MAP

def save_emotion_record(
    user_id: str,
    session_id: str,
    emotion: str,
    intensity: float,
    emotion_description: str = "",
    raw_message: str | None = None,
) -> dict:
    intensity = max(0.0, min(1.0, float(intensity)))

    # VA 좌표 자동 계산 (룩업 테이블 기반)
    va = EMOTION_VA_MAP.get(emotion, (0.0, 0.0, 0.25))
    valence, arousal, va_radius = va

    supabase.table("emotion_records").insert({
        "user_id": user_id,
        "session_id": session_id,
        "emotion": emotion,
        "intensity": intensity,
        "emotion_description": emotion_description,
        "valence": valence,
        "arousal": arousal,
        "va_radius": va_radius,
        "raw_message": raw_message,
    }).execute()
```

### DB 마이그레이션 (emotion_records 테이블)

```sql
ALTER TABLE emotion_records
ADD COLUMN emotion_description TEXT,
ADD COLUMN valence FLOAT,
ADD COLUMN arousal FLOAT,
ADD COLUMN va_radius FLOAT;
```

### compute_emotion_trend 개선 (reranker.py)

현재 `intensity` 스칼라로 트렌드 계산하는 방식을 `valence`로 개선:

```python
def compute_emotion_trend(emotion_records: list[dict]) -> dict:
    """
    최근 감정 기록의 valence 변화로 트렌드 계산.

    논문 근거 (P1): Valence(정서가)는 감정의 긍정/부정 방향을 직접 나타내므로
                    'intensity 변화'보다 'valence 변화'가 심리적 회복을 더 정확히 반영.
    """
    if len(emotion_records) < 2:
        return {"trend": "stable", "direction": 0.0}

    records = sorted(emotion_records, key=lambda r: r["created_at"])[-3:]

    # valence 컬럼이 있으면 사용, 없으면 intensity fallback (하위 호환)
    if records[0].get("valence") is not None:
        values = [float(r.get("valence", 0.0)) for r in records]
        delta = values[-1] - values[0]
        # valence 상승 = 회복, valence 하락 = 악화
        if delta > 0.15:
            return {"trend": "recovering", "direction": delta}
        elif delta < -0.15:
            return {"trend": "worsening", "direction": delta}
        else:
            return {"trend": "stable", "direction": delta}
    else:
        # fallback: 기존 intensity 방식
        intensities = [float(r.get("intensity", 0.5)) for r in records]
        delta = intensities[-1] - intensities[0]
        if delta > 0.15:
            return {"trend": "worsening", "direction": delta}
        elif delta < -0.15:
            return {"trend": "recovering", "direction": delta}
        else:
            return {"trend": "stable", "direction": delta}
```

---

## state.py 수정

`emotion_score` dict의 형식 주석 업데이트:

```python
emotion_score: dict = Field(default_factory=dict)
# 형식:
# {
#   "emotion": "불안",                    # 24개 기준 감정 중 하나
#   "intensity": 0.7,                     # 0.0~1.0
#   "emotion_description": "직장 스트레스와 자책감으로...",  # 임베딩 쿼리용 서술문
# }
```

---

## 구현 순서 (의존성 순)

1. **`ai/tools/emotion_va_map.py`** 신규 생성 — 다른 파일들이 import함
2. **DB 마이그레이션 실행** — `emotion_description`, `valence`, `arousal`, `va_radius` 컬럼 추가
3. **`ai/tools/emotion_record.py`** 수정 — 파라미터 추가, VA 자동 계산, DB 저장
4. **`ai/agents/counselor.py`** 수정 — `_TOOL_DEFINITIONS`, `_TOOL_FUNCTIONS`, `emotion_score` 캐시
5. **`ai/prompts/system_prompt.md`** 수정 — 24개 감정 목록 주입, emotion_description 지시 추가
6. **`ai/agents/reranker.py`** 수정 — `hybrid_rerank` 시그니처, `compute_emotion_trend`, `emotion_vec` 생성
7. **`ai/agents/content_recommender.py`** 수정 — `hybrid_rerank` 호출 시 `emotion_description` 전달
8. **`ai/state.py`** 수정 — 주석 업데이트

---

## 파일별 변경 요약

| 파일 | 변경 유형 | 핵심 내용 |
|------|----------|----------|
| `ai/tools/emotion_va_map.py` | **신규 생성** | 24개 감정 VA 좌표 룩업 테이블, compute_va_score 함수 |
| `ai/tools/emotion_record.py` | 수정 | emotion_description·VA 좌표 저장 |
| `ai/agents/counselor.py` | 수정 | save_emotion_record 툴 파라미터 확장 |
| `ai/prompts/system_prompt.md` | 수정 | 24개 감정 목록, emotion_description 생성 지시 |
| `ai/agents/reranker.py` | 수정 | emotion_vec 개선, compute_emotion_trend valence 기반 전환 |
| `ai/agents/content_recommender.py` | 수정 | emotion_description 전달 |
| `ai/state.py` | 수정 (주석) | emotion_score 형식 문서화 |
| DB (emotion_records) | 마이그레이션 | 컬럼 4개 추가 |

---

## 논문 참조 요약

| 설계 결정 | 참조 논문 |
|----------|----------|
| 24개 한국어 기준 감정 채택 | P4 (이유미 외, 2020) |
| Valence·Arousal 2D 좌표계 | P1 (박선호 외, 2022), P2 (한의환·차형태, 2017) |
| 복합 감정의 intensity 가중 평균 | P2 (한의환·차형태, 2017) |
| confidence_radius (불확실성 반경) | P2·P3 (한의환·차형태) - 타원 영역 개념 단순화 |
| Arousal 복합 감정 시 radius 증가 | P3 (한의환·차형태, 2014) - Active/Inactive 상호 배타성 |
| valence 기반 트렌드 계산 | P1 (박선호 외, 2022) - Valence가 정서 방향의 직접 지표 |
| 감동·질투 등의 넓은 radius | P4 - 감정 간 상관분석 (감동-분노 정적 상관, 질투의 이중 속성) |
