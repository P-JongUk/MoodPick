import {
  createSession,
  endSession,
  submitSurveyResponse,
  submitContentFeedback,
  recordWatchedContent,
} from "./api"

export type SurveyPhase = "pre" | "post"
export type ContentFeedbackType = "like" | "dislike"

const moodScoreMap: Record<string, number> = {
  great: 5,
  good: 4,
  neutral: 3,
  low: 2,
  bad: 1,
}

// Get userId from Supabase auth
async function getCurrentUserId() {
  // 이 함수는 프론트엔드에서 auth context에서 가져올 수 있음
  // 임시로 localStorage에서 가져오거나, useAuth hook 사용
  const stored = localStorage.getItem("__moodpick_user_id")
  if (stored) return stored
  
  // fallback: Supabase auth에서 가져오기
  const { getSupabaseClient } = await import("./supabaseClient")
  const supabase = getSupabaseClient()
  const { data, error } = await supabase.auth.getUser()
  
  if (error || !data.user) {
    throw new Error("User not authenticated")
  }
  
  return data.user.id
}

/**
 * 새 상담 세션 시작
 * @param context 상담 맥락 (선택사항)
 * @returns 세션 ID
 */
export async function startCounselingSession(context?: string): Promise<string> {
  const userId = await getCurrentUserId()
  
  const response = await createSession(userId, context)
  return response.id
}

/**
 * 상담 세션 종료
 * @param sessionId 종료할 세션 ID
 */
export async function endCounselingSession(sessionId: string): Promise<void> {
  await endSession(sessionId)
}

/**
 * 문진 응답 저장
 * @param sessionId 세션 ID
 * @param phase "pre" 또는 "post"
 * @param moodValue 감정 이모지 ("great", "good", "neutral", "low", "bad")
 */
export async function saveSurveyResponse(
  sessionId: string,
  phase: SurveyPhase,
  moodValue: string
): Promise<void> {
  // question_key는 임시로 "mood_general" 사용 (추후 다양한 문항 추가)
  const questionKey = "mood_general"
  
  await submitSurveyResponse(sessionId, phase, questionKey, moodValue)
}

/**
 * 콘텐츠 피드백 저장 및 시청 기록 기록
 * @param params 피드백 정보
 */
export async function saveContentFeedback(params: {
  sessionId: string
  feedback: ContentFeedbackType
  contentId: string
  contentTitle: string
  thumbnailUrl?: string
}): Promise<void> {
  const userId = await getCurrentUserId()

  // 1. 피드백 저장
  await submitContentFeedback(
    userId,
    params.contentId,
    params.feedback,
    params.sessionId
  )

  // 2. 시청 기록 저장
  await recordWatchedContent(
    userId,
    params.contentId,
    params.contentTitle,
    params.thumbnailUrl,
    params.sessionId
  )
}
