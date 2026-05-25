"use client"

import { useEffect, useMemo, useRef, useState, memo, useCallback } from "react"
import { createPortal } from "react-dom"
import { useAuth } from "@/components/auth-provider"
import { getSupabaseClient } from "@/lib/supabaseClient"
import {
  endCounselingSession,
  saveContentFeedback,
  saveSurveyResponse,
  startCounselingSession,
} from "@/lib/sessionData"
import {
  endSession,
  getContentHistory,
  getCounselingHistory,
  cleanupStaleSessionsForUser,
  getCurrentSession,
  getDailySummary,
  getEmotionRecords,
  getEmotionSummary,
  getInitialCounselingMessage,
  getSurveyDelta,
  getUserSessions,
  getUserStats,
  getUserProfile,
  sendCounselingMessage,
  getReminderPreference,
  upsertReminderPreference,
  upsertUserProfile,
  type CounselorPersona,
  type DailySummary,
  type SessionResponse,
} from "@/lib/api"
import { cn } from "@/lib/utils"
import {
  resolvePlayback,
  youtubeEmbedUrl,
  youtubeThumbnailUrl,
} from "@/lib/contentPlayback"
import {
  Home,
  MessageCircle,
  Plus,
  BarChart3,
  Heart,
  Send,
  Play,
  Pause,
  Volume2,
  SkipForward,
  Flame,
  ChevronLeft,
  ChevronRight,
  User,
  LogOut,
  Trash2,
  Maximize2,
  Minimize2,
  X,
  Eye,
  EyeOff,
} from "lucide-react"
import { ChatMarkdown } from "@/components/chat-markdown"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogContent,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"

const REMINDER_FEATURE_ENABLED = process.env.NEXT_PUBLIC_REMINDER_ENABLED === "true"
const DEMO_HIDE_ONBOARDING = false

type TabType = "home" | "counseling" | "dashboard" | "mypage"

type SurveyType = "GAD" | "PHQ" | "PSS";

interface RecommendedContent {
  video_id?: string
  title?: string
  url?: string
  thumbnail?: string
  reason?: string
  search_query?: string
  candidate_pool?: Array<{
    video_id?: string
    title?: string
    thumbnail?: string
    url?: string
    media_provider?: string
    score?: number
  }>
}

interface Message {
  id: number
  sender: "user" | "ai"
  text: string
  timestamp: string
  recommendedContent?: RecommendedContent | null
}

interface SessionHistory {
  sessionId: string
  date: string
  timeLabel: string
  endTimeLabel: string | null
  durationLabel: string | null
  media: string
}

interface SurveyDeltaSummary {
  sessionId: string
  averageDelta: number
  improved: boolean
}

interface UserStats {
  total_sessions: number
  weekly_record_days?: number
  total_content_watched: number
  total_feedback: number
  likes: number
  dislikes: number
}

interface ContentHistoryItem {
  id: string
  content_id: string
  content_title: string
  thumbnail_url?: string | null
  media_provider?: "youtube" | "podcast" | null
  media_url?: string | null
  watched_at: string
  session_id?: string | null
}

interface EmotionRecordItem {
  question: string
  emoji: string
  score: number
  phase?: "pre" | "post"
  recorded_at: string
  session_id: string
}

interface EmotionSummary {
  average_score: number
  trend: "improving" | "declining" | "stable"
}

interface SurveyState  {
  scores: number[];
  isDone: boolean;
};

interface SurveyConfig  {
  title: string;
  description: string;
  questions: string[];
  scoreDescription: string;
  scoreOptions: number[];
};

const SURVEY_DEFAULT_SCORES: Record<SurveyType, number[]> = {
  GAD: [-1, -1, -1, -1, -1, -1, -1],
  PHQ: [-1, -1, -1, -1, -1, -1, -1, -1, -1],
  PSS: [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
}

function createSurveyState(type: SurveyType, isDone: boolean): SurveyState {
  return {
    scores: [...SURVEY_DEFAULT_SCORES[type]],
    isDone,
  }
}

const defaultContentItem: ContentHistoryItem = {
  id: "default-content",
  content_id: "youtube:jfKfPfyJRdk",
  content_title: "잠시 쉬어가는 음악 (데모)",
  thumbnail_url: "https://img.youtube.com/vi/jfKfPfyJRdk/mqdefault.jpg",
  media_provider: "youtube",
  watched_at: new Date().toISOString(),
}

function mapContentHistoryRow(row: Record<string, unknown>): ContentHistoryItem {
  return {
    id: String(row.id ?? ""),
    content_id: String(row.content_id ?? ""),
    content_title: String(row.content_title ?? ""),
    thumbnail_url: row.thumbnail_url != null ? String(row.thumbnail_url) : null,
    media_provider:
      row.media_provider === "youtube" || row.media_provider === "podcast"
        ? row.media_provider
        : null,
    media_url: row.media_url != null ? String(row.media_url) : null,
    watched_at: String(row.watched_at ?? new Date().toISOString()),
    session_id: row.session_id != null ? String(row.session_id) : null,
  }
}

const sessionContentFeedbackStorageKey = (sessionId: string) =>
  `moodpick:sessionContentFeedbackIds:${sessionId}`

function readSessionContentFeedbackIds(sessionId: string): Set<string> {
  if (typeof window === "undefined") return new Set()
  try {
    const raw = window.sessionStorage.getItem(sessionContentFeedbackStorageKey(sessionId))
    if (!raw) return new Set()
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return new Set()
    return new Set(parsed.filter((x): x is string => typeof x === "string" && x.trim().length > 0))
  } catch {
    return new Set()
  }
}

function persistSessionContentFeedbackIds(sessionId: string, ids: Set<string>): void {
  if (typeof window === "undefined") return
  try {
    window.sessionStorage.setItem(
      sessionContentFeedbackStorageKey(sessionId),
      JSON.stringify([...ids])
    )
  } catch {
    /* 저장 공간 부족·프라이빗 모드 등 */
  }
}

function addSessionContentFeedbackId(sessionId: string, contentId: string): void {
  const next = readSessionContentFeedbackIds(sessionId)
  next.add(contentId.trim())
  persistSessionContentFeedbackIds(sessionId, next)
}

function clearSessionContentFeedbackStorage(sessionId: string): void {
  if (typeof window === "undefined") return
  try {
    window.sessionStorage.removeItem(sessionContentFeedbackStorageKey(sessionId))
  } catch {
    /* noop */
  }
}

const scoreToEmoji = (score: number) => {
  if (score >= 4.5) return "😊"
  if (score >= 3.5) return "🙂"
  if (score >= 2.5) return "😐"
  if (score >= 1.5) return "😔"
  return "😢"
}

const scoreToLabel = (score: number) => {
  if (score >= 4.5) return "기쁨"
  if (score >= 3.5) return "평온"
  if (score >= 2.5) return "보통"
  if (score >= 1.5) return "지침"
  return "슬픔"
}

const scoreToCalendarColor = (score: number) => {
  if (score >= 4) return "bg-amber-200"
  if (score >= 3) return "bg-sky-200"
  return "bg-blue-200"
}

/** 사전/사후 문진 mood_general 값 — DB·API와 동일한 value 키 */
const SURVEY_MOOD_OPTIONS = [
  { emoji: "😊", label: "아주 좋아요", value: "great" },
  { emoji: "🙂", label: "괜찮아요", value: "good" },
  { emoji: "😐", label: "그저 그래요", value: "neutral" },
  { emoji: "😔", label: "조금 힘들어요", value: "low" },
  { emoji: "😢", label: "많이 힘들어요", value: "bad" },
] as const

/** 상담 탭에서 일정 시간 무응답 시 마무리 권유 배너 */
const COUNSELING_IDLE_PROMPT_MS = 15 * 60 * 1000

/** API 전송용 접미사 — 백엔드 `counseling.py`와 동일 문자열 */
const COUNSELING_USER_MARKDOWN_SUFFIX = "\n\n마크다운 형식으로 제공해."

function stripCounselingUserMarkdownSuffix(text: string): string {
  if (text.endsWith(COUNSELING_USER_MARKDOWN_SUFFIX)) {
    return text.slice(0, -COUNSELING_USER_MARKDOWN_SUFFIX.length)
  }
  return text
}

function formatHistoryMessageTime(iso: string | undefined): string {
  if (!iso) return ""
  try {
    return new Date(iso).toLocaleTimeString("ko-KR", {
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    })
  } catch {
    return ""
  }
}

function mapCounselingHistoryToMessages(
  rows: Array<{ role?: string; content?: string; created_at?: string }>
): Message[] {
  return rows.map((row, index) => {
    const sender: "user" | "ai" = row.role === "user" ? "user" : "ai"
    const raw = typeof row.content === "string" ? row.content : ""
    const text = sender === "user" ? stripCounselingUserMarkdownSuffix(raw) : raw
    return {
      id: index + 1,
      sender,
      text,
      timestamp: formatHistoryMessageTime(row.created_at),
    }
  })
}

function formatMoodGeneralForDisplay(value: string | null | undefined): string {
  if (value == null || String(value).trim() === "") return "—"
  const key = String(value).trim().toLowerCase()
  const found = SURVEY_MOOD_OPTIONS.find((o) => o.value === key)
  if (found) return `${found.emoji} ${found.label}`
  return String(value).trim()
}

const formatEmotionDayKey = (date: Date) => date.toLocaleDateString("en-CA")

const formatEmotionDayLabel = (date: Date) => `${date.getMonth() + 1}/${date.getDate()}`

function formatCounselingSessionDate(iso: string): string {
  return new Date(iso).toLocaleDateString("ko-KR", {
    year: "numeric",
    month: "long",
    day: "numeric",
  })
}

function formatCounselingSessionTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("ko-KR", {
    hour: "numeric",
    minute: "2-digit",
  })
}

function formatCounselingDurationLabel(
  startedAt: string,
  endedAt?: string | null
): string | null {
  if (!endedAt) return null
  const a = new Date(startedAt).getTime()
  const b = new Date(endedAt).getTime()
  if (!Number.isFinite(a) || !Number.isFinite(b) || b <= a) return null
  const mins = Math.round((b - a) / 60000)
  if (mins < 1) return "1분 미만"
  return `약 ${mins}분`
}

const getSidebarEncouragement = (
  isSessionActive: boolean,
  summary: EmotionSummary | null,
  delta: SurveyDeltaSummary | null
) => {
  if (isSessionActive) {
    return "지금 대화에 천천히 머물러도 괜찮아요."
  }
  if (delta?.improved) {
    return "방금의 작은 변화도 충분히 의미 있어요."
  }
  if (summary?.trend === "improving") {
    return "최근 마음의 흐름이 조금씩 좋아지고 있어요."
  }
  if (summary?.trend === "declining") {
    return "조금 무거운 날들도 혼자 버티지 않아도 괜찮아요."
  }
  if (summary && summary.average_score >= 4) {
    return "좋은 흐름을 오늘도 부드럽게 이어가봐요."
  }
  if (summary && summary.average_score <= 2.5) {
    return "오늘은 마음을 더 작고 다정하게 돌봐도 좋아요."
  }
  return "오늘도 당신의 마음을 응원합니다."
}

/** `<audio>` 시크 시 duration·seekable·UI 메타 길이를 맞춰 Range 미지원/지연 로드 케이스를 줄입니다. */
function podcastSeekUpperBound(el: HTMLMediaElement, uiDuration: number): number {
  try {
    if (el.seekable?.length) {
      const end = el.seekable.end(el.seekable.length - 1)
      if (Number.isFinite(end) && end > 0) return end
    }
  } catch {
    // seekable 접근 실패 무시
  }
  if (Number.isFinite(el.duration) && el.duration > 0) return el.duration
  if (Number.isFinite(uiDuration) && uiDuration > 0) return uiDuration
  return 0
}

function clampPodcastTargetTime(el: HTMLMediaElement, sec: number, uiDuration: number): number {
  const max = podcastSeekUpperBound(el, uiDuration)
  const t = Number.isFinite(sec) ? sec : 0
  if (max > 0) return Math.max(0, Math.min(max, t))
  return Math.max(0, t)
}

