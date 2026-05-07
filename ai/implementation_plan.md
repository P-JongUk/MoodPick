# MoodPick AI 구현 계획 (3-에이전트 구조 + FastMCP) — 최종

## 확정 아키텍처

| 구성 요소 | 역할 |
|----------|------|
| **Orchestrator Agent** | 위기 감지, 의도 분류, 라우팅 |
| **Counselor Agent** | 심리 분석 + 공감 응답 생성 (RAG 활용, 멀티턴 대화) |
| **Content Recommender Agent** | 개인화 판단 + 검색 쿼리 생성 + MCP 호출 |
| **FastMCP YouTube 서버** | YouTube API 실행 + 기술적 필터링만 담당 |

### 역할 분리 원칙

```
Content Recommender Agent (AI 담당):
  감정 + 사용자 선호도 + 세션 맥락
  → "이 사람에게 어떤 콘텐츠가 맞을지" 판단
  → 검색 쿼리 생성: "healing piano music for loneliness"
  → MCP 서버 호출 → 결과를 받아 최종 선정

FastMCP YouTube 서버 (실행 담당):
  쿼리 수신 → YouTube Data API v3 호출
  → 이미 본 영상 제외(watched_ids 필터링) → 결과 반환
```

> **MCP 서버는 "어떤 콘텐츠가 맞는가"를 판단하지 않는다.**
> MCP 서버는 "원하는 영상을 어떻게 찾는가"만 담당한다.

### 임포트 경로 설정 (중요)

`backend/app/main.py` 맨 위에 아래 코드를 추가한다.
백엔드 기존 실행 방법은 **변경 없음** — 기존 임포트도 모두 그대로 유지된다.

```python
# backend/app/main.py 상단에 추가
import sys
from pathlib import Path

# 프로젝트 루트(MoodPick/)를 Python 경로에 추가 → ai/ 패키지 임포트 가능
PROJECT_ROOT = Path(__file__).parent.parent.parent  # main.py → app → backend → MoodPick
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
```

```bash
# 기존 실행 방법 그대로 유지
cd backend
uvicorn app.main:app --reload
```

---

## 구현 순서 (의존성 순서대로)

### Phase 1 — 공유 상태 정의

#### [NEW] `ai/state.py`

```python
from pydantic import BaseModel, Field
from typing import Optional

class CounselingState(BaseModel):
    # 입력 (항상 채워짐)
    user_id: str
    session_id: str
    message: str                                    # 현재 메시지

    # 멀티턴 대화 히스토리 (호출 전 외부에서 주입)
    messages: list[dict] = Field(default_factory=list)
    # 형식: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]

    # Orchestrator가 채움
    is_crisis: bool = False
    intent: str = "상담"               # "상담" / "추천" / "잡담"
    needs_recommendation: bool = False

    # Counselor가 채움
    rag_context: list = Field(default_factory=list)
    emotion_score: dict = Field(default_factory=dict)  # {"emotion": "불안", "intensity": 0.7}
    user_profile: Optional[dict] = None            # Counselor가 조회 후 저장 → Recommender 재사용
    response: str = ""
    # Counselor가 needs_recommendation을 True로 덮어쓸 수 있음

    # Content Recommender가 채움
    recommended_content: Optional[dict] = None     # {"title": ..., "url": ..., "reason": ...}
```

> **`messages`는 `/counseling/message` 엔드포인트에서 DB의 이전 대화를 불러와 주입한다.**

---

### Phase 2 — Python 직접 도구 구현

> **임포트 경로 원칙**: `ai/tools/`는 `backend/app/`을 임포트하지 않는다.
> openai, supabase 클라이언트를 직접 생성해 사용한다. (자체 완결 모듈)
> 환경변수는 `ai/config.py`가 `backend/.env.local`을 읽어 공급한다.

#### [NEW] `ai/tools/rag_search.py`
RAG 벡터 검색 도구.

- 입력: `query_text`, `user_id`, `top_k`
- 동작:
  - `openai.embeddings.create()` → 임베딩 생성
  - Supabase `match_rag_chunks` RPC 호출
- 출력: 청크 텍스트 목록

