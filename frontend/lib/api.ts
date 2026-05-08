/**
 * MoodPick Backend API Client
 * 모든 API 호출의 중앙 집중식 관리
 */

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  "http://localhost:8000"

// ============ Session API ============

export interface SessionResponse {
  id: string
  user_id: string
  status: string
  started_at: string
  ended_at?: string
}

export async function createSession(userId: string, context?: string): Promise<SessionResponse> {
  const response = await fetch(`${API_BASE_URL}/session/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, context }),
  })

  if (!response.ok) {
    throw new Error(`Session creation failed: ${response.statusText}`)
  }

  return response.json()
}

export async function endSession(sessionId: string): Promise<{ status: string }> {
  const response = await fetch(`${API_BASE_URL}/session/end`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  })

  if (!response.ok) {
    throw new Error(`Session end failed: ${response.statusText}`)
  }

  return response.json()
}

export async function getCurrentSession(userId: string): Promise<SessionResponse | null> {
  const response = await fetch(`${API_BASE_URL}/session/current/${userId}`, {
    method: "GET",
  })

  if (response.status === 404) {
    return null
  }

  if (!response.ok) {
    throw new Error(`Get session failed: ${response.statusText}`)
  }

  return response.json()
}

// ============ Survey API ============

export interface SurveyQuestion {
  key: string
  question: string
  type: string
  emoji_options: string[]
}

export async function getSurveyQuestions(): Promise<SurveyQuestion[]> {
  const response = await fetch(`${API_BASE_URL}/survey/questions`, {
    method: "GET",
  })

  if (!response.ok) {
    throw new Error(`Get survey questions failed: ${response.statusText}`)
  }

  return response.json()
}

export async function submitSurveyResponse(
  sessionId: string,
  phase: "pre" | "post",
  questionKey: string,
  emojiValue: string
): Promise<{ status: string; response_id: string; score: number }> {
  const response = await fetch(`${API_BASE_URL}/survey/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      phase,
      question_key: questionKey,
      emoji_value: emojiValue,
    }),
  })

  if (!response.ok) {
    throw new Error(`Survey submission failed: ${response.statusText}`)
  }

  return response.json()
}

export async function getSurveyDelta(sessionId: string) {
  const response = await fetch(`${API_BASE_URL}/survey/delta/${sessionId}`, {
    method: "GET",
  })

  if (response.status === 404) {
    return null
  }

  if (!response.ok) {
    throw new Error(`Get survey delta failed: ${response.statusText}`)
  }

  return response.json()
}

export interface DailySummaryContent {
  id: string
  content_id: string
  content_title: string
  thumbnail_url?: string | null
  watched_at: string
  session_id?: string | null
}

export interface DailySummary {
  date: string
  timezone: string
  sessions: Array<{ id: string; started_at: string; ended_at?: string | null; status: string }>
  pre_mood_general: string | null
  post_mood_general: string | null
  improved: boolean | null
  delta_average: number | null
  contents: DailySummaryContent[]
  counseling_summary: string
}

export async function getDailySummary(
  userId: string,
  date: string,
  timezone: string = "Asia/Seoul"
): Promise<DailySummary> {
  const params = new URLSearchParams({ date, timezone })
  const response = await fetch(
    `${API_BASE_URL}/user/daily-summary/${userId}?${params.toString()}`,
    { method: "GET" }
  )

  if (!response.ok) {
    throw new Error(`Get daily summary failed: ${response.statusText}`)
  }

  return response.json()
}

// ============ Content API ============

export async function submitContentFeedback(
  userId: string,
  contentId: string,
  feedback: "like" | "dislike",
  sessionId?: string
): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/content/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      user_id: userId,
      content_id: contentId,
      feedback,
    }),
  })

  if (!response.ok) {
    throw new Error(`Content feedback failed: ${response.statusText}`)
  }

  return response.json()
}

