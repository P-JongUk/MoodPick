# MoodPick 클래스(구조)도 — Pydantic 모델 중심 (Obsidian용)

> 이 프로젝트는 전통적인 OOP 클래스 계층보다 **FastAPI 라우터 + Pydantic(BaseModel) 요청/응답 모델**이 중심입니다.  
> 따라서 “클래스도”는 **API DTO(요청/응답 스키마) 구조도**로 정리합니다.

## 1) Auth 모델 (`backend/app/routers/auth.py`)

```mermaid
classDiagram
  class AuthRequest {
    +EmailStr email
    +str password
  }
```

## 2) Session 모델 (`backend/app/routers/session.py`)

```mermaid
classDiagram
  class SessionStartRequest {
    +str user_id
    +str context <<optional>>
  }

  class SessionEndRequest {
    +str session_id
  }

  class SessionResponse {
    +str id
    +str user_id
    +str status
    +str started_at
    +str ended_at <<optional>>
  }
```

## 3) Survey(문진) 모델 (`backend/app/routers/survey.py`)

```mermaid
classDiagram
  class SurveyQuestion {
    +str key
    +str question
    +str type
    +List~str~ emoji_options
  }

  class SurveyResponseRequest {
    +str session_id
    +str phase
    +str question_key
    +str emoji_value
  }

  class SurveyDeltaResponse {
    +dict pre_scores
    +dict post_scores
    +dict delta
    +bool improved
  }
```

## 4) Emotion(감정) 모델 (`backend/app/routers/emotion.py`)

```mermaid
classDiagram
  class EmotionAnalysisRequest {
    +str user_input
    +str context <<optional>>
  }

  class EmotionAnalysisResponse {
    +str emotion
    +float intensity
    +List~str~ recommendations
  }
```

> 감정 “기록/요약” 응답은 `emotion.py`에서 `dict` 형태로 반환되며, 프론트에서 별도 타입으로 사용합니다.

## 5) Counseling(상담) 모델 (`backend/app/routers/counseling.py`)

```mermaid
classDiagram
  class CounselingMessageRequest {
    +str user_id
    +str message
    +str session_id <<optional>>
  }
```

## 6) Content(콘텐츠) 모델 (`backend/app/routers/content.py`)

```mermaid
classDiagram
  class ContentFeedbackRequest {
    +str session_id <<optional>>
    +str user_id
    +str content_id
    +str feedback  <<like|dislike>>
  }

  class WatchedContentRequest {
    +str user_id
    +str session_id <<optional>>
    +str content_id
    +str content_title
    +str thumbnail_url <<optional>>
  }

  class ContentFeedbackResponse {
    +str id
    +str session_id <<optional>>
    +str user_id
    +str content_id
    +str feedback
    +str created_at
  }

  class WatchedContentResponse {
    +str id
    +str user_id
    +str session_id <<optional>>
    +str content_id
    +str content_title
    +str thumbnail_url <<optional>>
    +str watched_at
  }
```

## 7) User(프로필) 모델 (`backend/app/routers/user.py`)

```mermaid
classDiagram
  class UserProfileResponse {
    +str id
    +str email
    +str name <<optional>>
    +str avatar_url <<optional>>
    +str created_at
  }

  class UserProfileUpsertRequest {
    +str user_id
    +str display_name
  }
```

## 8) Reminder 모델 (`backend/app/routers/reminder.py`)

```mermaid
classDiagram
  class ReminderPreferenceRequest {
    +str user_id
    +bool enabled
    +str reminder_time
    +str timezone
  }

  class ReminderMarkSentRequest {
    +str user_id
  }
```

## 9) RAG 모델 (`backend/app/routers/rag.py`)

```mermaid
classDiagram
  class RagSearchRequest {
    +List~float~ query_embedding  <<1536-dim>>
    +str user_id <<optional>>
    +int top_k  <<1..20>>
  }

  class RagSearchByTextRequest {
    +str query_text
    +str user_id <<optional>>
    +int top_k  <<1..20>>
  }

  class RagSearchResult {
    +str chunk_id
    +str document_id
    +str content
    +float similarity
  }

  RagSearchRequest --> RagSearchResult : returns[]
  RagSearchByTextRequest --> RagSearchResult : returns[]
```

## 10) 참고(라우터 구성)

라우터는 `backend/app/main.py`에서 다음 순서로 include 됩니다:

- `auth`, `session`, `counseling`, `emotion`, `survey`, `content`, `user`, `rag`, `reminder`