#### [NEW] `ai/tools/user_profile.py`
온보딩 정보 + 최근 세션 감정 이력 조회.

- 입력: `user_id`
- 동작:
  - Supabase `user_profiles`에서 `onboarding_profile` (concerns, comfort_style) 조회
  - 최근 세션 `survey_responses`에서 감정 이력 조회
- 출력: `{ concerns, comfort_style, recent_emotions }`

#### [NEW] `ai/tools/content_history.py`
시청 기록 + 콘텐츠 피드백 조회.

- 입력: `user_id`
- 동작:
  - Supabase `watched_content_records`에서 `video_id` 목록 조회
  - Supabase `content_feedback`에서 `liked`, `disliked` content_id 목록 조회
- 출력: `{ watched_ids, liked_ids, disliked_ids }`

#### [NEW] `ai/tools/emotion_record.py`  ← 신규 추가 (save_emotion_record)
감정 분석 결과를 DB에 저장하는 도구.

- 입력: `user_id`, `session_id`, `emotion`, `intensity`
- 동작:
  - Supabase `emotion_records` 테이블에 감정 기록 upsert
- 출력: `{ success: bool }`

---

### Phase 3 — 유틸리티 및 환경변수 설정

#### [NEW] `ai/config.py`  ← 신규 추가 (환경변수 로딩)
`ai/` 모듈이 `backend/.env.local`의 환경변수를 직접 읽도록 설정한다.

```python
# ai/config.py
from dotenv import load_dotenv
from pathlib import Path
import os

# backend/.env.local을 ai 모듈이 직접 로드
_env_path = Path(__file__).parent.parent / "backend" / ".env.local"
if _env_path.exists():
    load_dotenv(_env_path)

# ai 모듈 전역에서 사용하는 설정
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
```

> `ai/tools/` 각 파일 상단에서 `from ai.config import OPENAI_API_KEY` 등으로 임포트한다.

#### [NEW] `ai/utils.py`
프롬프트 파일 로딩 유틸리티.

```python
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent / "prompts"

def load_prompt(filename: str) -> str:
    """ai/prompts/ 폴더에서 프롬프트 파일을 읽어 반환한다."""
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")

def load_crisis_response() -> str:
    """위기 대응 텍스트를 반환한다."""
    return load_prompt("crisis_response.md")
```

---

### Phase 4 — FastMCP YouTube 서버 구축

#### [NEW] `mcp_servers/youtube/server.py`

```python
from dotenv import load_dotenv
load_dotenv()  # mcp_servers/youtube/.env 명시적 로드

from fastmcp import FastMCP
import os

mcp = FastMCP("moodpick-youtube")

@mcp.tool()
async def search_youtube(
    query: str,
    watched_ids: list[str] | None = None,  # 뮤터블 기본값 방지
    max_results: int = 5,
) -> list[dict]:
    """
    YouTube에서 영상을 검색하고 기술적 필터링만 수행한다.
    개인화 판단은 하지 않음 — 에이전트가 이미 쿼리에 반영했음.

    반환: [{"video_id": ..., "title": ..., "url": ..., "thumbnail": ...}]
    """
    api_key = os.getenv("YOUTUBE_API_KEY")
    exclude = watched_ids or []
    # 1. YouTube Data API v3 호출
    # 2. exclude(watched_ids) 제외
    # 3. 결과 반환 (판단/선정은 에이전트 몫)
```

#### [NEW] `mcp_servers/youtube/.env`

```
YOUTUBE_API_KEY=your_youtube_api_key_here
```

> ⚠️ `mcp_servers/youtube/.env`는 반드시 `.gitignore`에 추가할 것

#### [NEW] `mcp_servers/youtube/requirements.txt`

```
fastmcp>=0.1.0
google-api-python-client>=2.0.0
python-dotenv>=1.0.0
```

> Spotify 추가 시: `mcp_servers/spotify/server.py` 동일 패턴으로 추가

---

### Phase 5 — 프롬프트 작성

#### [NEW] `ai/prompts/orchestrator_prompt.md`