export function MoodPickDashboard() {
  const {
    user,
    isLoggedIn,
    isAuthLoading,
    authErrorMessage,
    setAuthErrorMessage,
    signUpWithPassword,
    signInWithPassword,
    signInWithOAuth,
    signOut,
  } = useAuth()
  const [hasCompletedOnboarding, setHasCompletedOnboarding] = useState(true)
  const [isOnboardingStateLoading, setIsOnboardingStateLoading] = useState(true)
  const [isSavingOnboarding, setIsSavingOnboarding] = useState(false)
  const [onboardingErrorMessage, setOnboardingErrorMessage] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<TabType>("home")
  const [messages, setMessages] = useState<Message[]>([])
  const [isPlaying, setIsPlaying] = useState(true)
  const [currentMonth, setCurrentMonth] = useState(new Date().getMonth() + 1)
  const [mediaFeedback, setMediaFeedback] = useState<"like" | "dislike" | null>(null)
  const [contentFeedbackSubmitting, setContentFeedbackSubmitting] = useState(false)
  /** 현재 상담 세션에서 이미 피드백을 보낸 content_id (sessionStorage와 동기화) */
  const [sessionContentFeedbackIds, setSessionContentFeedbackIds] = useState<string[]>([])

  // Session flow state
  const [isSessionActive, setIsSessionActive] = useState(false)
  const [showPreSurvey, setShowPreSurvey] = useState(false)
  const [showPostSurvey, setShowPostSurvey] = useState(false)
  const [showStartSessionPrompt, setShowStartSessionPrompt] = useState(false)
  const [preSurveyFromCounselingTabNav, setPreSurveyFromCounselingTabNav] = useState(false)
  const [preSurveyMood, setPreSurveyMood] = useState<string | null>(null)
  const [preSurveyPersona, setPreSurveyPersona] = useState<CounselorPersona | null>(null)
  const [postSurveyMood, setPostSurveyMood] = useState<string | null>(null)
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)
  const [syncWarningMessage, setSyncWarningMessage] = useState<string | null>(null)
  const [isSendingMessage, setIsSendingMessage] = useState(false)
  const [crisisModalText, setCrisisModalText] = useState<string | null>(null)
  const [lastSurveyDelta, setLastSurveyDelta] = useState<SurveyDeltaSummary | null>(null)
  const [dashboardRefreshKey, setDashboardRefreshKey] = useState(0)
  const [userStats, setUserStats] = useState<UserStats | null>(null)
  const [emotionSummary, setEmotionSummary] = useState<EmotionSummary | null>(null)
  const [emotionData, setEmotionData] = useState<{ date: string; score: number; label: string }[]>([])
  const [recentEmotionRecords, setRecentEmotionRecords] = useState<EmotionRecordItem[]>([])
  const [calendarMoods, setCalendarMoods] = useState<Record<number, { emoji: string; color: string }>>({})
  const [sessionHistory, setSessionHistory] = useState<SessionHistory[]>([])
  const [contentHistory, setContentHistory] = useState<ContentHistoryItem[]>([])
  const [currentContent, setCurrentContent] = useState<ContentHistoryItem>(defaultContentItem)
  const [recommendedQueue, setRecommendedQueue] = useState<ContentHistoryItem[]>([])
  const [topCandidates, setTopCandidates] = useState<ContentHistoryItem[]>([])

  // Login form state
  const [loginEmail, setLoginEmail] = useState("")
  const [signupDisplayName, setSignupDisplayName] = useState("")
  const [signupGender, setSignupGender] = useState("")
  const [signupBirthYear, setSignupBirthYear] = useState("")
  const [loginPassword, setLoginPassword] = useState("")
  const [authSuccessMessage, setAuthSuccessMessage] = useState<string | null>(null)

  // Onboarding state
  const [selectedConcerns, setSelectedConcerns] = useState<string[]>([])
  const [selectedCounselingTone, setSelectedCounselingTone] = useState<string[]>([])
  const [selectedContentPreference, setSelectedContentPreference] = useState<string[]>([])

  // My page settings state
  const [autoPlayEnabled, setAutoPlayEnabled] = useState(true)
  const [dailyReminderEnabled, setDailyReminderEnabled] = useState(true)
  const [dailyReminderTime, setDailyReminderTime] = useState("22:00")
  const [dailyReminderTimezone, setDailyReminderTimezone] = useState("Asia/Seoul")
  const [reminderSaveMessage, setReminderSaveMessage] = useState<string | null>(null)

  const [calendarYear, setCalendarYear] = useState(() => new Date().getFullYear())
  const [dayDetailOpen, setDayDetailOpen] = useState(false)
  const [dayDetailLoading, setDayDetailLoading] = useState(false)
  const [dayDetailError, setDayDetailError] = useState<string | null>(null)
  const [dayDetailData, setDayDetailData] = useState<DailySummary | null>(null)
  const [dayDetailIsoDate, setDayDetailIsoDate] = useState<string | null>(null)
  const [dashboardHistoryFullscreenOpen, setDashboardHistoryFullscreenOpen] = useState(false)

  const [profileSaveMessage, setProfileSaveMessage] = useState<string | null>(null)
  const [isSavingProfile, setIsSavingProfile] = useState(false)
  const [profileDisplayName, setProfileDisplayName] = useState<string | null>(null)
  const [mypagePrefsMessage, setMypagePrefsMessage] = useState<string | null>(null)
  const [isSavingMypagePrefs, setIsSavingMypagePrefs] = useState(false)
  const [isExportingMyData, setIsExportingMyData] = useState(false)
  const [exportMyDataMessage, setExportMyDataMessage] = useState<string | null>(null)
  const previousUserIdRef = useRef<string | null>(null)
  const lastCounselingActivityRef = useRef<number>(0)
  const counselingActiveSessionIdRef = useRef<string | null>(null)
  const lastResumePromptForSessionIdRef = useRef<string | null>(null)
  const skipResumeDismissMarkRef = useRef(false)
  const surveyOverlayBlocksInteractionRef = useRef(false)
  /** 정상 종료 직후 getCurrentSession 지연 등으로 이어가기 다이얼로그가 뜨는 것을 막음 (epoch ms) */
  const suppressResumeDialogUntilRef = useRef(0)
  const postSurveySubmittingRef = useRef(false)
  const [isPostSurveySubmitting, setIsPostSurveySubmitting] = useState(false)
  const [showResumeSessionDialog, setShowResumeSessionDialog] = useState(false)
  const [pendingResumeSession, setPendingResumeSession] = useState<SessionResponse | null>(null)
  const [showIdleWrapUpBanner, setShowIdleWrapUpBanner] = useState(false)
  const sidebarEncouragement = getSidebarEncouragement(
    isSessionActive,
    emotionSummary,
    lastSurveyDelta
  )

  const touchCounselingActivity = useCallback(() => {
    lastCounselingActivityRef.current = Date.now()
    setShowIdleWrapUpBanner(false)
  }, [])

  const resetCounselingState = () => {
    setDashboardHistoryFullscreenOpen(false)
    setActiveTab("home")
    setMessages([])
    setMediaFeedback(null)
    setContentFeedbackSubmitting(false)
    if (currentSessionId) {
      clearSessionContentFeedbackStorage(currentSessionId)
    }
    setSessionContentFeedbackIds([])
    setIsSessionActive(false)
    setShowPreSurvey(false)
    setShowPostSurvey(false)
    setShowStartSessionPrompt(false)
    setPreSurveyFromCounselingTabNav(false)
    setPreSurveyMood(null)
    setPreSurveyPersona(null)
    setPostSurveyMood(null)
    setCurrentSessionId(null)
    setSyncWarningMessage(null)
    setIsSendingMessage(false)
    setShowResumeSessionDialog(false)
    setPendingResumeSession(null)
    setShowIdleWrapUpBanner(false)
    lastCounselingActivityRef.current = 0
    counselingActiveSessionIdRef.current = null
    postSurveySubmittingRef.current = false
    setIsPostSurveySubmitting(false)
    suppressResumeDialogUntilRef.current = 0
  }

  useEffect(() => {
    const previousUserId = previousUserIdRef.current
    const currentUserId = user?.id ?? null

    if (previousUserId !== currentUserId) {
      resetCounselingState()
      previousUserIdRef.current = currentUserId
      lastResumePromptForSessionIdRef.current = null
    }
  }, [user?.id])

  useEffect(() => {
    setMediaFeedback(null)
  }, [currentContent.content_id])

  useEffect(() => {
    if (!currentSessionId) {
      setSessionContentFeedbackIds([])
      return
    }
    setSessionContentFeedbackIds([...readSessionContentFeedbackIds(currentSessionId)])
  }, [currentSessionId])

  const contentFeedbackComplete =
    Boolean(currentContent.content_id.trim()) &&
    sessionContentFeedbackIds.includes(currentContent.content_id.trim())

  useEffect(() => {
    if (activeTab !== "dashboard") {
      setDashboardHistoryFullscreenOpen(false)
    }
  }, [activeTab])

  useEffect(() => {
    if (!dashboardHistoryFullscreenOpen) return
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = "hidden"
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setDashboardHistoryFullscreenOpen(false)
    }
    window.addEventListener("keydown", onKey)
    return () => {
      document.body.style.overflow = prevOverflow
      window.removeEventListener("keydown", onKey)
    }
  }, [dashboardHistoryFullscreenOpen])

  useEffect(() => {
    counselingActiveSessionIdRef.current =
      isSessionActive && currentSessionId ? currentSessionId : null
  }, [isSessionActive, currentSessionId])

  useEffect(() => {
    surveyOverlayBlocksInteractionRef.current = showPreSurvey || showPostSurvey
  }, [showPreSurvey, showPostSurvey])

  useEffect(() => {
    if (!isSessionActive) {
      setShowIdleWrapUpBanner(false)
      return
    }
    const tick = () => {
      const last = lastCounselingActivityRef.current
      if (!last) return
      if (Date.now() - last >= COUNSELING_IDLE_PROMPT_MS) {
        setShowIdleWrapUpBanner(true)
      }
    }
    const id = window.setInterval(tick, 60_000)
    tick()
    return () => window.clearInterval(id)
  }, [isSessionActive])

  useEffect(() => {
    if (!user?.id || isAuthLoading || !isLoggedIn) return
    if (!hasCompletedOnboarding || isOnboardingStateLoading) return
    if (showPreSurvey || showPostSurvey) return

    let cancelled = false

    void (async () => {
      try {
        if (Date.now() < suppressResumeDialogUntilRef.current) return
        await cleanupStaleSessionsForUser(user.id)
        if (cancelled) return
        const cur = await getCurrentSession(user.id)
        if (cancelled || !cur?.id) return
        if (surveyOverlayBlocksInteractionRef.current) return
        if (lastResumePromptForSessionIdRef.current === cur.id) return
        if (counselingActiveSessionIdRef.current === cur.id) return
        setPendingResumeSession(cur)
        setShowResumeSessionDialog(true)
      } catch {
        /* 로그인 직후 백엔드 미기동 등은 무시 */
      }
    })()

    return () => {
      cancelled = true
    }
  }, [
    user?.id,
    isAuthLoading,
    isLoggedIn,
    hasCompletedOnboarding,
    isOnboardingStateLoading,
    showPreSurvey,
    showPostSurvey,
    isSessionActive,
    currentSessionId,
  ])

  useEffect(() => {
    if (!showPreSurvey && !showPostSurvey) return
    skipResumeDismissMarkRef.current = true
    setShowResumeSessionDialog(false)
    setPendingResumeSession(null)
  }, [showPreSurvey, showPostSurvey])

  //문진
  const [gad, setGad] = useState<SurveyState>(() => createSurveyState("GAD", false))
  const [phq, setPhq] = useState<SurveyState>(() => createSurveyState("PHQ", false))
  const [pss, setPss] = useState<SurveyState>(() => createSurveyState("PSS", false))
  const [isSavingSurvey, setIsSavingSurvey] = useState(false)
  const [surveyErrorMessage, setSurveyErrorMessage] = useState<string | null>(null)
  const [surveySave, setSurveySave]=useState(false)
  const [isSurveyStateLoading, setIsSurveyStateLoading] = useState(true)
  const surveyEnter = !gad.isDone || !phq.isDone || !pss.isDone
  const shouldShowSurvey = Boolean(user?.id) && !isSurveyStateLoading && !surveySave && surveyEnter

  const [readIntroduce, setReadIntroduce]=useState(false)
  const handleCheckIntroduce=()=>{setReadIntroduce(true)}

  useEffect(() => {
    if (!user?.id) {
      setGad(createSurveyState("GAD", true))
      setPhq(createSurveyState("PHQ", true))
      setPss(createSurveyState("PSS", true))
      setSurveySave(true)
      setIsSurveyStateLoading(false)
      return
    }

    setIsSurveyStateLoading(true)
    try {
      const metadata = (user.user_metadata ?? {}) as {
        survey_completed?: boolean
      }
      const completed = typeof metadata.survey_completed === "boolean" ? metadata.survey_completed : true
      setGad(createSurveyState("GAD", completed))
      setPhq(createSurveyState("PHQ", completed))
      setPss(createSurveyState("PSS", completed))
      setSurveySave(completed)
    } catch {
      setGad(createSurveyState("GAD", false))
      setPhq(createSurveyState("PHQ", false))
      setPss(createSurveyState("PSS", false))
      setSurveySave(false)
    } finally {
      setIsSurveyStateLoading(false)
    }
  }, [user])

  const handleSurveySave = async () => {
    if (!user?.id) return

    setIsSavingSurvey(true)
    setSurveyErrorMessage(null)

    try {
      const supabase = getSupabaseClient()
      const { error } = await supabase.auth.updateUser({
        data: {
          survey_completed: true,
        },
      })

      if (error) {
        throw error
      }

      setSurveySave(true)
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "설문 완료 저장 중 오류가 발생했습니다."
      setSurveyErrorMessage(message)
      throw error
    } finally {
      setIsSavingSurvey(false)
    }
  }

  useEffect(() => {
    const loadDashboardData = async () => {
      if (!user?.id) {
        setUserStats(null)
        setEmotionSummary(null)
        setEmotionData([])
        setRecentEmotionRecords([])
        setCalendarMoods({})
        setSessionHistory([])
        setContentHistory([])
        setCurrentContent(defaultContentItem)
        setRecommendedQueue([])
        setProfileDisplayName(null)
        return
      }

      try {
        const [
          statsResult,
          emotionRecordsResult,
          summaryResult,
          sessionsResult,
          contentsResult,
          profileResult,
        ] = await Promise.allSettled([
          getUserStats(user.id),
          getEmotionRecords(user.id, 30),
          getEmotionSummary(user.id, 7),
          getUserSessions(user.id, 10),
          getContentHistory(user.id, 20),
          getUserProfile(user.id),
        ])

        setUserStats(statsResult.status === "fulfilled" ? (statsResult.value as UserStats) : null)
        setEmotionSummary(
          summaryResult.status === "fulfilled" ? (summaryResult.value as EmotionSummary) : null
        )
        const userProfile =
          profileResult.status === "fulfilled"
            ? (profileResult.value as { name?: string | null; display_name?: string | null } | null)
            : null
        setProfileDisplayName(userProfile?.name ?? userProfile?.display_name ?? null)

        const emotionRecords =
          emotionRecordsResult.status === "fulfilled"
            ? ((emotionRecordsResult.value as EmotionRecordItem[]) ?? [])
            : []
        const validEmotionRecords = emotionRecords
          .filter((record) => record?.recorded_at && Number.isFinite(Number(record.score)))
          .sort(
            (a, b) =>
              new Date(b.recorded_at).getTime() - new Date(a.recorded_at).getTime()
          )
        const groupedByDay = new Map<string, { label: string; timestamp: number; scores: number[] }>()
        const latestMoodByDay = new Map<
          number,
          { recordedAt: number; mood: { emoji: string; color: string } }
        >()

        validEmotionRecords.forEach((record) => {
          const date = new Date(record.recorded_at)
          const dayKey = formatEmotionDayKey(date)
          const grouped = groupedByDay.get(dayKey) ?? {
            label: formatEmotionDayLabel(date),
            timestamp: date.getTime(),
            scores: [],
          }
          grouped.scores.push(record.score)
          grouped.timestamp = Math.min(grouped.timestamp, date.getTime())
          groupedByDay.set(dayKey, grouped)

          if (
            date.getFullYear() === calendarYear &&
            date.getMonth() + 1 === currentMonth &&
            record.question === "mood_general"
          ) {
            const day = date.getDate()
            const recordedAt = date.getTime()
            const existing = latestMoodByDay.get(day)
            if (!existing || recordedAt > existing.recordedAt) {
              latestMoodByDay.set(day, {
                recordedAt,
                mood: {
                  emoji: scoreToEmoji(record.score),
                  color: scoreToCalendarColor(record.score),
                },
              })
            }
          }
        })

        const emotionChartData = Array.from(groupedByDay.values())
          .map(({ label, timestamp, scores }) => {
            const avg = scores.reduce((sum, score) => sum + score, 0) / scores.length
            return {
              date: label,
              timestamp,
              score: Math.round((avg / 5) * 100),
              label: scoreToLabel(avg),
            }
          })
          .sort((a, b) => a.timestamp - b.timestamp)
          .map(({ date, score, label }) => ({ date, score, label }))

        setEmotionData(emotionChartData)
        setRecentEmotionRecords(validEmotionRecords.slice(0, 5))
        setCalendarMoods(
          Object.fromEntries(
            Array.from(latestMoodByDay.entries()).map(([day, value]) => [day, value.mood])
          )
        )

        const contentsRaw = contentsResult.status === "fulfilled" ? contentsResult.value : []
        const sessionsRaw = sessionsResult.status === "fulfilled" ? sessionsResult.value : null

        const contentItems = ((contentsRaw as unknown[]) ?? []).map((r) =>
          mapContentHistoryRow(r as Record<string, unknown>)
        )
        setContentHistory(contentItems)
        const first = contentItems[0] ?? defaultContentItem
        setCurrentContent(first)

        const contentBySession = new Map<string, string>()
        contentItems.forEach((content) => {
          if (content.session_id && !contentBySession.has(content.session_id)) {
            contentBySession.set(content.session_id, content.content_title)
          }
        })

        const sessionRows =
          (sessionsRaw?.sessions as Array<{
            id: string
            started_at: string
            ended_at?: string | null
          }>) || []
        const mappedSessionHistory = sessionRows.slice(0, 6).map((session) => {
          const endedRaw = session.ended_at?.trim()
          const endTimeLabel =
            endedRaw && endedRaw.length > 0
              ? formatCounselingSessionTime(endedRaw)
              : null
          return {
            sessionId: session.id,
            date: formatCounselingSessionDate(session.started_at),
            timeLabel: formatCounselingSessionTime(session.started_at),
            endTimeLabel,
            durationLabel: formatCounselingDurationLabel(
              session.started_at,
              session.ended_at
            ),
            media: contentBySession.get(session.id) ?? "추천 콘텐츠 기록 없음",
          }
        })

        setSessionHistory(mappedSessionHistory)
      } catch (error) {
        console.error("Failed to load dashboard data", error)
        setUserStats(null)
        setEmotionSummary(null)
        setEmotionData([])
        setRecentEmotionRecords([])
        setCalendarMoods({})
      }
    }

    void loadDashboardData()
  }, [currentMonth, calendarYear, user?.id, dashboardRefreshKey])

  useEffect(() => {
    const loadReminderPreference = async () => {
      if (!REMINDER_FEATURE_ENABLED) {
        setDailyReminderEnabled(false)
        setDailyReminderTime("22:00")
        setDailyReminderTimezone("Asia/Seoul")
        setReminderSaveMessage(null)
        return
      }

      if (!user?.id) {
        setDailyReminderEnabled(true)
        setDailyReminderTime("22:00")
        setDailyReminderTimezone("Asia/Seoul")
        return
      }

      try {
        const preference = await getReminderPreference(user.id)
        setDailyReminderEnabled(Boolean(preference.enabled))
        setDailyReminderTime(preference.reminder_time || "22:00")
        setDailyReminderTimezone(preference.timezone || "Asia/Seoul")
      } catch {
        setDailyReminderEnabled(true)
        setDailyReminderTime("22:00")
        setDailyReminderTimezone("Asia/Seoul")
      }
    }

    void loadReminderPreference()
  }, [user?.id])

  useEffect(() => {
    if (!user) {
      setHasCompletedOnboarding(true)
      setSelectedConcerns([])
      setSelectedCounselingTone([])
      setSelectedContentPreference([])
      setOnboardingErrorMessage(null)
      setIsOnboardingStateLoading(false)
      return
    }

    if (DEMO_HIDE_ONBOARDING) {
      setHasCompletedOnboarding(true)
      setOnboardingErrorMessage(null)
      setIsOnboardingStateLoading(false)
      return
    }

    const metadata = (user.user_metadata ?? {}) as {
      onboarding_completed?: boolean
      onboarding_profile?: {
        concerns?: string[]
        counseling_tone?: string[]
        content_preference?: string[]
      }
    }

    const completed = metadata.onboarding_completed
    // Backward compatibility: existing users without metadata skip onboarding.
    setHasCompletedOnboarding(typeof completed === "boolean" ? completed : true)

    const profile = metadata.onboarding_profile
    setSelectedConcerns(Array.isArray(profile?.concerns) ? profile.concerns : [])
    setSelectedCounselingTone(Array.isArray(profile?.counseling_tone) ? profile.counseling_tone : [])
    setSelectedContentPreference(Array.isArray(profile?.content_preference) ? profile.content_preference : [])
    setOnboardingErrorMessage(null)
    setIsOnboardingStateLoading(false)
  }, [user])

  useEffect(() => {
    if (!user) return
    const meta = user.user_metadata as {
      moodpick_preferences?: { autoplay_enabled?: boolean }
    }
    const prefs = meta.moodpick_preferences
    if (prefs && typeof prefs.autoplay_enabled === "boolean") {
      setAutoPlayEnabled(prefs.autoplay_enabled)
    }
  }, [user])

  const handleLogin = async () => {
    if (!loginEmail || !loginPassword) {
      setAuthErrorMessage("이메일과 비밀번호를 모두 입력해 주세요.")
      return
    }

    setAuthSuccessMessage(null)

    try {
      await signInWithPassword(loginEmail, loginPassword)
    } catch {
      return
    }
  }

  const handleSignUp = async () => {
    if (!loginEmail || !loginPassword) {
      setAuthErrorMessage("이메일과 비밀번호를 모두 입력해 주세요.")
      return
    }

    if (loginPassword.length < 6) {
      setAuthErrorMessage("비밀번호는 6자 이상이어야 합니다.")
      return
    }

    if (!signupDisplayName.trim()) {
      setAuthErrorMessage("서비스에서 불릴 이름을 입력해 주세요.")
      return
    }

    const normalizedBirthYear = signupBirthYear.trim()
    const parsedBirthYear = normalizedBirthYear ? Number(normalizedBirthYear) : null
    const currentYear = new Date().getFullYear()

    if (
      normalizedBirthYear &&
      parsedBirthYear !== null &&
      (!Number.isInteger(parsedBirthYear) || parsedBirthYear < 1900 || parsedBirthYear > currentYear)
    ) {
      setAuthErrorMessage("출생년도는 1900년부터 현재 연도 사이의 숫자로 입력해 주세요.")
      return
    }

    try {
      await signUpWithPassword(
        loginEmail,
        loginPassword,
        signupDisplayName.trim(),
        signupGender || null,
        parsedBirthYear
      )
      setAuthSuccessMessage("회원가입이 완료되었습니다. 이제 같은 계정으로 로그인해 주세요.")
      setAuthErrorMessage(null)
      setSignupDisplayName("")
      setSignupGender("")
      setSignupBirthYear("")
    } catch {
      return
    }
  }

  const handleCompleteOnboarding = () => {
    void completeOnboarding()
  }

  const completeOnboarding = async () => {
    if (!user) {
      setHasCompletedOnboarding(true)
      return
    }

    setIsSavingOnboarding(true)
    setOnboardingErrorMessage(null)

    try {
      const supabase = getSupabaseClient()
      const onboardingProfile = {
        concerns: selectedConcerns,
        counseling_tone: selectedCounselingTone,
        content_preference: selectedContentPreference,
        collected_at: new Date().toISOString(),
      }

      const { error } = await supabase.auth.updateUser({
        data: {
          onboarding_completed: true,
          onboarding_profile: onboardingProfile,
        },
      })

      if (error) {
        throw error
      }

      // AI 백엔드는 public.user_profiles.onboarding_profile을 읽으므로 여기에도 동기화.
      // 기존 패턴(/api/user/profile route, service_role)을 따라 client는 anon key로
      // user_profiles 테이블에 직접 접근하지 않는다. upsertUserProfile은 display_name을
      // 필수로 받으므로 metadata에서 꺼내 같이 보낸다(기존 행이 있으면 같은 값으로 덮어쓰여도 무해).
      const metadata = (user.user_metadata ?? {}) as { display_name?: string }
      const displayName =
        metadata.display_name?.trim() || user.email?.split("@")[0] || user.id
      await upsertUserProfile(user.id, displayName, undefined, undefined, onboardingProfile)

      setHasCompletedOnboarding(true)
    } catch (error) {
      const message = error instanceof Error ? error.message : "초기 정보 저장 중 오류가 발생했어요."
      setOnboardingErrorMessage(message)
    } finally {
      setIsSavingOnboarding(false)
    }
  }

  const handleLogout = async () => {
    await signOut()
    setLoginEmail("")
    setSignupDisplayName("")
    setSignupGender("")
    setSignupBirthYear("")
    setLoginPassword("")
    setAuthSuccessMessage(null)
    resetCounselingState()
  }

  const handleSocialLogin = async (provider: "google" | "kakao") => {
    try {
      await signInWithOAuth(provider)
      setAuthSuccessMessage(null)
    } catch {
      return
    }
  }

  const handleStartNewSession = () => {
    suppressResumeDialogUntilRef.current = 0
    setPreSurveyFromCounselingTabNav(false)
    setShowStartSessionPrompt(false)
    setSyncWarningMessage(null)
    setPreSurveyMood(null)
    setPreSurveyPersona(null)
    setShowPreSurvey(true)
  }

  const handleSelectNavTab = (itemId: TabType) => {
    if (itemId === "counseling" && !isSessionActive) {
      // 이미 사전 문진 중이면 무드 선택을 지우지 않음(같은 탭·네비 재클릭 시 상담 시작이 막히던 문제)
      if (showPreSurvey) {
        setActiveTab("counseling")
        return
      }
      setPreSurveyFromCounselingTabNav(true)
      setShowStartSessionPrompt(false)
      setSyncWarningMessage(null)
      setPreSurveyMood(null)
      setPreSurveyPersona(null)
      setShowPreSurvey(true)
      setActiveTab("counseling")
      return
    }
    setActiveTab(itemId)
  }

  const handlePreSurveyComplete = async () => {
    if (!preSurveyMood) {
      setSyncWarningMessage("사전 문진: 마음 온도를 먼저 선택해 주세요.")
      return
    }
    if (!preSurveyPersona) {
      setSyncWarningMessage("상담사 페르소나를 먼저 선택해 주세요.")
      return
    }

    let initialCounselingMessage = "안녕하세요, 저는 무드픽 상담사입니다. 오늘 하루 어떠셨나요? 편하게 이야기해 주세요."
    let createdSessionId: string | null = null

    try {
      if (user?.id) {
        const cur = await getCurrentSession(user.id)
        // 같은 날이라고 해서 기존 active를 두면 새 세션만 종료될 때 이전 세션이 orphan active로 남아
        // 재접속 시 이어가기 다이얼로그가 뜸. 사전 문진으로 새 상담을 시작할 때는 항상 정리합니다.
        if (cur?.id) {
          await endSession(cur.id)
          clearSessionContentFeedbackStorage(cur.id)
        }
      }

      createdSessionId = await startCounselingSession(undefined, preSurveyPersona)

      if (createdSessionId) {
        await saveSurveyResponse(createdSessionId, "pre", preSurveyMood)
        const initialResponse = await getInitialCounselingMessage(createdSessionId)
        if (initialResponse?.message) {
          initialCounselingMessage = initialResponse.message
        }
      }
    } catch {
      setSyncWarningMessage("세션 또는 사전 문진 저장에 실패했어요. 네트워크를 확인한 뒤 다시 시도해 주세요.")
    }

    if (!createdSessionId) {
      return
    }

    setCurrentSessionId(createdSessionId)
    setShowPreSurvey(false)
    setPreSurveyFromCounselingTabNav(false)
    suppressResumeDialogUntilRef.current = 0
    setIsSessionActive(true)
    setActiveTab("counseling")
    setMessages([
      {
        id: 1,
        sender: "ai",
        text: initialCounselingMessage,
        timestamp: new Date().toLocaleTimeString("ko-KR", {
          hour: "numeric",
          minute: "2-digit",
          hour12: true,
        }),
      },
    ])
    touchCounselingActivity()
  }

  const handleEndSession = () => {
    setDashboardHistoryFullscreenOpen(false)
    setDayDetailOpen(false)
    setPostSurveyMood(null)
    skipResumeDismissMarkRef.current = true
    setShowResumeSessionDialog(false)
    setPendingResumeSession(null)
    setShowPostSurvey(true)
  }

  const handlePostSurveyComplete = async () => {
    if (!postSurveyMood) {
      setSyncWarningMessage("사후 문진: 마음 온도를 먼저 선택해 주세요.")
      return
    }
    if (postSurveySubmittingRef.current) return
    postSurveySubmittingRef.current = true
    setIsPostSurveySubmitting(true)

    const endedSessionId = currentSessionId
    let shouldRefreshDashboard = false

    try {
      if (currentSessionId) {
        const sid = currentSessionId
        try {
          await saveSurveyResponse(sid, "post", postSurveyMood)
          await endCounselingSession(sid)
          clearSessionContentFeedbackStorage(sid)
          shouldRefreshDashboard = true
          suppressResumeDialogUntilRef.current = Date.now() + 25_000
        } catch {
          setSyncWarningMessage(
            "사후 문진 또는 세션 종료 저장에 실패했어요. Supabase 설정 후 다시 확인해 주세요."
          )
          return
        }

        try {
          const deltaResponse = await getSurveyDelta(sid)
          if (deltaResponse?.delta && typeof deltaResponse.delta === "object") {
            const values = Object.values(deltaResponse.delta) as number[]
            const averageDelta = values.length
              ? values.reduce((sum, value) => sum + value, 0) / values.length
              : 0

            setLastSurveyDelta({
              sessionId: sid,
              averageDelta,
              improved: Boolean(deltaResponse.improved),
            })
          }
        } catch {
          /* 세션은 이미 종료됨 — 델타만 생략 */
        }
      }

      if (endedSessionId) {
        lastResumePromptForSessionIdRef.current = endedSessionId
      }

      setShowPostSurvey(false)
      setIsSessionActive(false)
      setCurrentSessionId(null)
      setPostSurveyMood(null)
      setPreSurveyMood(null)
      setPreSurveyPersona(null)
      setMediaFeedback(null)
      if (shouldRefreshDashboard) {
        setDashboardRefreshKey((value) => value + 1)
      }
      setActiveTab(endedSessionId ? "dashboard" : "home")
    } finally {
      postSurveySubmittingRef.current = false
      setIsPostSurveySubmitting(false)
    }
  }

  const closeResumeDialog = (dismissSessionId: string | null) => {
    if (dismissSessionId) {
      lastResumePromptForSessionIdRef.current = dismissSessionId
    }
    setShowResumeSessionDialog(false)
    setPendingResumeSession(null)
  }

  const handleResumeDialogOpenChange = (open: boolean) => {
    if (open) return
    if (!skipResumeDismissMarkRef.current) {
      const sid = pendingResumeSession?.id ?? null
      closeResumeDialog(sid)
    }
    skipResumeDismissMarkRef.current = false
  }

  const handleResumeSessionConfirm = async () => {
    if (!user?.id || !pendingResumeSession?.id) return
    const sid = pendingResumeSession.id
    skipResumeDismissMarkRef.current = true
    lastResumePromptForSessionIdRef.current = null
    suppressResumeDialogUntilRef.current = 0
    setShowResumeSessionDialog(false)
    setPendingResumeSession(null)
    try {
      const history = await getCounselingHistory(user.id, sid)
      let restored = mapCounselingHistoryToMessages(history.messages ?? [])
      if (restored.length === 0) {
        const initialResponse = await getInitialCounselingMessage(sid)
        const text =
          initialResponse?.message ??
          "안녕하세요, 저는 무드픽 상담사입니다. 오늘 하루 어떠셨나요? 편하게 이야기해 주세요."
        restored = [
          {
            id: 1,
            sender: "ai",
            text,
            timestamp: new Date().toLocaleTimeString("ko-KR", {
              hour: "numeric",
              minute: "2-digit",
              hour12: true,
            }),
          },
        ]
      }
      setCurrentSessionId(sid)
      setIsSessionActive(true)
      setMessages(restored)
      setActiveTab("counseling")
      touchCounselingActivity()
    } catch {
      setSyncWarningMessage("상담 기록을 불러오지 못했어요. 새 상담을 시작해 주세요.")
    }
  }

  const handleResumeSessionNewStart = async () => {
    if (!pendingResumeSession?.id) return
    const sid = pendingResumeSession.id
    skipResumeDismissMarkRef.current = true
    lastResumePromptForSessionIdRef.current = null
    suppressResumeDialogUntilRef.current = 0
    setShowResumeSessionDialog(false)
    setPendingResumeSession(null)
    try {
      await endSession(sid)
      clearSessionContentFeedbackStorage(sid)
    } catch {
      setSyncWarningMessage("이전 세션을 정리하지 못했어요. 잠시 후 다시 시도해 주세요.")
    }
    handleStartNewSession()
  }

  const handleMediaFeedbackChange = async (feedback: "like" | "dislike") => {
    const cid = currentContent.content_id.trim()
    if (!cid || contentFeedbackSubmitting) return
    const alreadySubmitted =
      sessionContentFeedbackIds.includes(cid) ||
      Boolean(currentSessionId && readSessionContentFeedbackIds(currentSessionId).has(cid))
    if (alreadySubmitted) return

    setContentFeedbackSubmitting(true)
    setMediaFeedback(feedback)

    try {
      if (currentSessionId) {
        await saveContentFeedback({
          sessionId: currentSessionId,
          feedback,
          contentId: currentContent.content_id,
          contentTitle: currentContent.content_title,
          thumbnailUrl: currentContent.thumbnail_url ?? undefined,
          mediaProvider: currentContent.media_provider ?? undefined,
          mediaUrl: currentContent.media_url ?? undefined,
        })
        addSessionContentFeedbackId(currentSessionId, cid)
      }
      setSessionContentFeedbackIds((prev) => (prev.includes(cid) ? prev : [...prev, cid]))
    } catch {
      setSyncWarningMessage("콘텐츠 피드백 저장에 실패했어요. Supabase 설정을 확인해 주세요.")
      setMediaFeedback(null)
    } finally {
      setContentFeedbackSubmitting(false)
    }
  }

  const handleSendMessage = (messageText: string): boolean => {
    const trimmedMessage = messageText.trim()
    if (!trimmedMessage || isSendingMessage) return false
    if (!user?.id) {
      setSyncWarningMessage("로그인 후 상담 메시지를 보낼 수 있어요.")
      return false
    }
    if (!isSessionActive || !currentSessionId) {
      setSyncWarningMessage(null)
      setShowStartSessionPrompt(true)
      return false
    }

    const newMessage: Message = {
      id: Date.now(),
      sender: "user",
      text: trimmedMessage,
      timestamp: new Date().toLocaleTimeString("ko-KR", {
        hour: "numeric",
        minute: "2-digit",
        hour12: true,
      }),
    }

    setMessages((prev) => [...prev, newMessage])
    setIsSendingMessage(true)
    touchCounselingActivity()

    void (async () => {
      try {
        const response = await sendCounselingMessage(
          user.id,
          trimmedMessage + COUNSELING_USER_MARKDOWN_SUFFIX,
          currentSessionId
        )

        if (response?.is_crisis) {
          setCrisisModalText(response.message ?? "")
          setSyncWarningMessage(null)
          return
        }

        const recommended = response?.recommended_content ?? null
        const aiResponse: Message = {
          id: Date.now() + 1,
          sender: "ai",
          text:
            response?.message ??
            "메시지를 받았어요. 현재는 AI 연동 전 단계라 기본 상담 응답으로 안내해드리고 있어요.",
          timestamp: new Date().toLocaleTimeString("ko-KR", {
            hour: "numeric",
            minute: "2-digit",
            hour12: true,
          }),
          recommendedContent: recommended,
        }

        setMessages((prev) => [...prev, aiResponse])

        touchCounselingActivity()

        if (response?.fallback) {
          setSyncWarningMessage("AI 응답이 일시적으로 불안정해 기본 상담 응답으로 안내했어요.")
        } else if (recommended && !recommended.video_id) {
          setSyncWarningMessage("추천 영상을 불러오지 못했어요. 상담은 계속 이용할 수 있고, 잠시 후 다시 요청해 주세요.")
        } else {
          setSyncWarningMessage(null)
        }

        if (recommended?.video_id) {
          const contentId = recommended.video_id.toString()
          const isPodcast = contentId.toLowerCase().startsWith("podcast:")
          const nowIso = new Date().toISOString()

          const mainItem: ContentHistoryItem = {
            id: contentId,
            content_id: contentId,
            content_title: recommended.title ?? "추천 콘텐츠",
            thumbnail_url: recommended.thumbnail,
            media_provider: isPodcast ? "podcast" : "youtube",
            media_url: isPodcast ? (recommended.url ?? null) : null,
            watched_at: nowIso,
            session_id: currentSessionId,
          }

          const pool = recommended.candidate_pool ?? []
          const poolItems: ContentHistoryItem[] = pool
            .filter((c) => c.video_id)
            .map((c) => {
              const id = String(c.video_id)
              const itemIsPodcast = id.toLowerCase().startsWith("podcast:")
              const provider: "youtube" | "podcast" =
                c.media_provider === "podcast" || c.media_provider === "youtube"
                  ? c.media_provider
                  : itemIsPodcast
                    ? "podcast"
                    : "youtube"
              return {
                id,
                content_id: id,
                content_title: c.title ?? "추천 콘텐츠",
                thumbnail_url: c.thumbnail ?? null,
                media_provider: provider,
                media_url: itemIsPodcast ? (c.url ?? null) : null,
                watched_at: nowIso,
                session_id: currentSessionId,
              }
            })

          // top-4 풀: 메인을 맨 앞으로 두고 풀에서 메인 중복 제거. candidate_pool에
          // 메인이 빠져 있더라도 안전하도록 mainItem을 명시적으로 선두에 둠.
          const dedupedPool = poolItems.filter((c) => c.content_id !== contentId)
          const top4 = [mainItem, ...dedupedPool].slice(0, 4)

          setTopCandidates(top4)
          setCurrentContent(mainItem)
          setRecommendedQueue(top4.filter((c) => c.content_id !== contentId).slice(0, 3))
          setIsPlaying(true)
        }
      } catch (error) {
        const errorMessage =
          error instanceof Error && error.message
            ? error.message
            : "상담 메시지 전송에 실패했어요. 잠시 후 다시 시도해 주세요."
        setSyncWarningMessage(errorMessage)

        const fallbackResponse: Message = {
          id: Date.now() + 1,
          sender: "ai",
          text: errorMessage,
          timestamp: new Date().toLocaleTimeString("ko-KR", {
            hour: "numeric",
            minute: "2-digit",
            hour12: true,
          }),
        }
        setMessages((prev) => [...prev, fallbackResponse])
      } finally {
        setIsSendingMessage(false)
      }
    })()

    return true
  }

  const handleSaveDisplayName = async (name: string): Promise<boolean> => {
    if (!user?.id) return false
    const trimmed = name.trim()
    if (!trimmed) {
      setProfileSaveMessage("이름을 입력해 주세요.")
      return false
    }
    setIsSavingProfile(true)
    setProfileSaveMessage(null)
    try {
      await upsertUserProfile(user.id, trimmed)
      const supabase = getSupabaseClient()
      const { error } = await supabase.auth.updateUser({
        data: { display_name: trimmed },
      })
      if (error) {
        console.warn("Failed to sync auth metadata display name:", error)
      }
      setProfileDisplayName(trimmed)
      setProfileSaveMessage("이름이 저장되었습니다.")
      return true
    } catch (e) {
      setProfileSaveMessage(e instanceof Error ? e.message : "저장에 실패했습니다.")
      return false
    } finally {
      setIsSavingProfile(false)
    }
  }

  const handleSaveMypagePreferences = async () => {
    if (!user?.id) return
    setIsSavingMypagePrefs(true)
    setMypagePrefsMessage(null)
    try {
      const supabase = getSupabaseClient()
      const { error } = await supabase.auth.updateUser({
        data: {
          moodpick_preferences: {
            autoplay_enabled: autoPlayEnabled,
          },
        },
      })
      if (error) throw error
      setMypagePrefsMessage("맞춤 설정이 계정에 저장되었습니다.")
    } catch (e) {
      setMypagePrefsMessage(e instanceof Error ? e.message : "저장에 실패했습니다.")
    } finally {
      setIsSavingMypagePrefs(false)
    }
  }

  const handleExportMyData = async () => {
    if (!user?.id) return
    setIsExportingMyData(true)
    setExportMyDataMessage(null)
    try {
      const [stats, contents, emotions] = await Promise.all([
        getUserStats(user.id),
        getContentHistory(user.id, 100),
        getEmotionRecords(user.id, 365),
      ])
      const payload = {
        exported_at: new Date().toISOString(),
        user_id: user.id,
        stats,
        content_history: contents,
        emotion_records: emotions,
      }
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" })
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `moodpick-export-${user.id.slice(0, 8)}.json`
      a.click()
      URL.revokeObjectURL(url)
      setExportMyDataMessage("JSON 파일로 내보냈습니다.")
    } catch (e) {
      console.error(e)
      setExportMyDataMessage(
        e instanceof Error ? e.message : "내보내기에 실패했습니다. 잠시 후 다시 시도해 주세요."
      )
    } finally {
      setIsExportingMyData(false)
    }
  }

  const handleCalendarDayClick = async (day: number) => {
    if (!user?.id || !day) return
    const iso = `${calendarYear}-${String(currentMonth).padStart(2, "0")}-${String(day).padStart(2, "0")}`
    setDayDetailOpen(true)
    setDayDetailLoading(true)
    setDayDetailError(null)
    setDayDetailData(null)
    setDayDetailIsoDate(iso)
    try {
      const data = await getDailySummary(user.id, iso, dailyReminderTimezone)
      setDayDetailData(data)
    } catch (e) {
      setDayDetailError(e instanceof Error ? e.message : "불러오기에 실패했습니다.")
    } finally {
      setDayDetailLoading(false)
    }
  }

  const handleSelectRecommendedFromQueue = (item: ContentHistoryItem) => {
    setCurrentContent(item)
    setIsPlaying(true)
    setRecommendedQueue(
      topCandidates.filter((c) => c.content_id !== item.content_id).slice(0, 3)
    )
  }

  const handlePlayContentFromHistory = (item: ContentHistoryItem) => {
    const playback = resolvePlayback({
      content_id: item.content_id,
      media_provider: item.media_provider,
      media_url: item.media_url,
    })
    if (playback.kind === "none") {
      const url = item.media_url?.trim()
      if (url && /^https?:\/\//i.test(url)) {
        window.open(url, "_blank", "noopener,noreferrer")
        return
      }
      setCurrentContent(item)
      setIsPlaying(true)
      setSyncWarningMessage("이 콘텐츠는 앱에서 바로 재생할 수 없습니다.")
      setDashboardHistoryFullscreenOpen(true)
      return
    }
    setSyncWarningMessage(null)
    setCurrentContent(item)
    setIsPlaying(true)
    setDashboardHistoryFullscreenOpen(true)
  }

  const handleSaveReminderPreference = async () => {
    if (!REMINDER_FEATURE_ENABLED) return
    if (!user?.id) return

    setReminderSaveMessage(null)

    try {
      await upsertReminderPreference({
        user_id: user.id,
        enabled: dailyReminderEnabled,
        reminder_time: dailyReminderTime,
        timezone: dailyReminderTimezone,
      })
      setReminderSaveMessage("매일 알림 설정이 저장되었습니다.")
    } catch {
      setReminderSaveMessage("알림 설정 저장에 실패했습니다. 잠시 후 다시 시도해 주세요.")
    }
  }

  const getDaysInMonth = () => {
    const days: (number | null)[] = []
    const daysInMonth = new Date(calendarYear, currentMonth, 0).getDate()
    const firstDay = new Date(calendarYear, currentMonth - 1, 1).getDay()

    for (let i = 0; i < firstDay; i++) {
      days.push(null)
    }

    for (let i = 1; i <= daysInMonth; i++) {
      days.push(i)
    }

    return days
  }

  const goCalendarPrev = () => {
    if (currentMonth <= 1) {
      setCurrentMonth(12)
      setCalendarYear((y) => y - 1)
    } else {
      setCurrentMonth((m) => m - 1)
    }
  }

  const goCalendarNext = () => {
    if (currentMonth >= 12) {
      setCurrentMonth(1)
      setCalendarYear((y) => y + 1)
    } else {
      setCurrentMonth((m) => m + 1)
    }
  }

  const navItems = [
    { id: "home" as TabType, label: "홈", icon: Home },
    { id: "counseling" as TabType, label: "AI 심리 상담", icon: MessageCircle },
    { id: "dashboard" as TabType, label: "나의 감정 기록", icon: BarChart3 },
    { id: "mypage" as TabType, label: "마이페이지", icon: User },
  ]

  if (isAuthLoading && !isLoggedIn) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background text-muted-foreground">
        <div className="text-center space-y-3">
          <div className="mx-auto h-10 w-10 animate-pulse rounded-full bg-primary/20" />
          <p className="text-sm">로그인 상태를 확인하는 중입니다...</p>
        </div>
      </div>
    )
  }

  // Show login screen if not logged in
  if (!isLoggedIn) {
    return (
      <LoginScreen
        email={loginEmail}
        setEmail={setLoginEmail}
        displayName={signupDisplayName}
        setDisplayName={setSignupDisplayName}
        gender={signupGender}
        setGender={setSignupGender}
        birthYear={signupBirthYear}
        setBirthYear={setSignupBirthYear}
        password={loginPassword}
        setPassword={setLoginPassword}
        onLogin={handleLogin}
        onSignUp={handleSignUp}
        onSocialLogin={handleSocialLogin}
        isAuthLoading={isAuthLoading}
        authErrorMessage={authErrorMessage}
        authSuccessMessage={authSuccessMessage}
        clearAuthSuccessMessage={() => setAuthSuccessMessage(null)}
      />
    )
  }

  if (isOnboardingStateLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background text-muted-foreground">
        <div className="text-center space-y-3">
          <div className="mx-auto h-10 w-10 animate-pulse rounded-full bg-primary/20" />
          <p className="text-sm">초기 설정 상태를 확인하는 중입니다...</p>
        </div>
      </div>
    )
  }

  // Show onboarding if first time after login
  if (!DEMO_HIDE_ONBOARDING && !hasCompletedOnboarding) {
    return (
      <OnboardingScreen
        selectedConcerns={selectedConcerns}
        setSelectedConcerns={setSelectedConcerns}
        selectedCounselingTone={selectedCounselingTone}
        setSelectedCounselingTone={setSelectedCounselingTone}
        selectedContentPreference={selectedContentPreference}
        setSelectedContentPreference={setSelectedContentPreference}
        onComplete={handleCompleteOnboarding}
        isSaving={isSavingOnboarding}
        errorMessage={onboardingErrorMessage}
        activeTab={activeTab}
      />
    )
  }

  if (shouldShowSurvey) {
    return (
      <SurveyScreen
        gad={gad}
        setGad={setGad}
        phq={phq}
        setPhq={setPhq}
        pss={pss}
        setPss={setPss}
        onComplete={handleSurveySave}
        isSaving={isSavingSurvey}
        errorMessage={surveyErrorMessage}
      />
    )
  }

  if (!readIntroduce) {
    return (
      <Introduce introduceCheck={handleCheckIntroduce}/>
    )
  }  

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <aside className="w-64 bg-sidebar border-r border-sidebar-border flex flex-col">
        <div className="p-6 border-b border-sidebar-border">
          <button
            type="button"
            onClick={() => setActiveTab("home")}
            className="flex w-full items-center gap-3 rounded-xl text-left transition-colors hover:bg-sidebar-accent/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label="홈으로 이동"
          >
            <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center">
              <Heart className="w-5 h-5 text-primary-foreground" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-sidebar-foreground">무드픽</h1>
              <p className="text-xs text-muted-foreground">MoodPick</p>
            </div>
          </button>
        </div>

        <nav className="flex-1 p-4">
          <ul className="space-y-2">
            {navItems.map((item) => (
              <li key={item.id}>
                <button
                  onClick={() => handleSelectNavTab(item.id)}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-left transition-all duration-200 ${
                    activeTab === item.id
                      ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  }`}
                >
                  <item.icon className="w-5 h-5" />
                  <span>{item.label}</span>
                </button>
              </li>
            ))}
          </ul>
        </nav>

        <div className="p-4 border-t border-sidebar-border">
          <Card className="bg-secondary/50 border-0 shadow-none">
            <CardContent className="p-4">
              <p className="text-sm text-muted-foreground leading-relaxed">
                {sidebarEncouragement}
              </p>
            </CardContent>
          </Card>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 min-w-0 overflow-auto">
        {activeTab === "home" && (
          <HomeView
            onStartNewSession={handleStartNewSession}
            userStats={userStats}
            emotionSummary={emotionSummary}
            currentContent={currentContent}
            onPlayRecommended={() => {
              setIsPlaying(true)
              setActiveTab("counseling")
            }}
            flowMessage={syncWarningMessage}
          />
        )}
        <Dialog open={showStartSessionPrompt} onOpenChange={setShowStartSessionPrompt}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>상담을 시작할까요?</DialogTitle>
              <DialogDescription>
                메시지를 보내기 전에 짧은 사전 문진을 먼저 완료해 주세요.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button
                type="button"
                variant="secondary"
                onClick={() => setShowStartSessionPrompt(false)}
              >
                닫기
              </Button>
              <Button type="button" onClick={handleStartNewSession}>
                상담 시작하기
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        <Dialog open={showResumeSessionDialog} onOpenChange={handleResumeDialogOpenChange}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>진행 중인 상담이 있어요</DialogTitle>
              <DialogDescription>
                이전에 시작한 상담을 이어서 진행할까요, 아니면 새로 시작할까요?
              </DialogDescription>
            </DialogHeader>
            <DialogFooter className="flex-col gap-2 sm:flex-col">
              <Button type="button" className="w-full rounded-xl" onClick={() => void handleResumeSessionConfirm()}>
                이전 상담 이어하기
              </Button>
              <Button
                type="button"
                variant="secondary"
                className="w-full rounded-xl"
                onClick={() => void handleResumeSessionNewStart()}
              >
                새로 시작하기
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        {activeTab === "counseling" && (
          <CounselingView
            messages={messages}
            onSendMessage={handleSendMessage}
            isSendingMessage={isSendingMessage}
            isPlaying={isPlaying}
            setIsPlaying={setIsPlaying}
            autoPlayEnabled={autoPlayEnabled}
            contentFeedbackSubmitting={contentFeedbackSubmitting}
            contentFeedbackComplete={contentFeedbackComplete}
            mediaFeedback={mediaFeedback}
            onMediaFeedbackChange={handleMediaFeedbackChange}
            onEndSession={handleEndSession}
            onStartNewSession={handleStartNewSession}
            isSessionActive={isSessionActive}
            syncWarningMessage={syncWarningMessage}
            currentContent={currentContent}
            recommendedQueue={recommendedQueue}
            onSelectRecommendedContent={handleSelectRecommendedFromQueue}
            idleWrapUpBanner={showIdleWrapUpBanner}
            onDismissIdleWrapUp={() => setShowIdleWrapUpBanner(false)}
            onRequestEndFromIdle={handleEndSession}
          />
        )}
        {activeTab === "dashboard" && (
          <DashboardView
            calendarYear={calendarYear}
            currentMonth={currentMonth}
            goCalendarPrev={goCalendarPrev}
            goCalendarNext={goCalendarNext}
            getDaysInMonth={getDaysInMonth}
            calendarMoods={calendarMoods}
            emotionData={emotionData}
            recentEmotionRecords={recentEmotionRecords}
            sessionHistory={sessionHistory}
            contentHistory={contentHistory}
            lastSurveyDelta={lastSurveyDelta}
            userStats={userStats}
            onCalendarDayClick={handleCalendarDayClick}
            onPlayContentHistory={handlePlayContentFromHistory}
          />
        )}
        {activeTab === "mypage" && (
          <MyPageView
            autoPlayEnabled={autoPlayEnabled}
            setAutoPlayEnabled={setAutoPlayEnabled}
            onLogout={handleLogout}
            userEmail={user?.email ?? "-"}
            displayName={profileDisplayName ?? (user?.user_metadata?.display_name as string | undefined) ?? null}
            onSaveDisplayName={handleSaveDisplayName}
            profileSaveMessage={profileSaveMessage}
            isSavingProfile={isSavingProfile}
            onSaveMypagePreferences={handleSaveMypagePreferences}
            mypagePrefsMessage={mypagePrefsMessage}
            isSavingMypagePrefs={isSavingMypagePrefs}
            userCreatedAt={user?.created_at ?? null}
            totalSessions={userStats?.total_sessions ?? 0}
            dailyReminderEnabled={dailyReminderEnabled}
            setDailyReminderEnabled={setDailyReminderEnabled}
            dailyReminderTime={dailyReminderTime}
            setDailyReminderTime={setDailyReminderTime}
            dailyReminderTimezone={dailyReminderTimezone}
            setDailyReminderTimezone={setDailyReminderTimezone}
            onSaveReminderPreference={handleSaveReminderPreference}
            reminderSaveMessage={reminderSaveMessage}
            onExportMyData={handleExportMyData}
            isExportingMyData={isExportingMyData}
            exportMyDataMessage={exportMyDataMessage}
            setHasCompletedOnboarding={setHasCompletedOnboarding}
            setSurveySave={setSurveySave}
            surveyEnter={surveyEnter}
          />
        )}
      </main>

      {showPreSurvey &&
        typeof document !== "undefined" &&
        createPortal(
          <PreSurveyOverlay
            selectedMood={preSurveyMood}
            setSelectedMood={setPreSurveyMood}
            selectedPersona={preSurveyPersona}
            setSelectedPersona={setPreSurveyPersona}
            onStart={handlePreSurveyComplete}
            showCounselingTabGateHint={preSurveyFromCounselingTabNav}
            onClose={() => {
              setShowPreSurvey(false)
              setPreSurveyPersona(null)
              if (preSurveyFromCounselingTabNav) {
                setActiveTab("home")
              }
              setPreSurveyFromCounselingTabNav(false)
            }}
          />,
          document.body
        )}
      {showPostSurvey &&
        typeof document !== "undefined" &&
        createPortal(
          <PostSurveyOverlay
            selectedMood={postSurveyMood}
            setSelectedMood={setPostSurveyMood}
            isSubmitting={isPostSurveySubmitting}
            onComplete={handlePostSurveyComplete}
          />,
          document.body
        )}

      {dashboardHistoryFullscreenOpen && (
        <div
          className="fixed inset-0 z-[100] flex flex-col bg-background p-4 sm:p-6 overflow-y-auto"
          role="dialog"
          aria-modal="true"
          aria-label="저장된 콘텐츠 전체 화면"
        >
          <ContentMediaPanel
            variant="fullscreen"
            currentContent={currentContent}
            recommendedQueue={[]}
            isPlaying={isPlaying}
            setIsPlaying={setIsPlaying}
            autoPlayEnabled={autoPlayEnabled}
            contentFeedbackSubmitting={contentFeedbackSubmitting}
            contentFeedbackComplete={contentFeedbackComplete}
            mediaFeedback={mediaFeedback}
            onMediaFeedbackChange={handleMediaFeedbackChange}
            syncWarningMessage={syncWarningMessage}
            onSelectRecommendedContent={setCurrentContent}
            onExitFullscreen={() => setDashboardHistoryFullscreenOpen(false)}
          />
        </div>
      )}

      <AlertDialog
        open={crisisModalText !== null}
        onOpenChange={(open) => {
          if (!open) setCrisisModalText(null)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>잠시 멈추고 이 메시지를 읽어 주세요</AlertDialogTitle>
          </AlertDialogHeader>
          <div className="py-2">
            <ChatMarkdown source={crisisModalText ?? ""} />
          </div>
          <div className="aspect-video w-full overflow-hidden rounded-lg">
            <iframe
              src="https://www.youtube-nocookie.com/embed/CPYLnJFrqlw?autoplay=1&mute=1&playsinline=1"
              title="자살예방 안내 영상"
              allow="autoplay; accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
              className="h-full w-full"
            />
          </div>
          <AlertDialogFooter>
            <AlertDialogAction onClick={() => setCrisisModalText(null)}>
              알겠어요
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Dialog open={dayDetailOpen} onOpenChange={setDayDetailOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>하루 기록</DialogTitle>
            <DialogDescription>
              {dayDetailIsoDate ? `${dayDetailIsoDate} · ${dailyReminderTimezone}` : ""}
            </DialogDescription>
          </DialogHeader>
          {dayDetailLoading && <p className="text-sm text-muted-foreground">불러오는 중…</p>}
          {dayDetailError && <p className="text-sm text-destructive">{dayDetailError}</p>}
          {dayDetailData && !dayDetailLoading && (
            <div className="space-y-3 text-sm">
              <div>
                <p className="font-medium text-foreground">요약</p>
                <p className="text-muted-foreground whitespace-pre-wrap leading-relaxed">
                  {dayDetailData.counseling_summary}
                </p>
              </div>
              <div className="flex flex-wrap gap-2 text-xs">
                <span className="rounded-full bg-muted px-2 py-1">
                  사전: {formatMoodGeneralForDisplay(dayDetailData.pre_mood_general)}
                </span>
                <span className="rounded-full bg-muted px-2 py-1">
                  사후: {formatMoodGeneralForDisplay(dayDetailData.post_mood_general)}
                </span>
                {dayDetailData.delta_average != null && (
                  <span className="rounded-full bg-muted px-2 py-1">
                    평균 델타: {dayDetailData.delta_average >= 0 ? "+" : ""}
                    {dayDetailData.delta_average.toFixed(2)}
                  </span>
                )}
              </div>
              {dayDetailData.contents.length > 0 && (
                <div>
                  <p className="font-medium text-foreground mb-1">콘텐츠</p>
                  <ul className="list-disc pl-4 text-muted-foreground space-y-1">
                    {dayDetailData.contents.map((c) => (
                      <li key={c.id}>{c.content_title}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button type="button" variant="secondary" onClick={() => setDayDetailOpen(false)}>
              닫기
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function HomeView({
  onStartNewSession,
  userStats,
  emotionSummary,
  currentContent,
  onPlayRecommended,
  flowMessage,
}: {
  onStartNewSession: () => void
  userStats: UserStats | null
  emotionSummary: EmotionSummary | null
  currentContent: ContentHistoryItem
  onPlayRecommended: () => void
  flowMessage: string | null
}) {
  const weeklyMoodEmoji = scoreToEmoji(emotionSummary?.average_score ?? 3)
  const homePlayback = resolvePlayback({
    content_id: currentContent.content_id,
    media_provider: currentContent.media_provider,
    media_url: currentContent.media_url,
  })
  const homeThumbUrl =
    currentContent.thumbnail_url?.trim() ||
    (homePlayback.kind === "youtube" && homePlayback.youtubeVideoId
      ? youtubeThumbnailUrl(homePlayback.youtubeVideoId)
      : null)

  return (
    <div className="p-8 max-w-4xl mx-auto">
      {/* Greeting Section */}
      <div className="mb-10">
        <h2 className="text-3xl font-bold text-foreground mb-3 text-balance">
          오늘 하루, 당신의 마음은 어떤 색인가요?
        </h2>
        {flowMessage && (
          <p className="mt-3 text-sm text-destructive bg-destructive/10 rounded-xl px-4 py-2">{flowMessage}</p>
        )}
      </div>

      {/* Start New Session Button */}
      <div className="mb-10">
        <Button
          onClick={onStartNewSession}
          size="lg"
          className="w-full h-14 rounded-2xl text-lg font-semibold shadow-lg"
        >
          <MessageCircle className="w-5 h-5 mr-3" />
          새로운 상담 시작하기
        </Button>
      </div>

      {/* Today's Care */}
      <Card className="overflow-hidden shadow-lg border-0 bg-card py-0 gap-0">
        <CardHeader className="bg-primary/5 border-b border-border p-6">
          <CardTitle className="text-lg flex items-center gap-2 text-foreground">
            <Heart className="w-5 h-5 text-primary" />
            오늘의 맞춤 위로 콘텐츠
          </CardTitle>
        </CardHeader>
        <CardContent className="p-6">
          <div className="flex gap-6">
            <div className="w-48 h-32 rounded-xl bg-muted flex items-center justify-center overflow-hidden shrink-0">
              {homeThumbUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={homeThumbUrl} alt="" className="w-full h-full object-cover" />
              ) : (
                <div className="text-center">
                  <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-2">
                    <Play className="w-6 h-6 text-primary" />
                  </div>
                  <p className="text-xs text-muted-foreground">썸네일</p>
                </div>
              )}
            </div>
            <div className="flex-1 flex flex-col justify-between">
              <div>
                <h3 className="font-semibold text-lg mb-2 text-foreground">
                  {currentContent.content_title}
                </h3>
                <p className="text-muted-foreground text-sm leading-relaxed">
                  최근 시청한 콘텐츠를 기준으로 위로 콘텐츠를 우선 노출하고 있어요.
                  상담 중 반응 데이터를 바탕으로 추천 정밀도를 점진적으로 높입니다.
                </p>
              </div>
              <Button className="w-fit mt-4 rounded-xl" type="button" onClick={onPlayRecommended}>
                <Play className="w-4 h-4 mr-2" />
                바로 재생하기
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Quick Stats */}
      <div className="grid grid-cols-3 gap-4 mt-8">
        <Card className="border-0 bg-secondary/50">
          <CardContent className="p-6 text-center">
            <p className="text-3xl font-bold text-primary mb-1">{userStats?.weekly_record_days ?? 0}</p>
            <p className="text-sm text-muted-foreground">이번 주 기록일</p>
          </CardContent>
        </Card>
        <Card className="border-0 bg-secondary/50">
          <CardContent className="p-6 text-center">
            <p className="text-3xl font-bold text-primary mb-1">{userStats?.total_sessions ?? 0}</p>
            <p className="text-sm text-muted-foreground">총 상담 횟수</p>
          </CardContent>
        </Card>
        <Card className="border-0 bg-secondary/50">
          <CardContent className="p-6 text-center">
            <p className="text-3xl font-bold text-primary mb-1">{weeklyMoodEmoji}</p>
            <p className="text-sm text-muted-foreground">주간 평균 기분</p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

const ContentMediaPanel = memo(function ContentMediaPanel({
  variant,
  currentContent,
  recommendedQueue,
  isPlaying,
  setIsPlaying,
  autoPlayEnabled,
  contentFeedbackSubmitting = false,
  contentFeedbackComplete = false,
  mediaFeedback,
  onMediaFeedbackChange,
  syncWarningMessage,
  onSelectRecommendedContent,
  onRequestFullscreen,
  onExitFullscreen,
}: {
  variant: "sidebar" | "fullscreen"
  currentContent: ContentHistoryItem
  recommendedQueue: ContentHistoryItem[]
  isPlaying: boolean
  setIsPlaying: (value: boolean) => void
  autoPlayEnabled: boolean
  contentFeedbackSubmitting?: boolean
  contentFeedbackComplete?: boolean
  mediaFeedback: "like" | "dislike" | null
  onMediaFeedbackChange: (value: "like" | "dislike") => void
  syncWarningMessage: string | null
  onSelectRecommendedContent: (value: ContentHistoryItem) => void
  onRequestFullscreen?: () => void
  onExitFullscreen?: () => void
}) {
  const isFullscreen = variant === "fullscreen"
  const playback = resolvePlayback({
    content_id: currentContent.content_id,
    media_provider: currentContent.media_provider,
    media_url: currentContent.media_url,
  })
  const hasPlayableContent = Boolean(currentContent.content_id.trim())
  const isEmbed = playback.kind === "youtube"
  const feedbackDisabled =
    !hasPlayableContent || contentFeedbackSubmitting || contentFeedbackComplete

  // Podcast 전용 오디오 상태/컨트롤
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const [podcastPlaying, setPodcastPlaying] = useState(false)
  const [podcastCurrentTime, setPodcastCurrentTime] = useState(0)
  const [podcastDuration, setPodcastDuration] = useState(0)
  const [podcastRate, setPodcastRate] = useState(1)

  useEffect(() => {
    if (playback.kind !== "podcast") return

    setPodcastPlaying(false)
    setPodcastCurrentTime(0)
    setPodcastDuration(0)

    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.currentTime = 0
      audioRef.current.playbackRate = podcastRate
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentContent.content_id, playback.kind])

  useEffect(() => {
    if (playback.kind !== "podcast") return
    if (!audioRef.current) return
    audioRef.current.playbackRate = podcastRate
  }, [podcastRate, playback.kind])

  useEffect(() => {
    if (playback.kind !== "podcast" || !autoPlayEnabled) return
    const el = audioRef.current
    if (!el) return
    const tryPlay = () => {
      void el.play().catch(() => {})
    }
    if (el.readyState >= HTMLMediaElement.HAVE_FUTURE_DATA) {
      tryPlay()
      return
    }
    el.addEventListener("canplay", tryPlay, { once: true })
    return () => el.removeEventListener("canplay", tryPlay)
  }, [currentContent.content_id, playback.kind, autoPlayEnabled])

  useEffect(() => {
    if (playback.kind !== "youtube" || !playback.youtubeVideoId) return

    function handleYouTubeMessage(event: MessageEvent) {
      if (
        event.origin !== "https://www.youtube-nocookie.com" &&
        event.origin !== "https://www.youtube.com"
      ) return

      let data: { event?: string; info?: number }
      try {
        data = typeof event.data === "string" ? JSON.parse(event.data) : event.data
      } catch {
        return
      }

      // 100 = 영상 없음(삭제), 101/150 = Content ID 또는 소유자 차단
      if (data.event === "onError" && [100, 101, 150].includes(data.info ?? -1)) {
        const next = recommendedQueue[0]
        if (next) onSelectRecommendedContent(next)
      }
    }

    window.addEventListener("message", handleYouTubeMessage)
    return () => window.removeEventListener("message", handleYouTubeMessage)
  }, [playback.kind, playback.youtubeVideoId, recommendedQueue, onSelectRecommendedContent])

  const formatPodcastTime = (sec: number) => {
    const s = Number.isFinite(sec) ? sec : 0
    const m = Math.floor(s / 60)
    const r = Math.floor(s % 60)
    return `${m}:${String(r).padStart(2, "0")}`
  }

  const togglePodcast = async () => {
    const el = audioRef.current
    if (!el) return
    try {
      if (el.paused) {
        await el.play()
      } else {
        el.pause()
      }
    } catch {
      // Autoplay 정책/네트워크 문제 등으로 play 실패 시 무시
    }
  }

  const skipPodcast = (deltaSeconds: number) => {
    const el = audioRef.current
    if (!el) return
    const max = podcastSeekUpperBound(el, podcastDuration)
    const nextRaw = el.currentTime + deltaSeconds
    const next = max > 0 ? Math.max(0, Math.min(max, nextRaw)) : Math.max(0, nextRaw)
    const wasPlaying = !el.paused
    el.currentTime = next
    setPodcastCurrentTime(next)
    if (wasPlaying) void el.play().catch(() => {})
  }

  const applyPodcastRate = (rate: number) => {
    setPodcastRate(rate)
    if (audioRef.current) {
      audioRef.current.playbackRate = rate
    }
  }

  const seekPodcast = (sec: number) => {
    const el = audioRef.current
    if (!el) return
    const wasPlaying = !el.paused
    const next = clampPodcastTargetTime(el, sec, podcastDuration)
    el.currentTime = next
    setPodcastCurrentTime(next)
    if (wasPlaying) void el.play().catch(() => {})
  }

  return (
    <div className={cn("flex flex-col min-h-0", isFullscreen && "flex-1")}>
      {isFullscreen && (
        <div className="flex items-start justify-between gap-3 mb-4 shrink-0">
          <div>
            <h3 className="text-xl font-semibold text-foreground">자동 추천 콘텐츠</h3>
            <p className="text-sm text-muted-foreground">대화 내용을 바탕으로 AI가 추천해 드려요</p>
          </div>
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="shrink-0 rounded-xl"
            onClick={onExitFullscreen}
            aria-label="전체 화면 닫기"
          >
            <Minimize2 className="w-4 h-4" />
          </Button>
        </div>
      )}

      {!isFullscreen && (
        <div className="mb-6">
          <h3 className="text-lg font-semibold text-foreground mb-1">자동 추천 콘텐츠</h3>
          <p className="text-sm text-muted-foreground">대화 내용을 바탕으로 AI가 추천해 드려요</p>
        </div>
      )}

      {hasPlayableContent &&
        playback.kind === "youtube" &&
        playback.youtubeVideoId &&
        autoPlayEnabled && (
          <div
            className="mb-3 flex shrink-0 gap-2 rounded-xl border border-border bg-muted/60 px-3 py-2.5 text-sm text-foreground/90"
            role="note"
          >
            <Volume2 className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
            <p className="leading-snug">
              유튜브는 브라우저 정책상 자동 재생 시 처음에 음소거됩니다. 플레이어 안의 음소거를 해제하면 소리가 납니다.
            </p>
          </div>
        )}

      <Card
        className={cn(
          "overflow-hidden border-0 shadow-lg shrink-0",
          isFullscreen && "max-w-5xl w-full mx-auto"
        )}
      >
        <div
          className={cn(
            "bg-foreground/90 relative flex overflow-hidden",
            !isEmbed &&
              playback.kind !== "podcast" &&
              "aspect-video items-center justify-center",
            playback.kind === "podcast" &&
              "min-h-[260px] h-[min(56vh,380px)] max-h-[420px] w-full max-w-[min(100%,22rem)] mx-auto flex-col sm:min-h-[280px] sm:h-[min(52vh,400px)] sm:max-w-[24rem]",
            isEmbed && playback.kind === "youtube" && "aspect-video items-center justify-center",
            isFullscreen && playback.kind === "youtube" && "max-h-[min(52vh,560px)] w-full",
            isFullscreen && playback.kind === "podcast" && "max-h-[min(70vh,520px)] flex-1 min-h-0"
          )}
        >
          {onRequestFullscreen && (
            <button
              type="button"
              className="absolute top-2 right-2 z-10 p-2 rounded-lg bg-foreground/30 hover:bg-foreground/50 transition-colors"
              onClick={onRequestFullscreen}
              aria-label="콘텐츠 전체 화면"
            >
              <Maximize2 className="w-4 h-4 text-primary-foreground" />
            </button>
          )}
          {hasPlayableContent && playback.kind === "youtube" && playback.youtubeVideoId && (
            <iframe
              key={`yt-${playback.youtubeVideoId}-${autoPlayEnabled ? "ap" : "noap"}`}
              title={currentContent.content_title}
              className="absolute inset-0 h-full w-full border-0"
              src={youtubeEmbedUrl(playback.youtubeVideoId, { autoplay: autoPlayEnabled })}
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
              allowFullScreen
            />
          )}
          {hasPlayableContent && playback.kind === "podcast" && playback.podcastAudioUrl && (
            <>
              <div
                className="absolute inset-0 bg-center bg-cover opacity-35 blur-2xl scale-110"
                style={{
                  backgroundImage: currentContent.thumbnail_url ? `url(${currentContent.thumbnail_url})` : undefined,
                }}
              />
              <div className="absolute inset-0 bg-gradient-to-b from-black/25 via-black/55 to-black/80" />

              {/* 턴테이블: 상단 flex 영역만 사용 → 프레임 안에 원 전체가 들어감 */}
              <div className="relative z-[1] flex min-h-0 flex-1 items-center justify-center px-4 pt-4 pb-2">
                <div className="relative aspect-square w-[min(72%,17.5rem)] max-h-full shrink-0 sm:w-[min(70%,18rem)]">
                  <div className="absolute inset-0 rounded-full bg-black/70 shadow-2xl" />
                  <div className="absolute inset-[10%] rounded-full bg-neutral-900/90" />
                  <div
                    className={cn("absolute inset-[18%] rounded-full bg-center bg-cover animate-spin")}
                    style={{
                      animationDuration: "14s",
                      backgroundImage: currentContent.thumbnail_url ? `url(${currentContent.thumbnail_url})` : undefined,
                    }}
                  />
                  <div className="absolute left-1/2 top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-neutral-200/80 sm:h-3 sm:w-3" />
                </div>
              </div>

              <audio
                ref={audioRef}
                src={playback.podcastAudioUrl}
                preload="auto"
                onLoadedMetadata={() => {
                  const el = audioRef.current
                  if (!el) return
                  const upper = podcastSeekUpperBound(el, 0)
                  const d =
                    Number.isFinite(el.duration) && el.duration > 0 ? el.duration : upper
                  setPodcastDuration(d)
                  setPodcastCurrentTime(Number.isFinite(el.currentTime) ? el.currentTime : 0)
                }}
                onDurationChange={() => {
                  const el = audioRef.current
                  if (!el) return
                  setPodcastDuration((prev) => {
                    const upper = podcastSeekUpperBound(el, prev)
                    const d =
                      Number.isFinite(el.duration) && el.duration > 0 ? el.duration : upper
                    return d > 0 ? Math.max(prev, d) : prev
                  })
                }}
                onProgress={() => {
                  const el = audioRef.current
                  if (!el) return
                  setPodcastDuration((prev) => {
                    const upper = podcastSeekUpperBound(el, prev)
                    return upper > prev ? upper : prev
                  })
                }}
                onTimeUpdate={() => {
                  const el = audioRef.current
                  if (!el) return
                  setPodcastCurrentTime(Number.isFinite(el.currentTime) ? el.currentTime : 0)
                }}
                onSeeked={() => {
                  const el = audioRef.current
                  if (!el) return
                  setPodcastCurrentTime(Number.isFinite(el.currentTime) ? el.currentTime : 0)
                }}
                onPlay={() => setPodcastPlaying(true)}
                onPause={() => setPodcastPlaying(false)}
                onEnded={() => setPodcastPlaying(false)}
              />

              <div className="relative z-[2] mt-auto flex shrink-0 justify-center px-3 pb-3 pt-1 sm:px-4 sm:pb-4">
                <div className="w-full max-w-[17.5rem] sm:max-w-xs rounded-lg overflow-hidden border border-white/15 bg-black/50 backdrop-blur-md shadow-lg">
                  <div className="px-2.5 pt-1.5 pb-1.5 sm:px-3 sm:pb-2">
                    <div className="flex items-center justify-between gap-1 mb-1.5">
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="h-9 w-9 rounded-full text-primary-foreground hover:bg-white/10 shrink-0"
                        onClick={() => skipPodcast(-15)}
                        aria-label="15초 뒤로"
                      >
                        <ChevronLeft className="w-4 h-4" />
                      </Button>

                      <Button
                        type="button"
                        onClick={() => void togglePodcast()}
                        size="icon"
                        className="h-10 w-10 rounded-full bg-primary hover:bg-primary/90 text-primary-foreground shrink-0"
                        aria-label={podcastPlaying ? "일시정지" : "재생"}
                      >
                        {podcastPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 ml-0.5" />}
                      </Button>

                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="h-9 w-9 rounded-full text-primary-foreground hover:bg-white/10 shrink-0"
                        onClick={() => skipPodcast(15)}
                        aria-label="15초 앞으로"
                      >
                        <SkipForward className="w-4 h-4" />
                      </Button>
                    </div>

                    <input
                      type="range"
                      min={0}
                      max={podcastDuration || 0}
                      step={0.1}
                      value={Math.min(podcastCurrentTime, podcastDuration || 0)}
                      onChange={(e) => seekPodcast(Number(e.target.value))}
                      disabled={podcastDuration <= 0}
                      className="w-full h-1.5 accent-primary"
                    />

                    <div className="flex items-center justify-between gap-2 mt-0.5">
                      <span className="text-[10px] tabular-nums text-white/70">
                        {formatPodcastTime(podcastCurrentTime)}
                      </span>
                      <div className="flex items-center gap-1">
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          onClick={() => applyPodcastRate(0.75)}
                          className={cn(
                            "h-6 min-w-0 rounded-full px-2 text-[10px] py-0",
                            podcastRate === 0.75 && "bg-primary text-primary-foreground"
                          )}
                        >
                          0.75
                        </Button>
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          onClick={() => applyPodcastRate(1)}
                          className={cn(
                            "h-6 min-w-0 rounded-full px-2 text-[10px] py-0",
                            podcastRate === 1 && "bg-primary text-primary-foreground"
                          )}
                        >
                          1×
                        </Button>
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          onClick={() => applyPodcastRate(1.25)}
                          className={cn(
                            "h-6 min-w-0 rounded-full px-2 text-[10px] py-0",
                            podcastRate === 1.25 && "bg-primary text-primary-foreground"
                          )}
                        >
                          1.25
                        </Button>
                      </div>
                      <span className="text-[10px] tabular-nums text-white/70">
                        {formatPodcastTime(podcastDuration)}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}
          {hasPlayableContent && playback.kind === "none" && (
            <>
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="text-center text-primary-foreground">
                  <Flame className={cn("mx-auto mb-2 opacity-80", isFullscreen ? "w-24 h-24" : "w-16 h-16")} />
                  <p className="text-sm opacity-70">영상 재생 중...</p>
                </div>
              </div>
              {!isPlaying && (
                <div className="absolute inset-0 bg-foreground/50 flex items-center justify-center z-[1]">
                  <Play className={cn("text-primary-foreground", isFullscreen ? "w-20 h-20" : "w-16 h-16")} />
                </div>
              )}
            </>
          )}
        </div>
        <CardContent className={cn("p-4", isFullscreen && "sm:p-6")}>
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <span className="px-2 py-1 bg-primary/10 text-primary text-xs rounded-full font-medium">
              {playback.kind === "youtube"
                ? "YouTube"
                : playback.kind === "podcast"
                  ? "Podcast"
                  : "재생 중"}
            </span>
          </div>
          <h4 className="font-medium text-foreground mb-2 text-balance">{currentContent.content_title}</h4>
          <p className="text-sm text-muted-foreground mb-4">
            최근 사용자 반응 기반으로 우선 노출된 콘텐츠입니다.
          </p>

          {playback.kind === "podcast" ? (
            <p className="text-xs text-muted-foreground mb-4">
              팟캐스트 오디오 컨트롤은 위 플레이어에서 조작할 수 있어요.
            </p>
          ) : isEmbed ? (
            <p className="text-xs text-muted-foreground mb-4">
              재생·일시정지·볼륨은 위 플레이어에서 조작할 수 있어요.
            </p>
          ) : (
            <>
              <div className="mb-4">
                <div className="h-1 bg-muted rounded-full overflow-hidden">
                  <div className="h-full w-1/3 bg-primary rounded-full" />
                </div>
                <div className="flex justify-between text-xs text-muted-foreground mt-1">
                  <span>12:34</span>
                  <span>45:00</span>
                </div>
              </div>

              <div className="flex items-center justify-center gap-4">
                <Button variant="ghost" size="icon" className="rounded-full">
                  <Volume2 className="w-5 h-5" />
                </Button>
                <Button onClick={() => setIsPlaying(!isPlaying)} size="icon" className="w-12 h-12 rounded-full">
                  {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
                </Button>
                <Button variant="ghost" size="icon" className="rounded-full">
                  <SkipForward className="w-5 h-5" />
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {hasPlayableContent && (
        <div className={cn("mt-4 p-4 rounded-xl bg-secondary/30 shrink-0", isFullscreen && "max-w-5xl w-full mx-auto")}>
          <p className="text-sm text-center text-muted-foreground mb-3">
            {contentFeedbackComplete
              ? "의견을 반영했어요. 재생은 그대로 이어져요."
              : "이 콘텐츠가 도움이 되었나요?"}
          </p>
          <div className="flex items-center justify-center gap-6 sm:gap-10">
            <div className="flex flex-col items-center gap-1.5">
              <button
                type="button"
                disabled={feedbackDisabled}
                onClick={() => onMediaFeedbackChange("like")}
                className={cn(
                  "flex h-14 w-14 sm:h-16 sm:w-16 items-center justify-center rounded-2xl border-2 text-3xl sm:text-4xl transition-all",
                  feedbackDisabled && "opacity-50 cursor-not-allowed",
                  mediaFeedback === "like"
                    ? "border-primary bg-primary/15 shadow-md scale-105"
                    : "border-transparent bg-muted/60 hover:bg-muted"
                )}
                aria-label="도움이 됐어요"
                aria-pressed={mediaFeedback === "like"}
              >
                👍
              </button>
              <span className="text-xs text-muted-foreground">도움이 됐어요</span>
            </div>
            <div className="flex flex-col items-center gap-1.5">
              <button
                type="button"
                disabled={feedbackDisabled}
                onClick={() => onMediaFeedbackChange("dislike")}
                className={cn(
                  "flex h-14 w-14 sm:h-16 sm:w-16 items-center justify-center rounded-2xl border-2 text-3xl sm:text-4xl transition-all",
                  feedbackDisabled && "opacity-50 cursor-not-allowed",
                  mediaFeedback === "dislike"
                    ? "border-primary bg-primary/15 shadow-md scale-105"
                    : "border-transparent bg-muted/60 hover:bg-muted"
                )}
                aria-label="아쉬워요"
                aria-pressed={mediaFeedback === "dislike"}
              >
                👎
              </button>
              <span className="text-xs text-muted-foreground">아쉬워요</span>
            </div>
          </div>
          {syncWarningMessage && (
            <p className="mt-3 text-xs text-center text-destructive">{syncWarningMessage}</p>
          )}
        </div>
      )}

      <div className={cn("mt-6 min-h-0", isFullscreen && "max-w-5xl w-full mx-auto pb-2")}>
        <h4 className="text-sm font-medium text-foreground mb-3">다음 추천 콘텐츠</h4>
        <div className="space-y-3">
          {recommendedQueue.map((content, idx) => (
            <div
              key={content.id}
              role="button"
              tabIndex={0}
              onClick={() => onSelectRecommendedContent(content)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault()
                  onSelectRecommendedContent(content)
                }
              }}
              className="flex items-center gap-3 p-3 rounded-xl bg-muted/50 hover:bg-muted transition-colors cursor-pointer"
            >
              <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center">
                <Play className="w-4 h-4 text-primary" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-foreground truncate">{content.content_title}</p>
                <p className="text-xs text-muted-foreground">{idx === 0 ? "추천 우선" : "다음 추천"}</p>
              </div>
            </div>
          ))}
          {recommendedQueue.length === 0 && (
            <p className="text-sm text-muted-foreground">추천 대기열이 아직 없습니다.</p>
          )}
        </div>
      </div>
    </div>
  )
})

const CounselChatBubble = memo(function CounselChatBubble({ message }: { message: Message }) {
  return (
    <div
      className={`flex w-full min-w-0 ${message.sender === "user" ? "justify-end" : "justify-start"}`}
    >
      <div
        className={`max-w-[80%] min-w-0 rounded-2xl px-4 py-3 ${
          message.sender === "user"
            ? "bg-primary text-primary-foreground rounded-br-md"
            : "bg-muted text-foreground rounded-bl-md"
        }`}
      >
        {message.sender === "user" ? (
          <p className="break-words text-sm leading-relaxed">
            {stripCounselingUserMarkdownSuffix(message.text)}
          </p>
        ) : (
          <ChatMarkdown source={message.text} />
        )}
        {message.sender === "ai" && message.recommendedContent?.video_id && (
          <div className="mt-3 p-3 rounded-xl bg-background/80 border">
            <div className="flex items-center gap-3">
              {message.recommendedContent.thumbnail && (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={message.recommendedContent.thumbnail}
                  alt={message.recommendedContent.title ?? ""}
                  className="w-20 h-14 rounded-lg object-cover flex-shrink-0"
                />
              )}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{message.recommendedContent.title}</p>
                {message.recommendedContent.reason && (
                  <p className="text-xs text-muted-foreground mt-0.5">{message.recommendedContent.reason}</p>
                )}
              </div>
            </div>
          </div>
        )}
        <p
          className={`text-xs mt-1 ${
            message.sender === "user" ? "text-primary-foreground/70" : "text-muted-foreground"
          }`}
        >
          {message.timestamp}
        </p>
      </div>
    </div>
  )
})

function CounselingView({
  messages,
  onSendMessage,
  isSendingMessage,
  isPlaying,
  setIsPlaying,
  autoPlayEnabled,
  contentFeedbackSubmitting,
  contentFeedbackComplete,
  mediaFeedback,
  onMediaFeedbackChange,
  onEndSession,
  onStartNewSession,
  isSessionActive,
  syncWarningMessage,
  currentContent,
  recommendedQueue,
  onSelectRecommendedContent,
  idleWrapUpBanner = false,
  onDismissIdleWrapUp,
  onRequestEndFromIdle,
}: {
  messages: Message[]
  onSendMessage: (messageText: string) => boolean
  isSendingMessage: boolean
  isPlaying: boolean
  setIsPlaying: (value: boolean) => void
  autoPlayEnabled: boolean
  contentFeedbackSubmitting: boolean
  contentFeedbackComplete: boolean
  mediaFeedback: "like" | "dislike" | null
  onMediaFeedbackChange: (value: "like" | "dislike") => void
  onEndSession: () => void
  onStartNewSession: () => void
  isSessionActive: boolean
  syncWarningMessage: string | null
  currentContent: ContentHistoryItem
  recommendedQueue: ContentHistoryItem[]
  onSelectRecommendedContent: (value: ContentHistoryItem) => void
  idleWrapUpBanner?: boolean
  onDismissIdleWrapUp?: () => void
  onRequestEndFromIdle?: () => void
}) {
  const [contentFullscreen, setContentFullscreen] = useState(false)
  const [draft, setDraft] = useState("")
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!contentFullscreen) return
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = "hidden"
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setContentFullscreen(false)
    }
    window.addEventListener("keydown", onKey)
    return () => {
      document.body.style.overflow = prevOverflow
      window.removeEventListener("keydown", onKey)
    }
  }, [contentFullscreen])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: "smooth",
    })
  }, [messages])

  const mediaProps = useMemo(
    () => ({
      currentContent,
      recommendedQueue,
      isPlaying,
      setIsPlaying,
      autoPlayEnabled,
      contentFeedbackSubmitting,
      contentFeedbackComplete,
      mediaFeedback,
      onMediaFeedbackChange,
      syncWarningMessage,
      onSelectRecommendedContent,
    }),
    [
      currentContent,
      recommendedQueue,
      isPlaying,
      setIsPlaying,
      autoPlayEnabled,
      contentFeedbackSubmitting,
      contentFeedbackComplete,
      mediaFeedback,
      onMediaFeedbackChange,
      syncWarningMessage,
      onSelectRecommendedContent,
    ]
  )

  const submitDraft = () => {
    if (onSendMessage(draft)) {
      setDraft("")
    }
  }

  return (
    <div className="flex h-full min-h-0 min-w-0">
      {/* Chat Section */}
      <div className="flex min-h-0 min-w-0 flex-1 flex-col border-r border-border">
        <div className="p-4 border-b border-border bg-card">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-primary flex items-center justify-center">
                <MessageCircle className="w-5 h-5 text-primary-foreground" />
              </div>
              <div>
                <h3 className="font-semibold text-foreground">무드픽 상담사</h3>
                <p className="text-xs text-muted-foreground">AI 심리 상담</p>
              </div>
            </div>
            <Button onClick={onStartNewSession} variant="outline" size="sm" className="rounded-lg">
              <Plus className="w-4 h-4 mr-1" />
              새 채팅
            </Button>
          </div>
        </div>

        {idleWrapUpBanner && isSessionActive && (
          <div className="shrink-0 border-b border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-950 dark:text-amber-100">
            <p className="font-medium">잠시 대화가 멈춘 것 같아요.</p>
            <p className="mt-1 text-amber-900/85 dark:text-amber-50/85">
              계속 상담하시겠어요? 마무리하고 싶다면 오늘의 상담을 종료할 수 있어요.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button
                type="button"
                size="sm"
                variant="secondary"
                className="rounded-lg"
                onClick={() => onDismissIdleWrapUp?.()}
              >
                계속 할게요
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="rounded-lg border-destructive text-destructive hover:bg-destructive/10"
                onClick={() => onRequestEndFromIdle?.()}
              >
                상담 종료하기
              </Button>
            </div>
          </div>
        )}

        <div className="min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-hidden p-4 [scrollbar-gutter:stable]">
          <div className="min-w-0 space-y-4">
            {messages.map((message) => (
              <CounselChatBubble key={message.id} message={message} />
            ))}
            {isSendingMessage && (
              <div className="w-8 h-8 border-[3px] border-primary border-t-transparent rounded-full animate-spin" />
            )}
            <div ref={bottomRef} />
          </div>
        </div>

        <div className="p-4 border-t border-border bg-card">
          <div className="flex gap-3 mb-3">
            <Input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="메시지를 입력하세요..."
              className="flex-1 rounded-xl bg-muted border-0"
              onKeyDown={(e) => e.key === "Enter" && submitDraft()}
            />
            <Button onClick={submitDraft} size="icon" className="rounded-xl" disabled={isSendingMessage}>
              <Send className={`w-4 h-4 ${isSendingMessage ? "opacity-50" : ""}`} />
            </Button>
          </div>
          {isSessionActive && (
            <Button
              onClick={onEndSession}
              variant="outline"
              className="w-full cursor-pointer rounded-xl border-destructive text-destructive hover:border-destructive/70 hover:bg-destructive/10 hover:text-destructive"
            >
              오늘의 상담 종료하기
            </Button>
          )}
        </div>
      </div>

      <div className={cn(
        contentFullscreen ? "fixed inset-0 z-50 bg-background p-4 sm:p-6" : "w-96 shrink-0 bg-card p-6 min-h-0", "overflow-y-auto flex flex-col")}
        role={contentFullscreen ? "dialog" : undefined}
        aria-modal={contentFullscreen? "true" : undefined}
        aria-label={contentFullscreen? "추천 콘텐츠 전체 화면" : undefined}
      >
        <ContentMediaPanel
          variant={contentFullscreen ? "fullscreen" : "sidebar"}
          {...mediaProps}
          onRequestFullscreen={contentFullscreen ? undefined : () => setContentFullscreen(true)}
          onExitFullscreen={contentFullscreen ? () => setContentFullscreen(false) : undefined}
        />
      </div>

    </div>
  )
}

function DashboardView({
  calendarYear,
  currentMonth,
  goCalendarPrev,
  goCalendarNext,
  getDaysInMonth,
  calendarMoods,
  emotionData,
  recentEmotionRecords,
  sessionHistory,
  contentHistory,
  lastSurveyDelta,
  userStats,
  onCalendarDayClick,
  onPlayContentHistory,
}: {
  calendarYear: number
  currentMonth: number
  goCalendarPrev: () => void
  goCalendarNext: () => void
  getDaysInMonth: () => (number | null)[]
  calendarMoods: Record<number, { emoji: string; color: string }>
  emotionData: { date: string; score: number; label: string }[]
  recentEmotionRecords: EmotionRecordItem[]
  sessionHistory: SessionHistory[]
  contentHistory: ContentHistoryItem[]
  lastSurveyDelta: SurveyDeltaSummary | null
  userStats: UserStats | null
  onCalendarDayClick: (day: number) => void
  onPlayContentHistory: (item: ContentHistoryItem) => void
}) {
  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-foreground mb-2">나의 감정 기록</h2>
        <p className="text-muted-foreground">
          당신의 감정 여정을 한눈에 확인하세요
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <Card className="border-0 bg-secondary/40">
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground">총 상담 세션</p>
            <p className="text-2xl font-bold text-foreground">{userStats?.total_sessions ?? 0}</p>
          </CardContent>
        </Card>
        <Card className="border-0 bg-secondary/40">
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground">시청 콘텐츠</p>
            <p className="text-2xl font-bold text-foreground">{userStats?.total_content_watched ?? 0}</p>
          </CardContent>
        </Card>
        <Card className="border-0 bg-secondary/40">
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground">좋아요 비율</p>
            <p className="text-2xl font-bold text-foreground">
              {userStats?.total_feedback
                ? `${Math.round((userStats.likes / userStats.total_feedback) * 100)}%`
                : "0%"}
            </p>
          </CardContent>
        </Card>
        <Card className="border-0 bg-secondary/40">
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground">최근 세션 변화</p>
            <p
              className={`text-2xl font-bold ${
                lastSurveyDelta?.improved ? "text-emerald-600" : "text-muted-foreground"
              }`}
            >
              {lastSurveyDelta ? `${lastSurveyDelta.averageDelta >= 0 ? "+" : ""}${lastSurveyDelta.averageDelta.toFixed(1)}` : "-"}
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-2 gap-6 mb-8">
        {/* Calendar */}
        <Card className="border-0 shadow-lg">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg">감정 캘린더</CardTitle>
              <div className="flex items-center gap-2">
                <Button variant="ghost" size="icon" className="h-8 w-8" onClick={goCalendarPrev}>
                  <ChevronLeft className="w-4 h-4" />
                </Button>
                <span className="text-sm font-medium min-w-[100px] text-center">
                  {calendarYear}년 {currentMonth}월
                </span>
                <Button variant="ghost" size="icon" className="h-8 w-8" onClick={goCalendarNext}>
                  <ChevronRight className="w-4 h-4" />
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-7 gap-1 mb-2">
              {["일", "월", "화", "수", "목", "금", "토"].map((day) => (
                <div key={day} className="text-center text-xs font-medium text-muted-foreground py-2">
                  {day}
                </div>
              ))}
            </div>
            <div className="grid grid-cols-7 gap-1">
              {getDaysInMonth().map((day, idx) => (
                <button
                  key={idx}
                  type="button"
                  disabled={!day}
                  onClick={() => day && onCalendarDayClick(day)}
                  className={`aspect-square flex flex-col items-center justify-center rounded-lg text-sm transition-colors ${
                    day && calendarMoods[day]
                      ? `${calendarMoods[day].color}`
                      : day
                        ? "bg-muted/30 hover:bg-muted cursor-pointer"
                        : ""
                  } ${!day ? "cursor-default" : ""}`}
                >
                  {day && (
                    <>
                      <span className="text-xs text-foreground">{day}</span>
                      {calendarMoods[day] && (
                        <span className="text-xs">{calendarMoods[day].emoji}</span>
                      )}
                    </>
                  )}
                </button>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Emotion Trend Graph */}
        <Card className="border-0 shadow-lg">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">최근 30일 감정 변화 추이</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              {emotionData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={emotionData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 12 }}
                      stroke="var(--muted-foreground)"
                    />
                    <YAxis
                      domain={[0, 100]}
                      tick={{ fontSize: 12 }}
                      stroke="var(--muted-foreground)"
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "var(--card)",
                        border: "1px solid var(--border)",
                        borderRadius: "0.75rem",
                      }}
                      labelStyle={{ color: "var(--foreground)" }}
                    />
                    <Line
                      type="monotone"
                      dataKey="score"
                      stroke="var(--primary)"
                      strokeWidth={3}
                      dot={{ fill: "var(--primary)", strokeWidth: 2, r: 4 }}
                      activeDot={{ r: 6 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-full items-center justify-center rounded-lg bg-muted/30 text-sm text-muted-foreground">
                  아직 표시할 감정 기록이 없습니다.
                </div>
              )}
            </div>
            {recentEmotionRecords.length > 0 && (
              <div className="mt-4 space-y-2">
                {recentEmotionRecords.slice(0, 3).map((record, index) => (
                  <div
                    key={`${record.session_id}-${record.phase ?? "record"}-${record.recorded_at}-${index}`}
                    className="flex items-center justify-between rounded-lg bg-muted/30 px-3 py-2 text-sm"
                  >
                    <div className="flex items-center gap-2">
                      <span>{scoreToEmoji(record.score)}</span>
                      <span className="font-medium text-foreground">
                        {record.phase === "post" ? "상담 후" : "상담 전"}
                      </span>
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {new Date(record.recorded_at).toLocaleString("ko-KR", {
                        month: "long",
                        day: "numeric",
                        hour: "numeric",
                        minute: "2-digit",
                      })}
                    </span>
                  </div>
                ))}
              </div>
            )}
            <div className="flex justify-center gap-4 mt-4">
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">😢 낮음</span>
                <div className="w-16 h-2 bg-gradient-to-r from-blue-300 via-sky-300 to-amber-300 rounded-full" />
                <span className="text-xs text-muted-foreground">😊 높음</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Comforting Media History */}
      <Card className="border-0 shadow-lg mb-8">
        <CardHeader>
          <CardTitle className="text-lg">내가 위로받은 콘텐츠</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-4 overflow-x-auto pb-4 -mx-2 px-2">
            {contentHistory.map((media) => (
              <div
                key={media.id}
                role="button"
                tabIndex={0}
                aria-label={`${media.content_title} 재생`}
                onClick={() => onPlayContentHistory(media)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault()
                    onPlayContentHistory(media)
                  }
                }}
                className="flex-shrink-0 w-48 group cursor-pointer rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                <div className="aspect-video rounded-xl bg-muted mb-2 relative overflow-hidden">
                  <div className="absolute inset-0 flex items-center justify-center">
                    <Play className="w-10 h-10 text-primary" />
                  </div>
                  <div className="absolute inset-0 bg-foreground/0 group-hover:bg-foreground/30 transition-colors flex items-center justify-center">
                    <div className="w-10 h-10 rounded-full bg-primary/80 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                      <Play className="w-5 h-5 text-primary-foreground ml-0.5" />
                    </div>
                  </div>
                  <span className="absolute bottom-2 right-2 px-2 py-0.5 bg-foreground/70 text-primary-foreground text-xs rounded">
                    {new Date(media.watched_at).toLocaleDateString("ko-KR")}
                  </span>
                </div>
                <p className="text-sm font-medium text-foreground line-clamp-2">
                  {media.content_title}
                </p>
              </div>
            ))}
            {contentHistory.length === 0 && (
              <p className="text-sm text-muted-foreground">아직 저장된 콘텐츠 기록이 없습니다.</p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Session History */}
      <Card className="border-0 shadow-lg">
        <CardHeader>
          <CardTitle className="text-lg">상담 기록</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4">
            {sessionHistory.map((session) => (
              <Card key={session.sessionId} className="border border-border bg-muted/30">
                <CardContent className="p-4">
                  <div className="mb-3 space-y-0.5">
                    <p className="text-sm text-muted-foreground">{session.date}</p>
                    <p className="text-xs text-muted-foreground">
                      <span>{session.timeLabel} 시작</span>
                      {session.endTimeLabel ? (
                        <span className="opacity-90"> · {session.endTimeLabel} 종료</span>
                      ) : null}
                      {session.durationLabel ? (
                        <span className="opacity-90"> · {session.durationLabel}</span>
                      ) : null}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">추천된 콘텐츠</p>
                    <p className="text-sm text-primary">{session.media}</p>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
          {sessionHistory.length === 0 && (
            <p className="text-sm text-muted-foreground">아직 저장된 상담 기록이 없습니다.</p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function LoginScreen({
  email,
  setEmail,
  displayName,
  setDisplayName,
  gender,
  setGender,
  birthYear,
  setBirthYear,
  password,
  setPassword,
  onLogin,
  onSignUp,
  onSocialLogin,
  isAuthLoading,
  authErrorMessage,
  authSuccessMessage,
  clearAuthSuccessMessage,
}: {
  email: string
  setEmail: (value: string) => void
  displayName: string
  setDisplayName: (value: string) => void
  gender: string
  setGender: (value: string) => void
  birthYear: string
  setBirthYear: (value: string) => void
  password: string
  setPassword: (value: string) => void
  onLogin: () => Promise<void>
  onSignUp: () => Promise<void>
  onSocialLogin: (provider: "google" | "kakao") => Promise<void>
  isAuthLoading: boolean
  authErrorMessage: string | null
  authSuccessMessage: string | null
  clearAuthSuccessMessage: () => void
}) {
  const isEmailOnlyMode = true
  const [isSignUpMode, setIsSignUpMode] = useState(false)
  const [showLoginPassword, setShowLoginPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const [confirmPassword, setConfirmPassword] = useState("")

  const handleAuthSubmit = async () => {
    if (!isSignUpMode) {
      await onLogin()
      return
    }

    if (!confirmPassword) {
      return
    }

    if (password !== confirmPassword) {
      return
    }

    await onSignUp()
  }

  return (
    <div className="min-h-screen bg-background flex items-start justify-center overflow-y-auto p-4 py-8">
      <div className="w-full max-w-md">
        <Card className="border-0 shadow-2xl">
          <CardContent className="p-8">
            {/* Logo */}
            <div className="text-center mb-8">
              <div className="w-16 h-16 rounded-2xl bg-primary flex items-center justify-center mx-auto mb-4">
                <Heart className="w-8 h-8 text-primary-foreground" />
              </div>
              <h1 className="text-3xl font-bold text-foreground mb-2">무드픽</h1>
              <p className="text-muted-foreground">MoodPick</p>
            </div>

            {/* Welcome Message */}
            <div className="text-center mb-8">
              <p className="text-lg text-foreground font-medium text-balance">
                당신의 마음에 귀 기울이는 시간
              </p>
              <p className="text-sm text-muted-foreground mt-2">
                AI 심리 상담과 맞춤형 미디어로 마음의 평화를 찾아보세요
              </p>
            </div>

            {/* Login Form */}
            <div className="space-y-4 mb-6">
              {isSignUpMode && (
                <div>
                  <Label htmlFor="display-name" className="text-sm text-muted-foreground">
                    서비스에서 불릴 이름
                  </Label>
                  <Input
                    id="display-name"
                    type="text"
                    placeholder="예: 민지"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    className="mt-1.5 rounded-xl bg-muted border-0 h-12"
                    onKeyDown={(e) => e.key === "Enter" && handleAuthSubmit()}
                  />
                </div>
              )}

              {isSignUpMode && (
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div className="flex min-w-0 flex-col">
                    <Label htmlFor="signup-gender" className="text-sm leading-5 text-muted-foreground">
                      성별
                    </Label>
                    <Select value={gender} onValueChange={setGender}>
                      <SelectTrigger
                        id="signup-gender"
                        className="mt-1.5 !h-12 !min-h-12 w-full box-border rounded-xl border-0 bg-muted py-0 data-[size=default]:!h-12"
                      >
                        <SelectValue placeholder="선택 안 함" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="female">여성</SelectItem>
                        <SelectItem value="male">남성</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex min-w-0 flex-col">
                    <Label htmlFor="signup-birth-year" className="text-sm leading-5 text-muted-foreground">
                      출생년도
                    </Label>
                    <Input
                      id="signup-birth-year"
                      type="number"
                      inputMode="numeric"
                      min={1900}
                      max={new Date().getFullYear()}
                      placeholder="예: 2001"
                      value={birthYear}
                      onChange={(e) => setBirthYear(e.target.value)}
                      className="mt-1.5 !h-12 !min-h-12 w-full box-border rounded-xl border-0 bg-muted py-0"
                      onKeyDown={(e) => e.key === "Enter" && handleAuthSubmit()}
                    />
                  </div>
                </div>
              )}

              <div>
                <Label htmlFor="email" className="text-sm text-muted-foreground">
                  이메일
                </Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="example@email.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="mt-1.5 rounded-xl bg-muted border-0 h-12"
                />
              </div>
              <div>
                <Label htmlFor="password" className="text-sm text-muted-foreground">
                  비밀번호
                </Label>
                <div className="relative mt-1.5">
                  <Input
                    id="password"
                    type={showLoginPassword ? "text" : "password"}
                    placeholder="비밀번호를 입력하세요"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="rounded-xl bg-muted border-0 h-12 pr-12"
                    onKeyDown={(e) => e.key === "Enter" && handleAuthSubmit()}
                  />
                  <button
                    type="button"
                    onClick={() => setShowLoginPassword((prev) => !prev)}
                    className="absolute inset-y-0 right-0 flex items-center justify-center w-12 text-muted-foreground hover:text-foreground"
                    aria-label={showLoginPassword ? "비밀번호 숨기기" : "비밀번호 보기"}
                  >
                    {showLoginPassword ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              {isSignUpMode && (
                <div>
                  <Label htmlFor="confirm-password" className="text-sm text-muted-foreground">
                    비밀번호 확인
                  </Label>
                  <div className="relative mt-1.5">
                    <Input
                      id="confirm-password"
                      type={showConfirmPassword ? "text" : "password"}
                      placeholder="비밀번호를 다시 입력하세요"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      className="rounded-xl bg-muted border-0 h-12 pr-12"
                      onKeyDown={(e) => e.key === "Enter" && handleAuthSubmit()}
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirmPassword((prev) => !prev)}
                      className="absolute inset-y-0 right-0 flex items-center justify-center w-12 text-muted-foreground hover:text-foreground"
                      aria-label={showConfirmPassword ? "비밀번호 숨기기" : "비밀번호 보기"}
                    >
                      {showConfirmPassword ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
                    </button>
                  </div>
                  {confirmPassword && password !== confirmPassword && (
                    <p className="mt-2 text-xs text-destructive">비밀번호가 일치하지 않습니다.</p>
                  )}
                </div>
              )}
            </div>

            {/* Login Button */}
            <Button
              onClick={handleAuthSubmit}
              className="w-full h-12 rounded-xl text-base font-medium mb-6"
              disabled={isAuthLoading}
            >
              {isAuthLoading ? (isSignUpMode ? "회원가입 중..." : "로그인 중...") : (isSignUpMode ? "회원가입" : "로그인")}
            </Button>

            {authErrorMessage && (
              <p className="text-sm text-destructive text-center mb-4">{authErrorMessage}</p>
            )}

            {authSuccessMessage && (
              <p className="text-sm text-emerald-600 text-center mb-4">{authSuccessMessage}</p>
            )}

            {!isEmailOnlyMode && (
              <>
                <div className="relative mb-6">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-border" />
                  </div>
                  <div className="relative flex justify-center text-xs">
                    <span className="bg-card px-4 text-muted-foreground">
                      또는 소셜 계정으로 시작하기
                    </span>
                  </div>
                </div>

                <div className="space-y-3">
                  <Button
                    variant="outline"
                    className="w-full h-12 rounded-xl border-2 bg-[#FEE500] hover:bg-[#FEE500]/90 border-[#FEE500] text-[#191919] font-medium"
                    onClick={() => onSocialLogin("kakao")}
                    disabled={isAuthLoading}
                  >
                    카카오로 시작하기
                  </Button>
                  <Button
                    variant="outline"
                    className="w-full h-12 rounded-xl border-2 hover:bg-muted font-medium"
                    onClick={() => onSocialLogin("google")}
                    disabled={isAuthLoading}
                  >
                    Google로 시작하기
                  </Button>
                </div>
              </>
            )}


            {/* Sign Up Link */}
            <p className="text-center text-sm text-muted-foreground mt-6">
              {isSignUpMode ? "이미 계정이 있으신가요? " : "계정이 없으신가요? "}
              <button
                className="text-primary font-medium hover:underline"
                onClick={() => {
                  setIsSignUpMode((prev) => !prev)
                  setConfirmPassword("")
                  setDisplayName("")
                  setGender("")
                  setBirthYear("")
                  clearAuthSuccessMessage()
                }}
              >
                {isSignUpMode ? "로그인" : "회원가입"}
              </button>
            </p>
          </CardContent>
        </Card>

        {/* Footer */}
      </div>
    </div>
  )
}

function OnboardingScreen({
  selectedConcerns,
  setSelectedConcerns,
  selectedCounselingTone,
  setSelectedCounselingTone,
  selectedContentPreference,
  setSelectedContentPreference,
  onComplete,
  isSaving,
  errorMessage,
  activeTab
}: {
  selectedConcerns: string[]
  setSelectedConcerns: (value: string[]) => void
  selectedCounselingTone: string[]
  setSelectedCounselingTone: (value: string[]) => void
  selectedContentPreference: string[]
  setSelectedContentPreference: (value: string[]) => void
  onComplete: () => void
  isSaving: boolean
  errorMessage: string | null
  activeTab: TabType
}) {
  const concerns = [
    { id: "study", label: "학업/취업" },
    { id: "relationship", label: "인간관계" },
    { id: "future", label: "미래에 대한 불안" },
    { id: "work", label: "업무 스트레스" },
    { id: "other", label: "기타" },
  ]

  const counselingTones = [
    { id: "listen", label: "조용히 들어주기" },
    { id: "advice", label: "현실적인 조언" },
  ]

  const contentPreferences = [
    { id: "music", label: "신나는 음악" },
    { id: "video", label: "차분한 영상" },
  ]

  const toggleConcern = (id: string) => {
    if (selectedConcerns.includes(id)) {
      setSelectedConcerns(selectedConcerns.filter((c) => c !== id))
    } else {
      setSelectedConcerns([...selectedConcerns, id])
    }
  }

  const toggleCounselingTone = (id: string) => {
    if (selectedCounselingTone.includes(id)) {
      setSelectedCounselingTone(selectedCounselingTone.filter((s) => s !== id))
    } else {
      setSelectedCounselingTone([...selectedCounselingTone, id])
    }
  }

  const toggleContentPreference = (id: string) => {
    if (selectedContentPreference.includes(id)) {
      setSelectedContentPreference(selectedContentPreference.filter((s) => s !== id))
    } else {
      setSelectedContentPreference([...selectedContentPreference, id])
    }
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-lg">
        <Card className="border-0 shadow-2xl">
          <CardContent className="p-8">
            {/* Logo */}
            <div className="text-center mb-6">
              <div className="w-14 h-14 rounded-2xl bg-primary flex items-center justify-center mx-auto mb-4">
                <Heart className="w-7 h-7 text-primary-foreground" />
              </div>
              <h1 className="text-2xl font-bold text-foreground mb-2">
                무드픽과 더 깊어지기
              </h1>
              <p className="text-muted-foreground text-sm">
                {"Let's get to know you"}
              </p>
            </div>

            {/* Question 1 */}
            <div className="mb-6 flex-1">
              <h3 className="text-base font-semibold text-foreground mb-3">
                요즘 가장 큰 고민이나 스트레스는 무엇인가요?
              </h3>
              <p className="text-xs text-muted-foreground mb-4">
                여러 개를 선택할 수 있어요
              </p>
              <div className="flex flex-wrap gap-2">
                {concerns.map((concern) => (
                  <button
                    key={concern.id}
                    onClick={() => toggleConcern(concern.id)}
                    className={`px-4 py-2 rounded-full text-sm font-medium transition-all duration-200 ${
                      selectedConcerns.includes(concern.id)
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted text-muted-foreground hover:bg-muted/80"
                    }`}
                  >
                    {concern.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Question 2 — 상담 방식 */}
            <div className="mb-6">
              <h3 className="text-base font-semibold text-foreground mb-3">
                어떤 상담 방식을 선호하시나요?
              </h3>
              <p className="text-xs text-muted-foreground mb-4">
                여러 개를 선택할 수 있어요
              </p>
              <div className="flex flex-wrap gap-2">
                {counselingTones.map((tone) => (
                  <button
                    key={tone.id}
                    onClick={() => toggleCounselingTone(tone.id)}
                    className={`px-4 py-2 rounded-full text-sm font-medium transition-all duration-200 ${
                      selectedCounselingTone.includes(tone.id)
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted text-muted-foreground hover:bg-muted/80"
                    }`}
                  >
                    {tone.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Question 3 — 콘텐츠 선호 */}
            <div className="mb-8">
              <h3 className="text-base font-semibold text-foreground mb-3">
                어떤 콘텐츠를 더 좋아하시나요?
              </h3>
              <p className="text-xs text-muted-foreground mb-4">
                여러 개를 선택할 수 있어요
              </p>
              <div className="flex flex-wrap gap-2">
                {contentPreferences.map((pref) => (
                  <button
                    key={pref.id}
                    onClick={() => toggleContentPreference(pref.id)}
                    className={`px-4 py-2 rounded-full text-sm font-medium transition-all duration-200 ${
                      selectedContentPreference.includes(pref.id)
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted text-muted-foreground hover:bg-muted/80"
                    }`}
                  >
                    {pref.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Start Button */}
            <Button
              onClick={onComplete}
              className="w-full h-12 rounded-xl text-base font-medium"
              disabled={(selectedConcerns.length === 0 && selectedCounselingTone.length === 0 && selectedContentPreference.length === 0) || isSaving}
            >
              {isSaving ? "저장 중..." : activeTab==="mypage"? "저장" : "시작하기"}
            </Button>

            {/* Skip Option */}
            <button
              onClick={onComplete}
              disabled={isSaving}
              className="w-full mt-4 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              나중에 설정할게요
            </button>
            {errorMessage && <p className="mt-3 text-center text-xs text-destructive">{errorMessage}</p>}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function SurveyScreen({
  gad,
  setGad,
  phq,
  setPhq,
  pss,
  setPss,
  onComplete,
  isSaving,
  errorMessage,
}: {
  gad: SurveyState;
  setGad: React.Dispatch<React.SetStateAction<SurveyState>>;
  phq: SurveyState;
  setPhq: React.Dispatch<React.SetStateAction<SurveyState>>;
  pss: SurveyState;
  setPss: React.Dispatch<React.SetStateAction<SurveyState>>;
  onComplete: () => Promise<void>;
  isSaving: boolean;
  errorMessage: string | null;
}) {
  const surveyConfigs: Record<SurveyType, SurveyConfig> = {
    GAD: {
      title: "GAD-7",
      description: "지난 2주 동안 당신은 다음의 문제들로 인해서 얼마나 자주 방해를 받았습니까?",
      questions: [
        "초조하거나 불안하거나 조마조마하게 느낀다.",
        "걱정하는 것을 멈추거나 조절할 수가 없다.",
        "여러 가지 것들에 대해 걱정을 너무 많이한다.",
        "편하게 있기가 어렵다.",
        "너무 안절부절 못해서 가만히 있기가 힘들다.",
        "쉽게 짜증이 나거나 쉽게 성을 내게 된다.",
        "마치 끔찍한 일이 생길 것처럼 두렵게 느껴진다.",
      ],
      scoreDescription: "전혀 아니다(0점), 몇일 동안(1점), 2주 중 절반 이상(2점), 거의 매일(3점), 매우 자주(4점)",
      scoreOptions: [0, 1, 2, 3, 4],
    },
    PHQ: {
      title: "PHQ-9",
      description: "아래의 문항을 잘 읽으신 후, 지난 2주 동안 자신을 가장 잘 설명하는 칸에 체크 해 주세요.",
      questions: [
        "기분이 가라앉거나, 우울하거나, 희망이 없다고 느꼈다.",
        "평소 하던 일에 대한 흥미가 없어지거나 즐거움을 느끼지 못했다.",
        "잠들기가 어렵거나 자꾸 깼다/혹은 너무 많이 잤다.",
        "평소보다 식욕이 줄었다/혹은 평소보다 많이 먹었다.",
        "다른 사람들이 눈치 챌 정도로 평소보다 말과 행동이 느려졌다 / 혹은 너무 안절부절 못해서 가만히 앉아있을 수 없었다.",
        "피곤하고 기운이 없었다.",
        "내가 잘 못했거나, 실패했다는 생각이 들었다 / 혹은 자신과 가족을 실망시켰다고 생각했다.",
        "신문을 읽거나 TV를 보는 것과 같은 일상적인 일에도 집중할 수가 없었다.",
        "차라리 죽는 것이 더 낫겠다고 생각했다 / 혹은 자해할 생각을 했다.",
      ],
      scoreDescription: "전혀 아니다(0점), 여러 날 동안(1점), 일주일 이상(2점), 거의 매일(3점)",
      scoreOptions: [0, 1, 2, 3],
    },
    PSS: {
      title: "PSS",
      description: "아래의 문항을 잘 읽으신 후, 지난 1개월 동안 자신의 상태를 가장 잘 나타내는 문항을 선택하여 주십시오.",
      questions: [
        "예상치 못했던 일 때문에 당황했던 적이 얼마나 있었습니까?",
        "인생에서 중요한 일들을 조절할 수 없다는 느낌을 얼마나 경험하였습니까?",
        "신경이 예민해지고 스트레스를 받고 있다는 느낌을 얼마나 경험하였습니까?",
        "당신의 개인적 문제들을 다루는데 있어서 얼마나 자주 자신감을 느끼셨습니까?",
        "일상의 일들이 당신의 생각대로 진행되고 있다는 느낌을 얼마나 경험하였습니까?",
        "당신이 꼭 해야 하는 일을 처리할 수 없다고 생각한 적이 얼마나 있었습니까?",
        "일상생활의 짜증을 얼마나 자주 잘 다스릴 수 있었습니까?",
        "최상의 컨디션이라고 얼마나 자주 느끼셨습니까?",
        "당신이 통제할 수 없는 일 때문에 화가 난 경험이 얼마나 있었습니까?",
        "어려운 일들이 너무 많이 쌓여서 극복하지 못할 것 같은 느낌을 얼마나 자주 경험하셨습니까?",
      ],
      scoreDescription: "전혀 없었다(0점), 거의 없었다(1점), 때때로 있었다(2점), 자주 있었다(3점), 매우 자주 있었다(4점)",
      scoreOptions: [0, 1, 2, 3, 4],
    },
  }

  const surveyOrder: SurveyType[] = ["GAD", "PHQ", "PSS"]
  const [surveyType, setSurveyType] = useState<SurveyType>("GAD")
  const [surveyIndex, setSurveyIndex] = useState(0)

  const surveyStateByType: Record<SurveyType, SurveyState> = {
    GAD: gad,
    PHQ: phq,
    PSS: pss,
  }
  const surveySetterByType: Record<SurveyType, React.Dispatch<React.SetStateAction<SurveyState>>> = {
    GAD: setGad,
    PHQ: setPhq,
    PSS: setPss,
  }

  const currentConfig = surveyConfigs[surveyType]
  const currentSurvey = surveyStateByType[surveyType]
  const currentSetSurvey = surveySetterByType[surveyType]
  const completedCount = currentSurvey.scores.filter((score) => score !== -1).length
  const isCompleted = currentSurvey.scores.every((score) => score !== -1)
  const isSubmitted = currentSurvey.isDone

  const moveToSurvey = (type: SurveyType) => {
    setSurveyType(type)
    setSurveyIndex(0)
  }

  const moveToNextQuestion = () => {
    const nextUnansweredIndex = currentSurvey.scores.findIndex(
      (score, index) => index > surveyIndex && score === -1
    )
    if (nextUnansweredIndex !== -1) {
      setSurveyIndex(nextUnansweredIndex)
      return
    }

    if (surveyIndex < currentConfig.questions.length - 1) {
      setSurveyIndex((prev) => prev + 1)
      return
    }

    const firstUnansweredIndex = currentSurvey.scores.findIndex((score) => score === -1)
    if (firstUnansweredIndex !== -1) {
      setSurveyIndex(firstUnansweredIndex)
    }
  }

  const moveToNextSurvey = (doneStates: Record<SurveyType, boolean>) => {
    const currentIndex = surveyOrder.indexOf(surveyType)
    const remainingInOrder = [
      ...surveyOrder.slice(currentIndex + 1),
      ...surveyOrder.slice(0, currentIndex),
    ]
    const nextType = remainingInOrder.find((type) => !doneStates[type])

    if (nextType) {
      moveToSurvey(nextType)
    }
  }

  const handleSelectScore = (score: number) => {
    if (isSubmitted) return

    currentSetSurvey((prev) => ({
      ...prev,
      scores: prev.scores.map((item, index) => (index === surveyIndex ? score : item)),
    }))

    if (surveyIndex < currentConfig.questions.length - 1) {
      window.setTimeout(() => {
        moveToNextQuestion()
      }, 120)
    }
  }

  const handleSubmitSurvey = async () => {
    if (isSaving || isSubmitted || !isCompleted) return

    currentSetSurvey((prev) => ({ ...prev, isDone: true }))

    const nextDoneStates: Record<SurveyType, boolean> = {
      GAD: surveyType === "GAD" ? true : gad.isDone,
      PHQ: surveyType === "PHQ" ? true : phq.isDone,
      PSS: surveyType === "PSS" ? true : pss.isDone,
    }

    const allCompleted = surveyOrder.every((type) => nextDoneStates[type])
    if (allCompleted) {
      await onComplete()
      return
    }

    moveToNextSurvey(nextDoneStates)
  }

  const nextButtonLabel = isSubmitted
    ? "제출 완료"
    : !isCompleted
      ? "다음"
      : isSaving
        ? "저장 중..."
        : "제출하기"

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-2xl">
        <Card className="min-h-[680px] border-0 shadow-2xl">
          <CardContent className="flex min-h-[680px] flex-col p-6 sm:p-8">
            <div className="mb-5 text-center">
              <div className="mx-auto mb-4 flex h-14 w-full max-w-sm items-center justify-evenly overflow-hidden rounded-2xl bg-primary">
                {surveyOrder.map((type) => {
                  const isActive = surveyType === type
                  const isDoneForType = surveyStateByType[type].isDone

                  return (
                    <button
                      key={type}
                      type="button"
                      onClick={() => moveToSurvey(type)}
                      className={`flex h-full flex-1 items-center justify-center transition-colors hover:bg-primary-foreground/10 cursor-pointer ${
                        isActive ? "bg-primary-foreground/20" : ""
                      }`}
                      aria-label={`${type} 설문으로 이동`}
                    >
                      <Heart
                        className={`h-7 w-7 ${
                          isActive
                            ? "text-black"
                            : isDoneForType
                              ? "text-emerald-200"
                              : "text-primary-foreground"
                        }`}
                      />
                    </button>
                  )
                })}
              </div>
              <h1 className="mb-2 text-2xl font-bold text-foreground">{currentConfig.title}</h1>
              <p className="text-sm leading-relaxed text-muted-foreground">{currentConfig.description}</p>
            </div>

            <div className="mb-8 flex-1">
              <div className="min-h-[132px]">
                <h3 className="mb-3 text-base font-semibold leading-relaxed text-foreground">
                  {surveyIndex + 1}. {currentConfig.questions[surveyIndex]}
                </h3>
                <p className="mb-4 text-xs leading-relaxed text-muted-foreground">
                  {currentConfig.scoreDescription}
                </p>
              </div>

              <div className="flex flex-col gap-3">
                <div className="grid grid-cols-5 gap-2">
                  {currentConfig.scoreOptions.map((score) => (
                    <label
                      key={score}
                      className={`flex h-14 items-center justify-center rounded-xl border text-sm font-medium transition hover:-translate-y-0.5 hover:shadow-md ${
                        currentSurvey.scores[surveyIndex] === score
                          ? "border-primary bg-primary/10 text-primary"
                          : "bg-background"
                      } ${isSubmitted ? "cursor-default opacity-70" : "cursor-pointer"}`}
                    >
                      <input
                        type="radio"
                        name={`survey-${surveyType}-${surveyIndex}`}
                        checked={currentSurvey.scores[surveyIndex] === score}
                        disabled={isSubmitted}
                        className="sr-only"
                        onChange={() => handleSelectScore(score)}
                      />
                      <span>{score}점</span>
                    </label>
                  ))}
                </div>

                <div>
                  <progress className="h-2 w-full" value={completedCount} max={currentConfig.questions.length} />
                </div>

                <div className="grid grid-cols-5 gap-2 sm:grid-cols-10">
                  {currentConfig.questions.map((_, index) => (
                    <button
                      key={index}
                      type="button"
                      onClick={() => setSurveyIndex(index)}
                      className={`h-9 rounded-lg text-sm font-medium cursor-pointer ${
                        currentSurvey.scores[index] !== -1 ? "bg-blue-500 text-white" : "bg-gray-200 text-gray-700"
                      } ${surveyIndex === index ? "ring-2 ring-primary ring-offset-2" : ""}`}
                    >
                      {index + 1}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <Button
                type="button"
                variant="outline"
                onClick={() => setSurveyIndex((prev) => Math.max(prev - 1, 0))}
                className="h-12 rounded-xl text-base font-medium cursor-pointer"
                disabled={surveyIndex === 0 || isSaving}
              >
                이전
              </Button>
              <Button
                type="button"
                onClick={() => {
                  if (isSubmitted) return
                  if (isCompleted) {
                    void handleSubmitSurvey()
                    return
                  }
                  moveToNextQuestion()
                }}
                className="h-12 rounded-xl text-base font-medium cursor-pointer"
                disabled={isSaving || isSubmitted}
              >
                {nextButtonLabel}
              </Button>
            </div>

            {errorMessage && <p className="mt-3 text-center text-xs text-destructive">{errorMessage}</p>}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function Introduce({introduceCheck}: {introduceCheck: () => void}){
  return (
    <div className="fixed inset-0 z-50 bg-background/95 backdrop-blur-sm flex items-center justify-center p-4">
      <Card className="w-full max-w-lg border-0 shadow-2xl">
        <CardContent className="p-8">
          {/* Logo */}
          <div className="text-center mb-8">
              <div className="w-16 h-16 rounded-2xl bg-primary flex items-center justify-center mx-auto mb-4">
                <Heart className="w-8 h-8 text-primary-foreground" />
              </div>
              <h1 className="text-3xl font-bold text-foreground mb-2">무드픽</h1>
              <p className="text-muted-foreground">MoodPick</p>
            </div>

          {/* Question */}
          <div className="mb-8">
            <h3 className="text-lg font-semibold text-foreground mb-4">
              무드픽은 어떤 서비스인가요?
            </h3>
            <div className="rounded-xl border p-3">
              <ul className="list-disc pl-5 text-lg">
                <li>무드픽은 사용자의 실시간 감정 맥락을 파악해 정서적 개선 및 개인화 콘텐츠를 제공하는 AI 에이전트 시스템입니다.</li>
                {/* 띄든가 말든가 */}
                <li>무드픽은 대화 전에 더 나은 추천을 위해 온보딩, 문진, 사전질문을 받습니다.</li>
                <li>더 나은 추천을 위해 사후질문에 꼭 답을 해주시기 바랍니다.</li>

              </ul>             
            </div>
          </div>

          {/* Complete Button */}
          <Button
            className="w-full h-12 rounded-xl text-base font-medium"
            onClick={introduceCheck}
          >
            확인완료
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}

function MyPageView({
  autoPlayEnabled,
  setAutoPlayEnabled,
  onLogout,
  userEmail,
  displayName,
  onSaveDisplayName,
  profileSaveMessage,
  isSavingProfile,
  onSaveMypagePreferences,
  mypagePrefsMessage,
  isSavingMypagePrefs,
  userCreatedAt,
  totalSessions,
  dailyReminderEnabled,
  setDailyReminderEnabled,
  dailyReminderTime,
  setDailyReminderTime,
  dailyReminderTimezone,
  setDailyReminderTimezone,
  onSaveReminderPreference,
  reminderSaveMessage,
  onExportMyData,
  isExportingMyData,
  exportMyDataMessage,
  setHasCompletedOnboarding,
  setSurveySave,
  surveyEnter
}: {
  autoPlayEnabled: boolean
  setAutoPlayEnabled: (value: boolean) => void
  onLogout: () => void
  userEmail: string
  displayName: string | null
  onSaveDisplayName: (name: string) => Promise<boolean>
  profileSaveMessage: string | null
  isSavingProfile: boolean
  onSaveMypagePreferences: () => Promise<void>
  mypagePrefsMessage: string | null
  isSavingMypagePrefs: boolean
  userCreatedAt: string | null
  totalSessions: number
  dailyReminderEnabled: boolean
  setDailyReminderEnabled: (value: boolean) => void
  dailyReminderTime: string
  setDailyReminderTime: (value: string) => void
  dailyReminderTimezone: string
  setDailyReminderTimezone: (value: string) => void
  onSaveReminderPreference: () => Promise<void>
  reminderSaveMessage: string | null
  onExportMyData: () => Promise<void>
  isExportingMyData: boolean
  exportMyDataMessage: string | null
  setHasCompletedOnboarding: (value: boolean)=>void
  setSurveySave: (value: boolean)=>void
  surveyEnter: boolean
}) {
  const [profileOpen, setProfileOpen] = useState(false)
  const [draftDisplayName, setDraftDisplayName] = useState("")

  const joinedAtText = userCreatedAt
    ? new Date(userCreatedAt).toLocaleDateString("ko-KR", {
        year: "numeric",
        month: "long",
        day: "numeric",
      })
    : "-"

  const shownName = displayName?.trim() || userEmail.split("@")[0]

  const openProfileEdit = () => {
    setDraftDisplayName(displayName?.trim() || userEmail.split("@")[0])
    setProfileOpen(true)
  }

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-foreground mb-2">마이페이지</h2>
        <p className="text-muted-foreground">계정 설정 및 환경설정을 관리하세요</p>
      </div>

      <Dialog open={profileOpen} onOpenChange={setProfileOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>표시 이름 수정</DialogTitle>
            <DialogDescription>서비스에서 보여질 이름을 입력하세요.</DialogDescription>
          </DialogHeader>
          <div className="space-y-2 py-2">
            <Label htmlFor="edit-display-name">이름</Label>
            <Input
              id="edit-display-name"
              value={draftDisplayName}
              onChange={(e) => setDraftDisplayName(e.target.value)}
              className="rounded-xl bg-muted border-0"
              placeholder="이름"
            />
            {profileSaveMessage && (
              <p
                className={`text-xs ${profileSaveMessage.includes("실패") ? "text-destructive" : "text-muted-foreground"}`}
              >
                {profileSaveMessage}
              </p>
            )}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setProfileOpen(false)}>
              취소
            </Button>
            <Button
              type="button"
              disabled={isSavingProfile}
              onClick={() =>
                void (async () => {
                  const ok = await onSaveDisplayName(draftDisplayName)
                  if (ok) setProfileOpen(false)
                })()
              }
            >
              {isSavingProfile ? "저장 중…" : "저장"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Profile Section */}
      <Card className="border-0 shadow-lg mb-6">
        <CardHeader>
          <CardTitle className="text-lg">프로필</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-6">
            <div className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center">
              <User className="w-10 h-10 text-primary" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="text-xl font-semibold text-foreground mb-1 truncate">{shownName}</h3>
              <p className="text-muted-foreground break-all">{userEmail}</p>
              <div className="flex items-center gap-2 mt-3 flex-wrap">
                <span className="px-3 py-1 bg-primary/10 text-primary text-xs rounded-full font-medium">
                  일반 회원
                </span>
                <span className="text-xs text-muted-foreground">
                  가입일: {joinedAtText}
                </span>
              </div>
            </div>
            <Button variant="outline" className="rounded-xl shrink-0" type="button" onClick={openProfileEdit}>
              프로필 수정
            </Button>
            <Button variant="outline" className="rounded-xl shrink-0" type="button" disabled={!surveyEnter} onClick={()=>setSurveySave(false)}>
              설문
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Preferences Section */}
      <Card className="border-0 shadow-lg mb-6">
        <CardHeader className="flex justify-between">
          <CardTitle className="text-lg">맞춤 설정</CardTitle>
          {!DEMO_HIDE_ONBOARDING ? (
            <Button variant="outline" className="rounded-xl shrink-0" type="button" onClick={()=>setHasCompletedOnboarding(false)}>온보딩</Button>
          ) : null}
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Auto-play Toggle */}
          <div className="flex items-center justify-between">
            <div>
              <Label htmlFor="autoplay" className="text-base font-medium text-foreground">
                콘텐츠 자동 재생 허용
              </Label>
              <p className="text-sm text-muted-foreground mt-1">
                AI 상담 중 추천 콘텐츠를 자동으로 재생합니다. 유튜브는 브라우저 정책상 처음에 음소거로
                시작할 수 있어요(플레이어에서 음소거 해제).
              </p>
            </div>
            <Switch
              id="autoplay"
              checked={autoPlayEnabled}
              onCheckedChange={setAutoPlayEnabled}
            />
          </div>

          <div className="flex flex-col sm:flex-row sm:items-center gap-2">
            <Button
              type="button"
              variant="secondary"
              className="rounded-xl w-fit"
              disabled={isSavingMypagePrefs}
              onClick={() => void onSaveMypagePreferences()}
            >
              {isSavingMypagePrefs ? "저장 중…" : "맞춤 설정 계정에 저장"}
            </Button>
            {mypagePrefsMessage && (
              <p className="text-xs text-muted-foreground">{mypagePrefsMessage}</p>
            )}
          </div>

          <div className="hidden rounded-xl border border-border p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <Label htmlFor="daily-reminder" className="text-base font-medium text-foreground">
                  매일 리마인더
                </Label>
                <p className="text-sm text-muted-foreground mt-1">
                  지정 시간에 상담 시작 알림을 받습니다
                </p>
              </div>
              <Switch
                id="daily-reminder"
                checked={dailyReminderEnabled}
                onCheckedChange={setDailyReminderEnabled}
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <Label htmlFor="reminder-time" className="text-sm text-muted-foreground">알림 시각</Label>
                <Input
                  id="reminder-time"
                  type="time"
                  value={dailyReminderTime}
                  onChange={(e) => setDailyReminderTime(e.target.value)}
                  className="mt-1.5 rounded-xl bg-muted border-0 h-11"
                />
              </div>
              <div>
                <Label htmlFor="reminder-timezone" className="text-sm text-muted-foreground">타임존</Label>
                <Input
                  id="reminder-timezone"
                  value={dailyReminderTimezone}
                  onChange={(e) => setDailyReminderTimezone(e.target.value)}
                  placeholder="Asia/Seoul"
                  className="mt-1.5 rounded-xl bg-muted border-0 h-11"
                />
              </div>
            </div>

            <Button onClick={() => void onSaveReminderPreference()} variant="outline" className="rounded-xl">
              리마인더 설정 저장
            </Button>
            {reminderSaveMessage && <p className="text-xs text-muted-foreground">{reminderSaveMessage}</p>}
          </div>
        </CardContent>
      </Card>

      {/* Data Management Section */}
      <Card className="border-0 shadow-lg mb-6">
        <CardHeader>
          <CardTitle className="text-lg">데이터 관리</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between p-4 bg-muted/50 rounded-xl">
            <div>
              <p className="font-medium text-foreground">내 상담 기록</p>
              <p className="text-sm text-muted-foreground">
                총 {totalSessions}회의 상담 기록이 저장되어 있습니다
              </p>
              {exportMyDataMessage && (
                <p className="text-xs text-muted-foreground mt-1">{exportMyDataMessage}</p>
              )}
            </div>
            <Button
              variant="outline"
              className="rounded-xl shrink-0"
              type="button"
              disabled={isExportingMyData}
              onClick={() => void onExportMyData()}
            >
              {isExportingMyData ? "내보내는 중…" : "기록 내보내기 (JSON)"}
            </Button>
          </div>

          <div className="hidden items-center justify-between p-4 bg-destructive/5 rounded-xl border border-destructive/20">
            <div>
              <p className="font-medium text-foreground">내 상담 기록 초기화</p>
              <p className="text-sm text-muted-foreground">
                모든 상담 기록과 감정 데이터가 영구적으로 삭제됩니다
              </p>
            </div>
            <Button
              variant="outline"
              type="button"
              disabled
              title="준비 중입니다"
              className="rounded-xl border-destructive text-destructive opacity-60"
            >
              <Trash2 className="w-4 h-4 mr-2" />
              초기화
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Logout Button */}
      <Button
        variant="outline"
        onClick={onLogout}
        className="w-full h-12 rounded-xl text-muted-foreground hover:text-foreground"
      >
        <LogOut className="w-4 h-4 mr-2" />
        로그아웃
      </Button>
    </div>
  )
}

const PERSONA_OPTIONS: { value: CounselorPersona; label: string; description: string; emoji: string }[] = [
  { value: "friend", label: "친구", description: "편하게 수다 떠는 친한 친구", emoji: "🧃" },
  { value: "teacher", label: "선생님", description: "차분히 다 받아주는 따뜻한 선생님", emoji: "🌿" },
  { value: "expert", label: "전문상담사", description: "정중한 존댓말의 임상 상담사", emoji: "🩺" },
]

function PreSurveyOverlay({
  selectedMood,
  setSelectedMood,
  selectedPersona,
  setSelectedPersona,
  onStart,
  onClose,
  showCounselingTabGateHint = false,
}: {
  selectedMood: string | null
  setSelectedMood: (value: string | null) => void
  selectedPersona: CounselorPersona | null
  setSelectedPersona: (value: CounselorPersona | null) => void
  onStart: () => void | Promise<void>
  onClose: () => void
  showCounselingTabGateHint?: boolean
}) {
  return (
    <div className="fixed inset-0 z-[550] bg-background/95 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto">
      <Card className="relative z-10 w-full max-w-lg border-0 shadow-2xl pointer-events-auto my-8">
        <CardContent className="p-8">
          {/* Close Button */}
          <button
            type="button"
            onClick={onClose}
            className="absolute top-4 right-4 p-2 rounded-full hover:bg-muted transition-colors"
          >
            <X className="w-5 h-5 text-muted-foreground" />
          </button>

          {/* Logo */}
          <div className="text-center mb-8">
            <div className="w-14 h-14 rounded-2xl bg-primary flex items-center justify-center mx-auto mb-4">
              <Heart className="w-7 h-7 text-primary-foreground" />
            </div>
            <h2 className="text-2xl font-bold text-foreground mb-2">사전 문진</h2>
            {showCounselingTabGateHint && (
              <p className="text-sm text-foreground/90 mb-3 text-balance leading-relaxed">
                상담을 시작하려면 아래 사전 문진을 먼저 완료해 주세요.
              </p>
            )}
            <p className="text-muted-foreground">상담 시작 전, 지금의 마음 상태를 알려주세요</p>
          </div>

          {/* Mood */}
          <div className="mb-8">
            <h3 className="text-lg font-semibold text-center text-foreground mb-6">
              지금 마음의 온도는 어떤가요?
            </h3>
            <div className="flex flex-wrap justify-center gap-3">
              {SURVEY_MOOD_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setSelectedMood(option.value)}
                  className={`flex flex-col items-center p-4 rounded-2xl transition-all duration-200 min-w-[90px] ${
                    selectedMood === option.value
                      ? "bg-primary/10 ring-2 ring-primary scale-105"
                      : "bg-muted hover:bg-muted/80"
                  }`}
                >
                  <span className="text-3xl mb-2">{option.emoji}</span>
                  <span className="text-xs text-foreground font-medium whitespace-nowrap">
                    {option.label}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Persona */}
          <div className="mb-8">
            <h3 className="text-lg font-semibold text-center text-foreground mb-2">
              어떤 상담사와 이야기하고 싶나요?
            </h3>
            <p className="text-xs text-muted-foreground text-center mb-6">
              이 세션 동안만 적용돼요. 다음 상담에서 다시 고를 수 있어요.
            </p>
            <div className="flex flex-col gap-2">
              {PERSONA_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setSelectedPersona(option.value)}
                  className={`flex items-center gap-3 p-3 rounded-xl text-left transition-all duration-200 ${
                    selectedPersona === option.value
                      ? "bg-primary/10 ring-2 ring-primary"
                      : "bg-muted hover:bg-muted/80"
                  }`}
                >
                  <span className="text-2xl">{option.emoji}</span>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-semibold text-foreground">{option.label}</div>
                    <div className="text-xs text-muted-foreground whitespace-normal">
                      {option.description}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Start Button */}
          <Button
            type="button"
            onClick={() => void onStart()}
            className={cn(
              "w-full h-12 rounded-xl text-base font-medium",
              (!selectedMood || !selectedPersona) && "opacity-80"
            )}
          >
            상담 시작
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}

function PostSurveyOverlay({
  selectedMood,
  setSelectedMood,
  isSubmitting = false,
  onComplete,
}: {
  selectedMood: string | null
  setSelectedMood: (value: string | null) => void
  isSubmitting?: boolean
  onComplete: () => void | Promise<void>
}) {
  return (
    <div className="fixed inset-0 z-[550] bg-background/95 backdrop-blur-sm flex items-center justify-center p-4">
      <Card className="relative z-10 w-full max-w-lg border-0 shadow-2xl pointer-events-auto">
        <CardContent className="p-8">
          {/* Logo */}
          <div className="text-center mb-8">
            <div className="w-14 h-14 rounded-2xl bg-primary flex items-center justify-center mx-auto mb-4">
              <Heart className="w-7 h-7 text-primary-foreground" />
            </div>
            <h2 className="text-2xl font-bold text-foreground mb-2">사후 문진</h2>
            <p className="text-muted-foreground text-balance">
              무드픽과 함께한 시간, 마음이 조금 편안해지셨나요?
            </p>
          </div>

          {/* Question */}
          <div className="mb-8">
            <h3 className="text-lg font-semibold text-center text-foreground mb-6">
              지금 마음의 온도는 어떤가요?
            </h3>
            <div className="flex flex-wrap justify-center gap-3">
              {SURVEY_MOOD_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setSelectedMood(option.value)}
                  className={`flex flex-col items-center p-4 rounded-2xl transition-all duration-200 min-w-[90px] ${
                    selectedMood === option.value
                      ? "bg-primary/10 ring-2 ring-primary scale-105"
                      : "bg-muted hover:bg-muted/80"
                  }`}
                >
                  <span className="text-3xl mb-2">{option.emoji}</span>
                  <span className="text-xs text-foreground font-medium whitespace-nowrap">
                    {option.label}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Complete Button */}
          <Button
            type="button"
            onClick={() => void onComplete()}
            disabled={isSubmitting}
            className={cn(
              "w-full h-12 rounded-xl text-base font-medium",
              !selectedMood && "opacity-80"
            )}
          >
            {isSubmitting ? "처리 중…" : "완료 및 홈으로"}
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
