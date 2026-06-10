# MoodPick AI 모듈

## 개요

3-에이전트 상담/추천 파이프라인으로 대화, 감정 기록, 개인화 콘텐츠 추천을 제공합니다.
상담 응답과 감정 저장, YouTube 기반 추천이 하나의 흐름으로 이어집니다.

---

## 에이전트 아키텍처 (3-Agent)

### 전체 흐름

```
사용자 메시지
      ↓
① Orchestrator Agent
  · 위기 징후 감지 (자해/자살 신호)
  · 대화 의도 분류 ("상담" / "추천 요청" / "잡담")
  · 콘텐츠 추천 필요 여부 초기 판단 (명시적 요청 시)
      ↓                    ↓
 [위기 감지]          [일반 대화]
      ↓                    ↓
🚨 안전 응답      ② Counselor Agent
  (즉시 종료)       · RAG 검색 (전문 상담 맥락 참조)
                    · 사용자 프로필 + 히스토리 조회
                    · 심리 상태 분석 (감정/강도/패턴)
                    · 공감 응답 생성
                    · 감정 기록 저장
                    · 추천 필요 여부 최종 판단 (맥락 기반)
                          ↓
                   ③ Content Recommender Agent
                     (Orchestrator 또는 Counselor가 트리거 시만 실행)
                     · 감정 지수 + 온보딩 선호도 조합
                     · YouTube 검색 및 콘텐츠 선정
                     · 추천 이유 생성
                          ↓
                   최종 응답 (상담 응답 + 콘텐츠 추천)
```

---

### 에이전트별 역할 상세

#### ① Orchestrator Agent
| 항목 | 내용 |
|------|------|
| 역할 | 위기 감지, 의도 분류, 라우팅 |
| 모델 | GPT-4o-mini (경량 판단) |
| 응답 시간 | 약 0.5~1초 |
| 출력 | `is_crisis`, `intent`, `needs_recommendation` |

**라우팅 규칙:**
- 위기 징후 감지 → 즉시 안전 응답, 이후 에이전트 건너뜀
- 명시적 추천 요청("음악 틀어줘") → `needs_recommendation=True`로 Content Recommender 트리거
- 일반 상담 → Counselor에게 `needs_recommendation` 판단 위임

#### ② Counselor Agent (상담 + 심리 분석 통합)
| 항목 | 내용 |
|------|------|
| 역할 | 심리 분석 + 공감 응답 생성 (동시 처리) |
| 모델 | GPT-4o-mini (Function Calling) |
| 응답 시간 | 약 2~4초 |
| 출력 | `response`, `emotion_score`, `needs_recommendation` |

**분석과 응답을 통합한 이유:**
심리 분석 결과가 응답의 톤·단어·질문 방향을 실시간으로 결정하므로, 분리 시 대화의 자연스러움과 품질이 저하됨. 단일 LLM이 "분석하면서 공감 응답"을 동시에 수행하는 것이 더 효과적.

**사용 도구 (Function Calling):**
- `search_rag_context(query_text, user_id, top_k)` — 전문 상담 매뉴얼 RAG 검색
- `get_user_profile_and_history(user_id)` — 온보딩 선호도 + 이전 대화 이력
- `save_emotion_record(user_id, session_id, valence, arousal, emotion_description, raw_message)` — 감정 기록 저장 (`emotion`/`va_radius`는 valence/arousal로부터 룩업 계산)

#### ③ Content Recommender Agent
| 항목 | 내용 |
|------|------|
| 역할 | 개인화 콘텐츠 검색 및 추천 |
| 모델 | GPT-4o-mini (Function Calling) |
| 응답 시간 | 약 1~2초 |
| 출력 | `recommended_content` |
| 실행 조건 | Orchestrator(명시 요청) 또는 Counselor(맥락 판단) 트리거 시만 실행 |

**사용 도구 (Function Calling):**
- `recommend_youtube(emotion, concerns, comfort_style, history)` — YouTube 영상 검색 및 선정

**콘텐츠 추천 결정 주체:**