```
역할: 사용자 메시지를 보고 아래 3가지를 판단해 JSON으로 반환하라.
1. is_crisis: 자해/자살/타해 징후 여부 (true/false)
2. intent: "상담" / "추천" / "잡담"
3. needs_recommendation: 명시적 콘텐츠 요청 여부 (true/false)

응답 형식: {"is_crisis": false, "intent": "상담", "needs_recommendation": false}
반드시 JSON만 반환하라. 다른 텍스트 없이.
```

#### [NEW] `ai/prompts/system_prompt.md`

```
당신은 MoodPick의 AI 심리 상담사입니다.
- 항상 공감으로 시작한다 ("그 마음이 많이 무거우셨겠어요")
- 의학적 진단/처방을 내리지 않는다
- RAG 근거가 약하면 단정형 표현 금지
- 2~4문장으로 간결하게 응답한다
- 한국어로 응답한다
- 이전 대화 흐름을 반드시 참고해 응답한다
```

#### [NEW] `ai/prompts/content_recommender_prompt.md`

```
당신은 사용자의 감정 상태에 맞는 YouTube 콘텐츠를 추천하는 AI입니다.

입력 정보:
- 감정: {emotion} (강도: {intensity})
- 사용자 고민 카테고리: {concerns}
- 선호 위로 방식: {comfort_style}

규칙:
- 감정 강도가 높을수록 자극이 적은 콘텐츠(명상, 잔잔한 음악)를 선택한다
- comfort_style이 "음악"이면 뮤직비디오/플레이리스트 위주로
- comfort_style이 "영상"이면 힐링 영상/브이로그 위주로
- 검색 쿼리는 영어로 생성한다 (YouTube 검색 정확도 향상)
- 추천 이유를 한국어로 1문장으로 작성한다

출력 형식: {"search_query": "...", "reason": "..."}
```

> **템플릿 치환**: `content_recommender.py`에서 `load_prompt()`로 읽은 뒤
> `prompt.format(emotion=..., intensity=..., concerns=..., comfort_style=...)` 로 치환 후 GPT에 전달한다.

#### [NEW] `ai/prompts/crisis_response.md`

```
지금 많이 힘드시죠. 혼자 감당하지 않아도 됩니다.
지금 바로 자살예방상담전화 1393 (24시간)에 연락해 주세요.
```

---

### Phase 6 — 에이전트 구현

#### [NEW] `ai/agents/orchestrator.py`

```python
async def orchestrator_agent(state: CounselingState) -> CounselingState:
    """
    1. orchestrator_prompt.md 로드 (load_prompt 사용)
    2. GPT 호출 (response_format=json_object)
       - 입력: 현재 message만 전달 (히스토리 불필요)
    3. 결과 파싱 → state.is_crisis, state.intent, state.needs_recommendation 업데이트
    """
```

> 모델: `gpt-4o-mini`, temperature: 0, max_tokens: 100

#### [NEW] `ai/agents/counselor.py`

```python
async def counselor_agent(state: CounselingState) -> CounselingState:
    """
    tools = [search_rag_context, get_user_profile_and_history, save_emotion_record]

    멀티턴 처리:
      - state.messages (이전 대화 히스토리)를 GPT messages에 포함
      - 현재 message를 마지막 user 메시지로 추가

    GPT Function Calling 루프:
      while tool_calls:
          tool 실행 → 결과 messages에 추가 → GPT 재호출

    출력:
      state.response              ← 공감 상담 응답
      state.emotion_score         ← {"emotion": "불안", "intensity": 0.7}
      state.user_profile          ← 조회한 유저 프로필 저장 (Recommender 재사용)
      state.needs_recommendation  ← 맥락 기반 추천 필요 여부
    """
```

> 모델: `gpt-4o-mini`, temperature: 0.7, max_tokens: 500

#### [NEW] `ai/agents/content_recommender.py`

