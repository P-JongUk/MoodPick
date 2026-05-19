# MoodPick ?대옒??援ъ“)????Pydantic 紐⑤뜽 以묒떖 (Obsidian??

> ???꾨줈?앺듃???꾪넻?곸씤 OOP ?대옒??怨꾩링蹂대떎 **FastAPI ?쇱슦??+ Pydantic(BaseModel) ?붿껌/?묐떟 紐⑤뜽**??以묒떖?낅땲??
> ?곕씪???쒗겢?섏뒪?꾟앸뒗 **API DTO(?붿껌/?묐떟 ?ㅽ궎留? 援ъ“??*濡??뺣━?⑸땲??

## 1) Auth 紐⑤뜽 (`backend/app/routers/auth.py`)

```mermaid
classDiagram
  class AuthRequest {
    +EmailStr email
    +str password
  }
```

## 2) Session 紐⑤뜽 (`backend/app/routers/session.py`)

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

## 3) Survey(臾몄쭊) 紐⑤뜽 (`backend/app/routers/survey.py`)

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

## 4) Emotion(媛먯젙) 紐⑤뜽 (`backend/app/routers/emotion.py`)

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

> 媛먯젙 ?쒓린濡??붿빟???묐떟? `emotion.py`?먯꽌 `dict` ?뺥깭濡?諛섑솚?섎ŉ, ?꾨줎?몄뿉??蹂꾨룄 ??낆쑝濡??ъ슜?⑸땲??

## 5) Counseling(?곷떞) 紐⑤뜽 (`backend/app/routers/counseling.py`)

```mermaid
classDiagram
  class CounselingMessageRequest {
    +str user_id
    +str message
    +str session_id <<optional>>
  }
```

## 6) Content(肄섑뀗痢? 紐⑤뜽 (`backend/app/routers/content.py`)

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

## 7) User(?꾨줈?? 紐⑤뜽 (`backend/app/routers/user.py`)

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

## 8) Reminder 紐⑤뜽 (`backend/app/routers/reminder.py`)

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

## 9) RAG 紐⑤뜽 (`backend/app/routers/rag.py`)

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

## 10) 李멸퀬(?쇱슦??援ъ꽦)

?쇱슦?곕뒗 `backend/app/main.py`?먯꽌 ?ㅼ쓬 ?쒖꽌濡?include ?⑸땲??

- `auth`, `session`, `counseling`, `emotion`, `survey`, `content`, `user`, `rag`, `reminder`