export async function recordWatchedContent(
  userId: string,
  contentId: string,
  contentTitle: string,
  thumbnailUrl?: string,
  sessionId?: string,
  mediaProvider?: "youtube" | "spotify" | "podcast" | null,
  mediaUrl?: string | null
): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/content/watched`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: userId,
      session_id: sessionId,
      content_id: contentId,
      content_title: contentTitle,
      thumbnail_url: thumbnailUrl,
      ...(mediaProvider != null ? { media_provider: mediaProvider } : {}),
      ...(mediaUrl != null && mediaUrl !== "" ? { media_url: mediaUrl } : {}),
    }),
  })

  if (!response.ok) {
    throw new Error(`Record watched content failed: ${response.statusText}`)
  }

  return response.json()
}

export type ContentMediaPreferenceQuery = "all" | "youtube" | "spotify" | "podcast"

export async function getContentRecommendations(
  userId: string,
  options?: { limit?: number; media?: ContentMediaPreferenceQuery }
): Promise<any[]> {
  const limit = options?.limit ?? 8
  const media = options?.media ?? "all"
  const response = await fetch(
    `${API_BASE_URL}/content/recommendations/${userId}?limit=${limit}&media=${media}`,
    { method: "GET" }
  )

  if (!response.ok) {
    throw new Error(`Get content recommendations failed: ${response.statusText}`)
  }

  const data = await response.json()
  return data || []
}

export async function getContentHistory(userId: string, limit = 20): Promise<any[]> {
  const response = await fetch(`${API_BASE_URL}/content/history/${userId}?limit=${limit}`, {
    method: "GET",
  })

  if (!response.ok) {
    throw new Error(`Get content history failed: ${response.statusText}`)
  }

  const data = await response.json()
  return data || []
}

export async function getFeedbackSummary(userId: string): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/content/feedback/${userId}`, {
    method: "GET",
  })

  if (!response.ok) {
    throw new Error(`Get feedback summary failed: ${response.statusText}`)
  }

  return response.json()
}

// ============ Emotion API ============

export async function analyzeEmotion(userInput: string, context?: string): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/emotion/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_input: userInput,
      context,
    }),
  })

  if (!response.ok) {
    throw new Error(`Emotion analysis failed: ${response.statusText}`)
  }

  return response.json()
}

export async function getEmotionRecords(userId: string, days = 7): Promise<any[]> {
  const response = await fetch(`${API_BASE_URL}/emotion/records/${userId}?days=${days}`, {
    method: "GET",
  })

  if (!response.ok) {
    throw new Error(`Get emotion records failed: ${response.statusText}`)
  }

  const data = await response.json()
  return data || []
}

export async function getEmotionSummary(userId: string, days = 7): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/emotion/summary/${userId}?days=${days}`, {
    method: "GET",
  })

  if (!response.ok) {
    throw new Error(`Get emotion summary failed: ${response.statusText}`)
  }

  return response.json()
}

// ============ User API ============

export async function getUserProfile(userId: string): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/user/profile/${userId}`, {
    method: "GET",
  })

  if (!response.ok) {
    throw new Error(`Get user profile failed: ${response.statusText}`)
  }

  return response.json()
}

export async function upsertUserProfile(userId: string, displayName: string): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/user/profile`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: userId,
      display_name: displayName,
    }),
  })

  if (!response.ok) {
    throw new Error(`Upsert user profile failed: ${response.statusText}`)
  }

  return response.json()
}

export async function getUserSessions(userId: string, limit = 10): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/user/sessions/${userId}?limit=${limit}`, {
    method: "GET",
  })

  if (!response.ok) {
    throw new Error(`Get user sessions failed: ${response.statusText}`)
  }

  return response.json()
}

export async function getUserStats(userId: string): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/user/stats/${userId}`, {
    method: "GET",
  })

  if (!response.ok) {
    throw new Error(`Get user stats failed: ${response.statusText}`)
  }

  return response.json()
}

// ============ Counseling API ============

export async function sendCounselingMessage(userId: string, message: string, sessionId?: string): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/counseling/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: userId,
      message,
      session_id: sessionId,
    }),
  })

  if (!response.ok) {
    throw new Error(`Send counseling message failed: ${response.statusText}`)
  }

  return response.json()
}

export async function getInitialCounselingMessage(sessionId: string): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/counseling/initial-message/${sessionId}`, {
    method: "GET",
  })

  if (!response.ok) {
    throw new Error(`Get initial counseling message failed: ${response.statusText}`)
  }

  return response.json()
}

// ============ Reminder API ============

export interface ReminderPreferencePayload {
  user_id: string
  enabled: boolean
  reminder_time: string
  timezone: string
}

export async function getReminderPreference(userId: string): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/reminder/preferences/${userId}`, {
    method: "GET",
  })

  if (!response.ok) {
    throw new Error(`Get reminder preference failed: ${response.statusText}`)
  }

  return response.json()
}

export async function upsertReminderPreference(payload: ReminderPreferencePayload): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/reminder/preferences`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    throw new Error(`Upsert reminder preference failed: ${response.statusText}`)
  }

  return response.json()
}