```python
async def content_recommender_agent(state: CounselingState) -> CounselingState:
    """
    [에이전트: 개인화 판단 + 쿼리 생성]
    1. state.user_profile에서 concerns, comfort_style 읽기 (재조회 불필요)
    2. content_history.py로 watched_ids, liked_ids, disliked_ids 조회
    3. content_recommender_prompt.md 로드 후 템플릿 치환:
       prompt.format(emotion=..., intensity=..., concerns=..., comfort_style=...)
    4. GPT에게 개인화된 YouTube 검색 쿼리 + 추천 이유 생성 요청
       예: "불안(0.8) + 음악 선호 → search_query: 'healing piano music calm anxiety'"

    [MCP 호출: 실행 담당]
    5. FastMCP YouTube 서버의 search_youtube(query, watched_ids) 호출
    6. 결과 목록 수신 (최대 5개 후보)

    [에이전트: 최종 선정]
    7. liked_ids / disliked_ids 기반 최적 영상 1개 선정 (GPT 판단)
    8. state.recommended_content 업데이트
       {"title": ..., "url": ..., "video_id": ..., "reason": ...}
    """
```

---

### Phase 7 — 파이프라인 조립

#### [NEW] `ai/pipeline.py`

```python
from ai.state import CounselingState
from ai.utils import load_crisis_response
from ai.agents.orchestrator import orchestrator_agent
from ai.agents.counselor import counselor_agent
from ai.agents.content_recommender import content_recommender_agent

async def run_counseling_pipeline(
    user_id: str,
    session_id: str,
    message: str,
    messages: list[dict] | None = None,   # 뮤터블 기본값 방지
) -> CounselingState:

    state = CounselingState(
        user_id=user_id,
        session_id=session_id,
        message=message,
        messages=messages or [],           # None이면 빈 리스트
    )

    # ① Orchestrator
    state = await orchestrator_agent(state)
    if state.is_crisis:
        state.response = load_crisis_response()
        return state                       # 즉시 종료

    # ② Counselor
    state = await counselor_agent(state)

    # ③ Content Recommender (조건부)
    if state.needs_recommendation:
        state = await content_recommender_agent(state)

    return state
```

---

### Phase 8 — 백엔드 연결

#### [NEW] `backend/app/services/ai_service.py`

```python
# main.py의 sys.path 설정 덕분에 ai/ 패키지 임포트 가능
from ai.pipeline import run_counseling_pipeline

async def get_ai_response(
    user_id: str,
    session_id: str,
    message: str,
    messages: list[dict] | None = None,   # 뮤터블 기본값 방지
) -> dict:
    try:
        state = await run_counseling_pipeline(
            user_id=user_id,
            session_id=session_id,
            message=message,
            messages=messages,
        )
        return {
            "message": state.response,
            "emotion": state.emotion_score,
            "recommended_content": state.recommended_content,
        }
    except Exception as e:
        # Fallback: 규칙 기반 응답 (대화 단절 방지)
        return {"message": "지금 감정을 한 문장으로 표현해 보면 원인을 더 명확히 찾는 데 도움이 돼요."}
```

#### [MODIFY] `backend/app/routers/counseling.py`

아래 두 헬퍼 함수를 `backend/app/services/` 또는 해당 파일 내부에 추가한다.

```python
def fetch_session_messages(supabase: Client, session_id: str) -> list[dict]:
    """세션의 이전 대화 이력을 가져온다."""
    result = supabase.table("counseling_history") \
        .select("role, content") \
        .eq("session_id", session_id) \
        .order("created_at") \
        .execute()
    return [{"role": r["role"], "content": r["content"]} for r in (result.data or [])]

def save_message(supabase: Client, session_id: str, user_msg: str, ai_msg: str) -> None:
    """사용자 메시지와 AI 응답을 DB에 저장한다."""
    supabase.table("counseling_history").insert([
        {"session_id": session_id, "role": "user",      "content": user_msg},
        {"session_id": session_id, "role": "assistant",  "content": ai_msg},
    ]).execute()
```

```python
@router.post("/message")
async def send_counseling_message(
    payload: CounselingMessageRequest,
    supabase: Client = Depends(get_supabase_client),
):
    # 1. 이전 대화 이력 조회
    history = fetch_session_messages(supabase, payload.session_id)

    # 2. AI 파이프라인 호출
    result = await get_ai_response(
        user_id=payload.user_id,
        session_id=payload.session_id,
        message=payload.message,
        messages=history,
    )

    # 3. 이번 대화를 DB에 저장
    save_message(supabase, payload.session_id, payload.message, result["message"])

    return {**result, "status": "ok"}
```