| 상황 | 결정 주체 |
|------|----------|
| 사용자가 명시적으로 요청 ("노래 틀어줘") | Orchestrator |
| 상담 중 감정 케어 시급도(`intensity`) 기반 자동 추천 판단 | Counselor |

---

### Shared State (공유 상태)

모든 에이전트가 공유하고 업데이트하는 공통 데이터 객체:

```python
class CounselingState(TypedDict):
    # 입력
    user_id: str
    session_id: str
    message: str

    # Orchestrator가 채움
    is_crisis: bool             # 위기 징후 여부
    intent: str                 # "상담" / "추천" / "잡담"
    needs_recommendation: bool  # 콘텐츠 추천 필요 여부 (초기 판단)

    # Counselor가 채움
    rag_context: list           # RAG 검색 결과
    emotion_score: dict         # {"emotion": "불안", "valence": -0.5, "arousal": 0.5,
                                #  "intensity": 0.50,  # 케어 시급도 = min(1, max(0,-V)*0.6 + |A|*0.4)
                                #  "emotion_description": "..."}
    response: str               # 최종 상담 응답
    needs_recommendation: bool  # 최종 판단 (Counselor가 덮어쓸 수 있음)

    # Content Recommender가 채움
    recommended_content: dict   # {"title": ..., "url": ..., "reason": ...}
```

---

### 안전 가드레일 (Guardrail)

- **위기 대응**: 자해/자살 징후 감지 시 Orchestrator에서 즉시 차단, 전문 기관 안내 (자살예방상담전화 1393) 반환
- **윤리 준수**: 의학적 처방 및 법적 조언 금지, 정서적 케어와 보조 콘텐츠 제공에 집중
- **Fallback**: 에이전트 실패 시 규칙 기반 응답으로 대화 단절 방지

---

### 예상 응답 시간

| 시나리오 | 소요 시간 |
|---------|----------|
| 위기 감지 (즉시 차단) | ~1초 |
| 일반 상담 (콘텐츠 추천 없음) | ~3~5초 |
| 상담 + 콘텐츠 추천 | ~4~7초 |

---

## 폴더 구조

```
ai/
├── agents/                     # 에이전트 모듈
│   ├── orchestrator.py         # ① Orchestrator Agent
│   ├── counselor.py            # ② Counselor Agent (분석 + 응답)
│   └── content_recommender.py  # ③ Content Recommender Agent
├── pipeline.py                 # 3-에이전트 실행 파이프라인
├── state.py                    # CounselingState 공유 상태 정의
├── prompts/                    # AI 프롬프트
│   ├── system_prompt.md        # 상담 페르소나 및 행동 규칙
│   ├── orchestrator_prompt.md  # Orchestrator 판단 기준 프롬프트
│   └── crisis_response.md      # 위기 대응 안전 응답 템플릿
├── tools/                      # Function Calling 도구 실행 모듈
│   ├── rag_search.py           # RAG 검색 (search_rag_context)
│   ├── emotion_record.py       # 감정 기록 저장
│   ├── content_history.py      # 시청/피드백 이력 조회
│   ├── user_profile.py         # 사용자 프로필/이력 조회
│   └── user_taste.py           # 취향 벡터 갱신
└── README.md                   # 이 파일
```

---

## Function Calling 도구 목록

| 도구 | 사용 에이전트 | 역할 |
|------|-------------|------|
| `search_rag_context` | Counselor | 전문 상담 매뉴얼 벡터 검색 |
| `get_user_profile_and_history` | Counselor | 온보딩 선호도 + 이전 세션 이력 |
| `save_emotion_record` | Counselor | 감정 분석 결과 DB 저장 |
| `recommend_youtube` | Content Recommender | 감정/선호도 기반 YouTube 검색 (MCP 연동) |

---

## 개발 환경 설정

프로젝트 전체 개요와 실행 방법은 [루트 README](../README.md)를 참고하세요.

### 추가 의존성 (requirements.txt에 추가 필요)

```
openai>=1.0.0   # 이미 설치됨
# LangGraph 미사용 — 3-에이전트 선형 흐름은 순수 Python으로 구현
```
