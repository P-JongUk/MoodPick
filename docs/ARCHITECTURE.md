# MoodPick 아키텍처 / 모듈 구조 (Obsidian용)

> **3-에이전트 + MCP 순환 도식**의 개요는 이 문서와 [루트 README](../README.md), [AI 모듈 README](../ai/README.md)를 함께 보세요.

## 1) 시스템 아키텍처(컨테이너/컴포넌트)

```mermaid
flowchart LR
  FE_UI[UI]
  FE_API[api.ts]
  FE_SESS[sessionData.ts]

  BE_MAIN[main.py]
  BE_AUTH[auth.py]
  BE_SESSION[session.py]
  BE_COUNSEL[counseling.py]
  BE_SURVEY[survey.py]
  BE_EMOTION[emotion.py]
  BE_RAG[rag.py]
  BE_CONTENT[content.py]
  BE_USER[user.py]
  BE_REMIND[reminder.py]
  BE_SUPA[supabase_service.py]
  BE_EMBED[embedding_service.py]
  BE_SCHED[reminder_scheduler.py]

  SB_AUTH[Supabase Auth]
  SB_DB[Postgres pgvector]

  EX_OPENAI[OpenAI]
  EX_YT[YouTube]

  FE_UI --> FE_API --> BE_MAIN
  FE_UI --> FE_SESS --> BE_MAIN

  BE_MAIN --> BE_AUTH
  BE_MAIN --> BE_SESSION
  BE_MAIN --> BE_COUNSEL
  BE_MAIN --> BE_SURVEY
  BE_MAIN --> BE_EMOTION
  BE_MAIN --> BE_RAG
  BE_MAIN --> BE_CONTENT
  BE_MAIN --> BE_USER
  BE_MAIN --> BE_REMIND

  BE_AUTH --> BE_SUPA --> SB_DB
  BE_SESSION --> BE_SUPA --> SB_DB
  BE_COUNSEL --> BE_SUPA --> SB_DB
  BE_SURVEY --> BE_SUPA --> SB_DB
  BE_EMOTION --> BE_SUPA --> SB_DB
  BE_CONTENT --> BE_SUPA --> SB_DB
  BE_USER --> BE_SUPA --> SB_DB
  BE_REMIND --> BE_SUPA --> SB_DB

  BE_RAG --> BE_EMBED --> EX_OPENAI
  BE_RAG --> BE_SUPA --> SB_DB

  BE_MAIN --> BE_SCHED

  FE_UI --> SB_AUTH
  BE_MAIN --> SB_AUTH
  BE_MAIN --> EX_YT
```

## 2) 데이터 모델(핵심 테이블) — 간단 ERD

> 실제 테이블 생성/함수는 `db/migrations/*.sql`에 정의됨.

```mermaid
erDiagram
  counseling_sessions {
    uuid id PK
    uuid user_id FK
    text status
    timestamptz started_at
    timestamptz ended_at
  }

  survey_responses {
    uuid id PK
    uuid session_id FK
    text phase
    text question_key
    text emoji_value
    float score
    timestamptz created_at
  }

  content_feedback {
    uuid id PK
    uuid session_id FK
    uuid user_id FK
    text content_id
    text feedback
    timestamptz created_at
  }

  watched_content_records {
    uuid id PK
    uuid user_id FK
    uuid session_id FK
    text content_id
    text content_title
    text thumbnail_url
    timestamptz watched_at
  }

  user_profiles {
    uuid user_id PK
    text display_name
    timestamptz created_at
    timestamptz updated_at
  }

  user_reminder_preferences {
    uuid user_id PK
    bool enabled
    text reminder_time
    text timezone
    timestamptz updated_at
  }

  reminder_dispatch_logs {
    uuid id PK
    uuid user_id FK
    timestamptz dispatched_at
    text status
  }

  rag_documents {
    uuid id PK
    uuid user_id
    text title
    timestamptz created_at
  }

  rag_chunks {
    uuid id PK
    uuid document_id FK
    uuid user_id
    vector embedding
    text content
  }

  emotion_embeddings {
    uuid id PK
    uuid user_id
    vector embedding
    timestamptz created_at
  }

  emotion_records {
    uuid id PK
    uuid user_id
    uuid session_id
    text emotion
    float intensity
    text raw_message
    timestamptz created_at
  }

  counseling_history {
    uuid id PK
    uuid user_id
    uuid session_id
    text role
    text message
    timestamptz created_at
  }

  counseling_sessions ||--o{ survey_responses : has
  counseling_sessions ||--o{ content_feedback : has
  counseling_sessions ||--o{ watched_content_records : has
  counseling_sessions ||--o{ counseling_history : has
  counseling_sessions ||--o{ emotion_records : has

  rag_documents ||--o{ rag_chunks : contains
```

## 3) 핵심 플로우(요약)

- **문진 점수화 / 변화량(Δ)** (`survey.py`)
  - 이모지 → 점수(`MOOD_EMOJI_MAP`)로 변환 후 저장
  - 같은 세션의 pre/post 점수 차이로 Δ 계산, 평균 Δ로 `improved` 판정

- **감정 요약(평균/추이)** (`emotion.py`)
  - 최근 N일 `survey_responses.score` 평균
  - 최근 3개 vs 이전 3개 평균 비교(±0.5)로 `improving/declining/stable`

- **RAG 검색(유사도)** (`rag.py` + DB 함수)
  - 임베딩(기본 1536차원) 생성/입력 → `match_rag_chunks` RPC
  - 코사인 거리 기반, `similarity = 1 - distance`

- **리마인더** (`reminder.py` + 스케줄러 옵션)
  - 마이페이지에서 사용자 설정 저장
  - 서버 설정에 따라 스케줄러 루프가 켜질 수 있음(`main.py` startup)

## 4) 근거 파일(읽는 순서 추천)

- 라우터 포함: `backend/app/main.py`
- 라우터 구현: `backend/app/routers/*.py`
- DB 스키마/함수: `db/migrations/*.sql`
- 프론트 API 호출: `frontend/lib/api.ts`
- 프론트 세션/문진 헬퍼: `frontend/lib/sessionData.ts`
