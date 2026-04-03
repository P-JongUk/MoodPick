import { getSupabaseClient } from "@/lib/supabaseClient"

export type SurveyPhase = "pre" | "post"
export type ContentFeedbackType = "like" | "dislike"

const moodScoreMap: Record<string, number> = {
  great: 5,
  good: 4,
  neutral: 3,
  low: 2,
  bad: 1,
}

async function getCurrentUserId() {
  const supabase = getSupabaseClient()
  const { data, error } = await supabase.auth.getUser()

  if (error) {
    throw error
  }

  return data.user?.id ?? null
}

export async function startCounselingSession() {
  const supabase = getSupabaseClient()
  const userId = await getCurrentUserId()

  if (!userId) {
    return null
  }

  const { data, error } = await supabase
    .from("counseling_sessions")
    .insert({
      user_id: userId,
      status: "active",
    })
    .select("id")
    .single()

  if (error) {
    throw error
  }

  return data.id as string
}

export async function endCounselingSession(sessionId: string) {
  const supabase = getSupabaseClient()

  const { error } = await supabase
    .from("counseling_sessions")
    .update({
      status: "ended",
      ended_at: new Date().toISOString(),
    })
    .eq("id", sessionId)

  if (error) {
    throw error
  }
}

export async function saveSurveyResponse(
  sessionId: string,
  phase: SurveyPhase,
  moodValue: string,
) {
  const supabase = getSupabaseClient()

  const { error } = await supabase.from("survey_responses").insert({
    session_id: sessionId,
    phase,
    question_key: "current_mood",
    emoji_value: moodValue,
    score: moodScoreMap[moodValue] ?? 0,
  })

  if (error) {
    throw error
  }
}

export async function saveContentFeedback(params: {
  sessionId: string
  feedback: ContentFeedbackType
  contentId: string
  contentTitle: string
}) {
  const supabase = getSupabaseClient()
  const userId = await getCurrentUserId()

  if (!userId) {
    return
  }

  const feedbackResult = await supabase.from("content_feedback").insert({
    session_id: params.sessionId,
    user_id: userId,
    content_id: params.contentId,
    feedback: params.feedback,
  })

  if (feedbackResult.error) {
    throw feedbackResult.error
  }

  const watchedResult = await supabase.from("watched_content_records").insert({
    user_id: userId,
    session_id: params.sessionId,
    content_id: params.contentId,
    content_title: params.contentTitle,
  })

  if (watchedResult.error) {
    throw watchedResult.error
  }
}