---

## 파일 생성 순서 요약

```
0.  backend/app/main.py              ← [MODIFY] sys.path 추가 (가장 먼저)

1.  ai/state.py                      ← messages + user_profile 포함
2.  ai/config.py                     ← NEW: 환경변수 로딩 (backend/.env.local 참조)
3.  ai/utils.py                      ← load_prompt, load_crisis_response
4.  ai/tools/rag_search.py           ← openai/supabase 직접 호출
5.  ai/tools/user_profile.py
6.  ai/tools/content_history.py      ← NEW: watched_ids / liked / disliked
7.  ai/tools/emotion_record.py       ← NEW: save_emotion_record (감정 기록 저장)
8.  mcp_servers/youtube/server.py    ← FastMCP 서버 (load_dotenv 포함)
9.  mcp_servers/youtube/.env         ← YOUTUBE_API_KEY (gitignore 추가)
10. mcp_servers/youtube/requirements.txt
11. ai/prompts/orchestrator_prompt.md
12. ai/prompts/system_prompt.md
13. ai/prompts/content_recommender_prompt.md ← NEW
14. ai/prompts/crisis_response.md
15. ai/agents/orchestrator.py
16. ai/agents/counselor.py           ← 멀티턴 + user_profile 저장
17. ai/agents/content_recommender.py ← 템플릿 치환 + MCP 호출
18. ai/pipeline.py
19. backend/app/services/ai_service.py
20. backend/app/routers/counseling.py ← 헬퍼 함수 + 히스토리 연동
```

---

## 환경변수

| 변수 | 위치 | 용도 | 필수 여부 |
|------|------|------|----------|
| `OPENAI_API_KEY` | `backend/.env.local` | GPT + 임베딩 호출 | ✅ 필수 |
| `SUPABASE_URL` | `backend/.env.local` | RAG + 유저 조회 | ✅ 필수 |
| `SUPABASE_SERVICE_ROLE_KEY` | `backend/.env.local` | Supabase 접근 | ✅ 필수 |
| `YOUTUBE_API_KEY` | `mcp_servers/youtube/.env` | YouTube 검색 | ✅ 필수 (추천 기능) |

---

## 추가 의존성

```
# backend/requirements.txt에 추가
fastmcp>=0.1.0      # FastMCP 클라이언트 (Content Recommender에서 MCP 서버 호출)

# mcp_servers/youtube/requirements.txt (별도 관리)
fastmcp>=0.1.0
google-api-python-client>=2.0.0
python-dotenv>=1.0.0
```

---

## .gitignore 추가 항목

```
mcp_servers/youtube/.env
mcp_servers/spotify/.env   # 나중에 추가 시 대비
```

---

## 검증 계획

### 단계별 스모크 테스트

```bash
# 백엔드는 기존 방식 그대로
cd backend
uvicorn app.main:app --reload

# 1. FastMCP 서버 단독 테스트 (별도 터미널)
cd mcp_servers/youtube && python server.py

# 2. RAG 검색 도구 테스트
POST /rag/search-by-text  {"query_text": "스트레스가 심해요", "top_k": 3}

# 3. 전체 파이프라인 — 일반 상담
POST /counseling/message  {"user_id": "...", "session_id": "...", "message": "요즘 너무 힘들어요"}

# 4. 위기 감지 테스트
POST /counseling/message  {"user_id": "...", "session_id": "...", "message": "다 끝내고 싶어"}

# 5. 추천 트리거 테스트
POST /counseling/message  {"user_id": "...", "session_id": "...", "message": "노래 추천해줘"}

# 6. 멀티턴 테스트 (2번 이상 메시지 후 맥락 유지 확인)
```

### 합격 기준

- [ ] 일반 메시지 → 공감 상담 응답 반환 (3~5초 이내)
- [ ] 멀티턴 대화 → 이전 맥락을 반영한 응답
- [ ] 위기 메시지 → 1393 안내 즉시 반환
- [ ] 추천 요청 → 개인화된 YouTube 영상 1개 반환
- [ ] GPT 에러 → fallback 응답 (대화 단절 없음)
- [ ] MCP 서버 미응답 → 추천 없이 상담만 정상 반환
