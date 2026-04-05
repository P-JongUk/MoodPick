"use client"

import { useEffect, useState } from "react"
import { useAuth } from "@/components/auth-provider"
import { getSupabaseClient } from "@/lib/supabaseClient"
import {
  endCounselingSession,
  saveContentFeedback,
  saveSurveyResponse,
  startCounselingSession,
} from "@/lib/sessionData"
import {
  getContentHistory,
  getEmotionRecords,
  getEmotionSummary,
  getInitialCounselingMessage,
  getSurveyDelta,
  getUserSessions,
  getUserStats,
  sendCounselingMessage,
  getReminderPreference,
  upsertReminderPreference,
} from "@/lib/api"
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
  ThumbsUp,
  ThumbsDown,
  X,
} from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
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

type TabType = "home" | "counseling" | "dashboard" | "mypage"

interface Message {
  id: number
  sender: "user" | "ai"
  text: string
  timestamp: string
}

interface Emotion {
  emoji: string
  label: string
  color: string
}

interface SessionHistory {
  id: number
  date: string
  concern: string
  media: string
}

interface SurveyDeltaSummary {
  sessionId: string
  averageDelta: number
  improved: boolean
}

interface UserStats {
  total_sessions: number
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

const emotions: Emotion[] = [
  { emoji: "😊", label: "기쁨", color: "bg-amber-100 hover:bg-amber-200 border-amber-300" },
  { emoji: "😐", label: "평온", color: "bg-sky-100 hover:bg-sky-200 border-sky-300" },
  { emoji: "😢", label: "슬픔", color: "bg-blue-100 hover:bg-blue-200 border-blue-300" },
  { emoji: "😡", label: "분노", color: "bg-rose-100 hover:bg-rose-200 border-rose-300" },
  { emoji: "😫", label: "불안", color: "bg-orange-100 hover:bg-orange-200 border-orange-300" },
]

const defaultContentItem: ContentHistoryItem = {
  id: "default-content",
  content_id: "fireplace-comfort-001",
  content_title: "우울함을 달래주는 따뜻한 장작 소리",
  watched_at: new Date().toISOString(),
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
  const [inputMessage, setInputMessage] = useState("")
  const [selectedEmotion, setSelectedEmotion] = useState<string | null>(null)
  const [isPlaying, setIsPlaying] = useState(true)
  const [currentMonth, setCurrentMonth] = useState(new Date().getMonth() + 1)
  const [mediaFeedback, setMediaFeedback] = useState<"like" | "dislike" | null>(null)

  // Session flow state
  const [isSessionActive, setIsSessionActive] = useState(false)
  const [showPreSurvey, setShowPreSurvey] = useState(false)
  const [showPostSurvey, setShowPostSurvey] = useState(false)
  const [preSurveyMood, setPreSurveyMood] = useState<string | null>(null)
  const [postSurveyMood, setPostSurveyMood] = useState<string | null>(null)
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)
  const [syncWarningMessage, setSyncWarningMessage] = useState<string | null>(null)
  const [isSendingMessage, setIsSendingMessage] = useState(false)
  const [lastSurveyDelta, setLastSurveyDelta] = useState<SurveyDeltaSummary | null>(null)
  const [userStats, setUserStats] = useState<UserStats | null>(null)
  const [emotionSummary, setEmotionSummary] = useState<EmotionSummary | null>(null)
  const [emotionData, setEmotionData] = useState<{ date: string; score: number; label: string }[]>([])
  const [calendarMoods, setCalendarMoods] = useState<Record<number, { emoji: string; color: string }>>({})
  const [sessionHistory, setSessionHistory] = useState<SessionHistory[]>([])
  const [contentHistory, setContentHistory] = useState<ContentHistoryItem[]>([])
  const [currentContent, setCurrentContent] = useState<ContentHistoryItem>(defaultContentItem)
  const [recommendedQueue, setRecommendedQueue] = useState<ContentHistoryItem[]>([])

  // Login form state
  const [loginEmail, setLoginEmail] = useState("")
  const [signupDisplayName, setSignupDisplayName] = useState("")
  const [loginPassword, setLoginPassword] = useState("")
  const [authSuccessMessage, setAuthSuccessMessage] = useState<string | null>(null)

  // Onboarding state
  const [selectedConcerns, setSelectedConcerns] = useState<string[]>([])
  const [selectedComfortStyle, setSelectedComfortStyle] = useState<string[]>([])

  // My page settings state
  const [autoPlayEnabled, setAutoPlayEnabled] = useState(true)
  const [mediaPreference, setMediaPreference] = useState("youtube")
  const [dailyReminderEnabled, setDailyReminderEnabled] = useState(true)
  const [dailyReminderTime, setDailyReminderTime] = useState("22:00")
  const [dailyReminderTimezone, setDailyReminderTimezone] = useState("Asia/Seoul")
  const [reminderSaveMessage, setReminderSaveMessage] = useState<string | null>(null)

  useEffect(() => {
    const loadDashboardData = async () => {
      if (!user?.id) {
        setUserStats(null)
        setEmotionSummary(null)
        setEmotionData([])
        setCalendarMoods({})
        setSessionHistory([])
        setContentHistory([])
        setCurrentContent(defaultContentItem)
        setRecommendedQueue([])
        return
      }

      try {
        const [stats, emotionRecordsRaw, summary, sessionsRaw, contentsRaw] = await Promise.all([
          getUserStats(user.id),
          getEmotionRecords(user.id, 30),
          getEmotionSummary(user.id, 30),
          getUserSessions(user.id, 10),
          getContentHistory(user.id, 20),
        ])

        setUserStats(stats as UserStats)
        setEmotionSummary(summary as EmotionSummary)

        const emotionRecords = (emotionRecordsRaw as EmotionRecordItem[]) || []
        const groupedByDay = new Map<string, number[]>()
        const dayMoodMap: Record<number, { emoji: string; color: string }> = {}

        emotionRecords.forEach((record) => {
          const date = new Date(record.recorded_at)
          const dayKey = `${date.getMonth() + 1}/${date.getDate()}`
          const scores = groupedByDay.get(dayKey) ?? []
          scores.push(record.score)
          groupedByDay.set(dayKey, scores)

          if (date.getMonth() + 1 === currentMonth && record.question === "mood_general") {
            dayMoodMap[date.getDate()] = {
              emoji: scoreToEmoji(record.score),
              color: scoreToCalendarColor(record.score),
            }
          }
        })

        const emotionChartData = Array.from(groupedByDay.entries())
          .map(([date, scores]) => {
            const avg = scores.reduce((sum, score) => sum + score, 0) / scores.length
            return {
              date,
              score: Math.round((avg / 5) * 100),
              label: scoreToLabel(avg),
            }
          })
          .sort((a, b) => {
            const [aMonth, aDay] = a.date.split("/").map(Number)
            const [bMonth, bDay] = b.date.split("/").map(Number)
            if (aMonth === bMonth) return aDay - bDay
            return aMonth - bMonth
          })

        setEmotionData(emotionChartData)
        setCalendarMoods(dayMoodMap)

        const contentItems = (contentsRaw as ContentHistoryItem[]) || []
        setContentHistory(contentItems)
        setCurrentContent(contentItems[0] ?? defaultContentItem)
        setRecommendedQueue(contentItems.slice(1, 3))

        const contentBySession = new Map<string, string>()
        contentItems.forEach((content) => {
          if (content.session_id && !contentBySession.has(content.session_id)) {
            contentBySession.set(content.session_id, content.content_title)
          }
        })

        const sessionRows = (sessionsRaw?.sessions as Array<{ id: string; started_at: string }>) || []
        const mappedSessionHistory = sessionRows.slice(0, 6).map((session, index) => ({
          id: index + 1,
          date: new Date(session.started_at).toLocaleDateString("ko-KR", {
            year: "numeric",
            month: "long",
            day: "numeric",
          }),
          concern: "상담 세션 기록",
          media: contentBySession.get(session.id) ?? "추천 콘텐츠 기록 없음",
        }))

        setSessionHistory(mappedSessionHistory)
      } catch {
        setUserStats(null)
        setEmotionSummary(null)
      }
    }

    void loadDashboardData()
  }, [currentMonth, user?.id])

  useEffect(() => {
    const loadReminderPreference = async () => {
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
      setSelectedComfortStyle([])
      setOnboardingErrorMessage(null)
      setIsOnboardingStateLoading(false)
      return
    }

    const metadata = (user.user_metadata ?? {}) as {
      onboarding_completed?: boolean
      onboarding_profile?: {
        concerns?: string[]
        comfort_style?: string[]
      }
    }

    const completed = metadata.onboarding_completed
    // Backward compatibility: existing users without metadata skip onboarding.
    setHasCompletedOnboarding(typeof completed === "boolean" ? completed : true)

    const profile = metadata.onboarding_profile
    setSelectedConcerns(Array.isArray(profile?.concerns) ? profile.concerns : [])
    setSelectedComfortStyle(Array.isArray(profile?.comfort_style) ? profile.comfort_style : [])
    setOnboardingErrorMessage(null)
    setIsOnboardingStateLoading(false)
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

    try {
      await signUpWithPassword(loginEmail, loginPassword, signupDisplayName.trim())
      setAuthSuccessMessage("회원가입이 완료되었습니다. 이제 같은 계정으로 로그인해 주세요.")
      setAuthErrorMessage(null)
      setSignupDisplayName("")
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
      const { error } = await supabase.auth.updateUser({
        data: {
          onboarding_completed: true,
          onboarding_profile: {
            concerns: selectedConcerns,
            comfort_style: selectedComfortStyle,
            collected_at: new Date().toISOString(),
          },
        },
      })

      if (error) {
        throw error
      }

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
    setLoginPassword("")
    setCurrentSessionId(null)
    setSyncWarningMessage(null)
  }

  const handleSocialLogin = async (provider: "google" | "kakao") => {
    try {
      await signInWithOAuth(provider)
    } catch {
      return
    }
  }

  const handleStartNewSession = () => {
    setPreSurveyMood(null)
    setSyncWarningMessage(null)
    setShowPreSurvey(true)
  }

  const handlePreSurveyComplete = async () => {
    if (!preSurveyMood) return

    let initialCounselingMessage = "안녕하세요, 저는 무드픽 상담사입니다. 오늘 하루 어떠셨나요? 편하게 이야기해 주세요."

    try {
      const createdSessionId = await startCounselingSession()
      setCurrentSessionId(createdSessionId)

      if (createdSessionId) {
        await saveSurveyResponse(createdSessionId, "pre", preSurveyMood)
        const initialResponse = await getInitialCounselingMessage(createdSessionId)
        if (initialResponse?.message) {
          initialCounselingMessage = initialResponse.message
        }
      }
    } catch {
      setSyncWarningMessage("세션 또는 사전 문진 저장에 실패했어요. 일단 로컬 화면 흐름으로 진행할게요.")
    }

    setShowPreSurvey(false)
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
  }

  const handleEndSession = () => {
    setShowPostSurvey(true)
  }

  const handlePostSurveyComplete = async () => {
    if (!postSurveyMood) return

    const endedSessionId = currentSessionId

    if (currentSessionId) {
      try {
        await saveSurveyResponse(currentSessionId, "post", postSurveyMood)
        await endCounselingSession(currentSessionId)

        const deltaResponse = await getSurveyDelta(currentSessionId)
        if (deltaResponse?.delta && typeof deltaResponse.delta === "object") {
          const values = Object.values(deltaResponse.delta) as number[]
          const averageDelta = values.length
            ? values.reduce((sum, value) => sum + value, 0) / values.length
            : 0

          setLastSurveyDelta({
            sessionId: currentSessionId,
            averageDelta,
            improved: Boolean(deltaResponse.improved),
          })
        }
      } catch {
        setSyncWarningMessage("사후 문진 또는 세션 종료 저장에 실패했어요. Supabase 설정 후 다시 확인해 주세요.")
      }
    }

    setShowPostSurvey(false)
    setIsSessionActive(false)
    setCurrentSessionId(null)
    setPostSurveyMood(null)
    setPreSurveyMood(null)
    setMediaFeedback(null)
    setActiveTab(endedSessionId ? "dashboard" : "home")
  }

  const handleMediaFeedbackChange = async (feedback: "like" | "dislike") => {
    setMediaFeedback(feedback)

    if (!currentSessionId) {
      return
    }

    try {
      await saveContentFeedback({
        sessionId: currentSessionId,
        feedback,
        contentId: currentContent.content_id,
        contentTitle: currentContent.content_title,
        thumbnailUrl: currentContent.thumbnail_url ?? undefined,
      })
    } catch {
      setSyncWarningMessage("콘텐츠 피드백 저장에 실패했어요. Supabase 설정을 확인해 주세요.")
    }
  }

  const handleSendMessage = async () => {
    const trimmedMessage = inputMessage.trim()
    if (!trimmedMessage || isSendingMessage) return

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
    setInputMessage("")
    setIsSendingMessage(true)

    try {
      const response = user
        ? await sendCounselingMessage(user.id, trimmedMessage, currentSessionId ?? undefined)
        : null

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
      }

      setMessages((prev) => [...prev, aiResponse])
    } catch {
      setSyncWarningMessage("상담 메시지 전송에 실패했어요. 백엔드 연결 상태를 확인해 주세요.")

      const fallbackResponse: Message = {
        id: Date.now() + 1,
        sender: "ai",
        text: "현재 서버 연결이 불안정해요. 잠시 후 다시 시도해 주세요.",
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
  }

  const handleEmotionSelect = (emoji: string) => {
    setSelectedEmotion(emoji)
  }

  const handleSaveReminderPreference = async () => {
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
    const days = []
    const daysInMonth = new Date(2026, currentMonth, 0).getDate()
    const firstDay = new Date(2026, currentMonth - 1, 1).getDay()

    for (let i = 0; i < firstDay; i++) {
      days.push(null)
    }

    for (let i = 1; i <= daysInMonth; i++) {
      days.push(i)
    }

    return days
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
        password={loginPassword}
        setPassword={setLoginPassword}
        onLogin={handleLogin}
        onSignUp={handleSignUp}
        onSocialLogin={handleSocialLogin}
        isAuthLoading={isAuthLoading}
        authErrorMessage={authErrorMessage}
        authSuccessMessage={authSuccessMessage}
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
  if (!hasCompletedOnboarding) {
    return (
      <OnboardingScreen
        selectedConcerns={selectedConcerns}
        setSelectedConcerns={setSelectedConcerns}
        selectedComfortStyle={selectedComfortStyle}
        setSelectedComfortStyle={setSelectedComfortStyle}
        onComplete={handleCompleteOnboarding}
        isSaving={isSavingOnboarding}
        errorMessage={onboardingErrorMessage}
      />
    )
  }

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <aside className="w-64 bg-sidebar border-r border-sidebar-border flex flex-col">
        <div className="p-6 border-b border-sidebar-border">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center">
              <Heart className="w-5 h-5 text-primary-foreground" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-sidebar-foreground">무드픽</h1>
              <p className="text-xs text-muted-foreground">MoodPick</p>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-4">
          <ul className="space-y-2">
            {navItems.map((item) => (
              <li key={item.id}>
                <button
                  onClick={() => setActiveTab(item.id)}
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
                오늘도 당신의 마음을 응원합니다
              </p>
            </CardContent>
          </Card>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        {activeTab === "home" && (
          <HomeView
            emotions={emotions}
            selectedEmotion={selectedEmotion}
            onEmotionSelect={handleEmotionSelect}
            onStartNewSession={handleStartNewSession}
            userStats={userStats}
            emotionSummary={emotionSummary}
            currentContent={currentContent}
          />
        )}
        {/* Pre-Survey Overlay */}
        {showPreSurvey && (
          <PreSurveyOverlay
            selectedMood={preSurveyMood}
            setSelectedMood={setPreSurveyMood}
            onStart={handlePreSurveyComplete}
            onClose={() => setShowPreSurvey(false)}
          />
        )}
        {/* Post-Survey Overlay */}
        {showPostSurvey && (
          <PostSurveyOverlay
            selectedMood={postSurveyMood}
            setSelectedMood={setPostSurveyMood}
            onComplete={handlePostSurveyComplete}
          />
        )}
        {activeTab === "counseling" && (
          <CounselingView
            messages={messages}
            inputMessage={inputMessage}
            setInputMessage={setInputMessage}
            onSendMessage={handleSendMessage}
            isSendingMessage={isSendingMessage}
            isPlaying={isPlaying}
            setIsPlaying={setIsPlaying}
            mediaFeedback={mediaFeedback}
            onMediaFeedbackChange={handleMediaFeedbackChange}
            onEndSession={handleEndSession}
            onStartNewSession={handleStartNewSession}
            isSessionActive={isSessionActive}
            syncWarningMessage={syncWarningMessage}
            currentContent={currentContent}
            recommendedQueue={recommendedQueue}
            onSelectRecommendedContent={setCurrentContent}
          />
        )}
        {activeTab === "dashboard" && (
          <DashboardView
            currentMonth={currentMonth}
            setCurrentMonth={setCurrentMonth}
            getDaysInMonth={getDaysInMonth}
            calendarMoods={calendarMoods}
            emotionData={emotionData}
            sessionHistory={sessionHistory}
            contentHistory={contentHistory}
            lastSurveyDelta={lastSurveyDelta}
            userStats={userStats}
          />
        )}
        {activeTab === "mypage" && (
          <MyPageView
            autoPlayEnabled={autoPlayEnabled}
            setAutoPlayEnabled={setAutoPlayEnabled}
            mediaPreference={mediaPreference}
            setMediaPreference={setMediaPreference}
            onLogout={handleLogout}
            userEmail={user?.email ?? "-"}
            displayName={(user?.user_metadata?.display_name as string | undefined) ?? null}
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
          />
        )}
      </main>
    </div>
  )
}

function HomeView({
  emotions,
  selectedEmotion,
  onEmotionSelect,
  onStartNewSession,
  userStats,
  emotionSummary,
  currentContent,
}: {
  emotions: Emotion[]
  selectedEmotion: string | null
  onEmotionSelect: (emoji: string) => void
  onStartNewSession: () => void
  userStats: UserStats | null
  emotionSummary: EmotionSummary | null
  currentContent: ContentHistoryItem
}) {
  const weeklyMoodEmoji = scoreToEmoji(emotionSummary?.average_score ?? 3)

  return (
    <div className="p-8 max-w-4xl mx-auto">
      {/* Greeting Section */}
      <div className="mb-10">
        <h2 className="text-3xl font-bold text-foreground mb-3 text-balance">
          오늘 하루, 당신의 마음은 어떤 색인가요?
        </h2>
        <p className="text-muted-foreground text-lg">
          지금 느끼는 감정을 선택해 주세요
        </p>
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

      {/* Emotion Selection */}
      <div className="mb-10">
        <div className="grid grid-cols-5 gap-4">
          {emotions.map((emotion) => (
            <button
              key={emotion.emoji}
              onClick={() => onEmotionSelect(emotion.emoji)}
              className={`flex flex-col items-center justify-center p-6 rounded-2xl border-2 transition-all duration-200 ${
                emotion.color
              } ${
                selectedEmotion === emotion.emoji
                  ? "ring-2 ring-primary ring-offset-2 scale-105"
                  : "hover:scale-105"
              }`}
            >
              <span className="text-4xl mb-2">{emotion.emoji}</span>
              <span className="text-sm font-medium text-foreground">{emotion.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Today's Care */}
      <Card className="overflow-hidden shadow-lg border-0 bg-card">
        <CardHeader className="bg-primary/5 border-b border-border">
          <CardTitle className="text-lg flex items-center gap-2 text-foreground">
            <Heart className="w-5 h-5 text-primary" />
            오늘의 맞춤 위로 콘텐츠
          </CardTitle>
        </CardHeader>
        <CardContent className="p-6">
          <div className="flex gap-6">
            <div className="w-48 h-32 rounded-xl bg-muted flex items-center justify-center overflow-hidden">
              <div className="text-center">
                <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-2">
                  <Play className="w-6 h-6 text-primary" />
                </div>
                <p className="text-xs text-muted-foreground">썸네일</p>
              </div>
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
              <Button className="w-fit mt-4 rounded-xl">
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
            <p className="text-3xl font-bold text-primary mb-1">{userStats?.total_content_watched ?? 0}</p>
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

function CounselingView({
  messages,
  inputMessage,
  setInputMessage,
  onSendMessage,
  isSendingMessage,
  isPlaying,
  setIsPlaying,
  mediaFeedback,
  onMediaFeedbackChange,
  onEndSession,
  onStartNewSession,
  isSessionActive,
  syncWarningMessage,
  currentContent,
  recommendedQueue,
  onSelectRecommendedContent,
}: {
  messages: Message[]
  inputMessage: string
  setInputMessage: (value: string) => void
  onSendMessage: () => Promise<void>
  isSendingMessage: boolean
  isPlaying: boolean
  setIsPlaying: (value: boolean) => void
  mediaFeedback: "like" | "dislike" | null
  onMediaFeedbackChange: (value: "like" | "dislike") => void
  onEndSession: () => void
  onStartNewSession: () => void
  isSessionActive: boolean
  syncWarningMessage: string | null
  currentContent: ContentHistoryItem
  recommendedQueue: ContentHistoryItem[]
  onSelectRecommendedContent: (value: ContentHistoryItem) => void
}) {
  return (
    <div className="flex h-full">
      {/* Chat Section */}
      <div className="flex-1 flex flex-col border-r border-border">
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

        <ScrollArea className="flex-1 p-4">
          <div className="space-y-4">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${message.sender === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                    message.sender === "user"
                      ? "bg-primary text-primary-foreground rounded-br-md"
                      : "bg-muted text-foreground rounded-bl-md"
                  }`}
                >
                  <p className="text-sm leading-relaxed">{message.text}</p>
                  <p
                    className={`text-xs mt-1 ${
                      message.sender === "user" ? "text-primary-foreground/70" : "text-muted-foreground"
                    }`}
                  >
                    {message.timestamp}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </ScrollArea>

        <div className="p-4 border-t border-border bg-card">
          <div className="flex gap-3 mb-3">
            <Input
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              placeholder="메시지를 입력하세요..."
              className="flex-1 rounded-xl bg-muted border-0"
              onKeyDown={(e) => e.key === "Enter" && void onSendMessage()}
            />
            <Button onClick={() => void onSendMessage()} size="icon" className="rounded-xl" disabled={isSendingMessage}>
              <Send className={`w-4 h-4 ${isSendingMessage ? "opacity-50" : ""}`} />
            </Button>
          </div>
          {isSessionActive && (
            <Button
              onClick={onEndSession}
              variant="outline"
              className="w-full rounded-xl border-destructive text-destructive hover:bg-destructive hover:text-destructive-foreground"
            >
              오늘의 상담 종료하기
            </Button>
          )}
        </div>
      </div>

      {/* Media Player Section */}
      <div className="w-96 bg-card p-6">
        <div className="mb-6">
          <h3 className="text-lg font-semibold text-foreground mb-1">자동 추천 콘텐츠</h3>
          <p className="text-sm text-muted-foreground">
            대화 내용을 바탕으로 AI가 추천해 드려요
          </p>
        </div>

        {/* Video Player Mockup */}
        <Card className="overflow-hidden border-0 shadow-lg">
          <div className="aspect-video bg-foreground/90 relative flex items-center justify-center">
            {/* Fullscreen Toggle */}
            <button className="absolute top-2 right-2 z-10 p-2 rounded-lg bg-foreground/30 hover:bg-foreground/50 transition-colors">
              <Maximize2 className="w-4 h-4 text-primary-foreground" />
            </button>
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center text-primary-foreground">
                <Flame className="w-16 h-16 mx-auto mb-2 opacity-80" />
                <p className="text-sm opacity-70">영상 재생 중...</p>
              </div>
            </div>
            {!isPlaying && (
              <div className="absolute inset-0 bg-foreground/50 flex items-center justify-center">
                <Play className="w-16 h-16 text-primary-foreground" />
              </div>
            )}
          </div>
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-3">
              <span className="px-2 py-1 bg-primary/10 text-primary text-xs rounded-full font-medium">
                재생 중
              </span>
            </div>
            <h4 className="font-medium text-foreground mb-2">
              {currentContent.content_title}
            </h4>
            <p className="text-sm text-muted-foreground mb-4">
              최근 사용자 반응 기반으로 우선 노출된 콘텐츠입니다.
            </p>

            {/* Progress Bar */}
            <div className="mb-4">
              <div className="h-1 bg-muted rounded-full overflow-hidden">
                <div className="h-full w-1/3 bg-primary rounded-full" />
              </div>
              <div className="flex justify-between text-xs text-muted-foreground mt-1">
                <span>12:34</span>
                <span>45:00</span>
              </div>
            </div>

            {/* Controls */}
            <div className="flex items-center justify-center gap-4">
              <Button variant="ghost" size="icon" className="rounded-full">
                <Volume2 className="w-5 h-5" />
              </Button>
              <Button
                onClick={() => setIsPlaying(!isPlaying)}
                size="icon"
                className="w-12 h-12 rounded-full"
              >
                {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
              </Button>
              <Button variant="ghost" size="icon" className="rounded-full">
                <SkipForward className="w-5 h-5" />
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Lightweight Feedback Section */}
        <div className="mt-4 p-4 rounded-xl bg-secondary/30">
          <p className="text-sm text-center text-muted-foreground mb-3">
            이 콘텐츠가 도움이 되었나요?
          </p>
          <div className="flex items-center justify-center gap-4">
            <Button
              variant={mediaFeedback === "like" ? "default" : "outline"}
              onClick={() => onMediaFeedbackChange("like")}
              className="rounded-xl px-6"
            >
              <ThumbsUp className="w-4 h-4 mr-2" />
              좋아요
            </Button>
            <Button
              variant={mediaFeedback === "dislike" ? "default" : "outline"}
              onClick={() => onMediaFeedbackChange("dislike")}
              className="rounded-xl px-6"
            >
              <ThumbsDown className="w-4 h-4 mr-2" />
              아쉬워요
            </Button>
          </div>
          {syncWarningMessage && (
            <p className="mt-3 text-xs text-center text-destructive">{syncWarningMessage}</p>
          )}
        </div>

        {/* Recommended Queue */}
        <div className="mt-6">
          <h4 className="text-sm font-medium text-foreground mb-3">다음 추천 콘텐츠</h4>
          <div className="space-y-3">
            {recommendedQueue.map((content, idx) => (
              <div
                key={content.id}
                onClick={() => onSelectRecommendedContent(content)}
                className="flex items-center gap-3 p-3 rounded-xl bg-muted/50 hover:bg-muted transition-colors cursor-pointer"
              >
                <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center">
                  <Play className="w-4 h-4 text-primary" />
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium text-foreground">{content.content_title}</p>
                  <p className="text-xs text-muted-foreground">
                    {idx === 0 ? "추천 우선" : "다음 추천"}
                  </p>
                </div>
              </div>
            ))}
            {recommendedQueue.length === 0 && (
              <p className="text-sm text-muted-foreground">추천 대기열이 아직 없습니다.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function DashboardView({
  currentMonth,
  setCurrentMonth,
  getDaysInMonth,
  calendarMoods,
  emotionData,
  sessionHistory,
  contentHistory,
  lastSurveyDelta,
  userStats,
}: {
  currentMonth: number
  setCurrentMonth: (value: number) => void
  getDaysInMonth: () => (number | null)[]
  calendarMoods: Record<number, { emoji: string; color: string }>
  emotionData: { date: string; score: number; label: string }[]
  sessionHistory: SessionHistory[]
  contentHistory: ContentHistoryItem[]
  lastSurveyDelta: SurveyDeltaSummary | null
  userStats: UserStats | null
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
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  onClick={() => setCurrentMonth(Math.max(1, currentMonth - 1))}
                >
                  <ChevronLeft className="w-4 h-4" />
                </Button>
                <span className="text-sm font-medium min-w-[80px] text-center">
                  2026년 {currentMonth}월
                </span>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  onClick={() => setCurrentMonth(Math.min(12, currentMonth + 1))}
                >
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
                <div
                  key={idx}
                  className={`aspect-square flex flex-col items-center justify-center rounded-lg text-sm ${
                    day && calendarMoods[day]
                      ? `${calendarMoods[day].color}`
                      : day
                      ? "bg-muted/30 hover:bg-muted"
                      : ""
                  }`}
                >
                  {day && (
                    <>
                      <span className="text-xs text-foreground">{day}</span>
                      {calendarMoods[day] && (
                        <span className="text-xs">{calendarMoods[day].emoji}</span>
                      )}
                    </>
                  )}
                </div>
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
            </div>
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
                className="flex-shrink-0 w-48 group cursor-pointer"
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
              <Card key={session.id} className="border border-border bg-muted/30">
                <CardContent className="p-4">
                  <p className="text-sm text-muted-foreground mb-2">{session.date}</p>
                  <div className="mb-3">
                    <p className="text-xs text-muted-foreground mb-1">주요 고민</p>
                    <p className="font-medium text-foreground">{session.concern}</p>
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
  password,
  setPassword,
  onLogin,
  onSignUp,
  onSocialLogin,
  isAuthLoading,
  authErrorMessage,
  authSuccessMessage,
}: {
  email: string
  setEmail: (value: string) => void
  displayName: string
  setDisplayName: (value: string) => void
  password: string
  setPassword: (value: string) => void
  onLogin: () => Promise<void>
  onSignUp: () => Promise<void>
  onSocialLogin: (provider: "google" | "kakao") => Promise<void>
  isAuthLoading: boolean
  authErrorMessage: string | null
  authSuccessMessage: string | null
}) {
  const isEmailOnlyMode = true
  const [isSignUpMode, setIsSignUpMode] = useState(false)
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
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
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
                <Input
                  id="password"
                  type="password"
                  placeholder="비밀번호를 입력하세요"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="mt-1.5 rounded-xl bg-muted border-0 h-12"
                  onKeyDown={(e) => e.key === "Enter" && handleAuthSubmit()}
                />
              </div>
              {isSignUpMode && (
                <div>
                  <Label htmlFor="confirm-password" className="text-sm text-muted-foreground">
                    비밀번호 확인
                  </Label>
                  <Input
                    id="confirm-password"
                    type="password"
                    placeholder="비밀번호를 다시 입력하세요"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="mt-1.5 rounded-xl bg-muted border-0 h-12"
                    onKeyDown={(e) => e.key === "Enter" && handleAuthSubmit()}
                  />
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

            {isEmailOnlyMode && (
              <p className="text-xs text-center text-muted-foreground mb-2">
                현재는 이메일 로그인/회원가입만 제공됩니다. 소셜 로그인은 추후 추가됩니다.
              </p>
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
                }}
              >
                {isSignUpMode ? "로그인" : "회원가입"}
              </button>
            </p>
          </CardContent>
        </Card>

        {/* Footer */}
        <p className="text-center text-xs text-muted-foreground mt-6">
          로그인하면 무드픽의 이용약관 및 개인정보처리방침에 동의하게 됩니다.
        </p>
      </div>
    </div>
  )
}

function OnboardingScreen({
  selectedConcerns,
  setSelectedConcerns,
  selectedComfortStyle,
  setSelectedComfortStyle,
  onComplete,
  isSaving,
  errorMessage,
}: {
  selectedConcerns: string[]
  setSelectedConcerns: (value: string[]) => void
  selectedComfortStyle: string[]
  setSelectedComfortStyle: (value: string[]) => void
  onComplete: () => void
  isSaving: boolean
  errorMessage: string | null
}) {
  const concerns = [
    { id: "study", label: "학업/취업" },
    { id: "relationship", label: "인간관계" },
    { id: "future", label: "미래에 대한 불안" },
    { id: "work", label: "업무 스트레스" },
    { id: "other", label: "기타" },
  ]

  const comfortStyles = [
    { id: "listen", label: "조용히 들어주기" },
    { id: "advice", label: "현실적인 조언" },
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

  const toggleComfortStyle = (id: string) => {
    if (selectedComfortStyle.includes(id)) {
      setSelectedComfortStyle(selectedComfortStyle.filter((s) => s !== id))
    } else {
      setSelectedComfortStyle([...selectedComfortStyle, id])
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
            <div className="mb-8">
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

            {/* Question 2 */}
            <div className="mb-8">
              <h3 className="text-base font-semibold text-foreground mb-3">
                어떤 방식의 위로를 선호하시나요?
              </h3>
              <p className="text-xs text-muted-foreground mb-4">
                여러 개를 선택할 수 있어요
              </p>
              <div className="flex flex-wrap gap-2">
                {comfortStyles.map((style) => (
                  <button
                    key={style.id}
                    onClick={() => toggleComfortStyle(style.id)}
                    className={`px-4 py-2 rounded-full text-sm font-medium transition-all duration-200 ${
                      selectedComfortStyle.includes(style.id)
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted text-muted-foreground hover:bg-muted/80"
                    }`}
                  >
                    {style.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Start Button */}
            <Button
              onClick={onComplete}
              className="w-full h-12 rounded-xl text-base font-medium"
              disabled={(selectedConcerns.length === 0 && selectedComfortStyle.length === 0) || isSaving}
            >
              {isSaving ? "저장 중..." : "시작하기"}
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

function MyPageView({
  autoPlayEnabled,
  setAutoPlayEnabled,
  mediaPreference,
  setMediaPreference,
  onLogout,
  userEmail,
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
}: {
  autoPlayEnabled: boolean
  setAutoPlayEnabled: (value: boolean) => void
  mediaPreference: string
  setMediaPreference: (value: string) => void
  onLogout: () => void
  userEmail: string
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
}) {
  const joinedAtText = userCreatedAt
    ? new Date(userCreatedAt).toLocaleDateString("ko-KR", {
        year: "numeric",
        month: "long",
        day: "numeric",
      })
    : "-"

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-foreground mb-2">마이페이지</h2>
        <p className="text-muted-foreground">계정 설정 및 환경설정을 관리하세요</p>
      </div>

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
            <div className="flex-1">
              <h3 className="text-xl font-semibold text-foreground mb-1">{userEmail.split("@")[0]}</h3>
              <p className="text-muted-foreground">{userEmail}</p>
              <div className="flex items-center gap-2 mt-3">
                <span className="px-3 py-1 bg-primary/10 text-primary text-xs rounded-full font-medium">
                  일반 회원
                </span>
                <span className="text-xs text-muted-foreground">
                  가입일: {joinedAtText}
                </span>
              </div>
            </div>
            <Button variant="outline" className="rounded-xl">
              프로필 수정
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Preferences Section */}
      <Card className="border-0 shadow-lg mb-6">
        <CardHeader>
          <CardTitle className="text-lg">맞춤 설정</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Auto-play Toggle */}
          <div className="flex items-center justify-between">
            <div>
              <Label htmlFor="autoplay" className="text-base font-medium text-foreground">
                콘텐츠 자동 재생 허용
              </Label>
              <p className="text-sm text-muted-foreground mt-1">
                AI 상담 중 추천 콘텐츠를 자동으로 재생합니다
              </p>
            </div>
            <Switch
              id="autoplay"
              checked={autoPlayEnabled}
              onCheckedChange={setAutoPlayEnabled}
            />
          </div>

          {/* Media Preference */}
          <div>
            <Label className="text-base font-medium text-foreground">
              선호 미디어 유형
            </Label>
            <p className="text-sm text-muted-foreground mt-1 mb-3">
              추천받고 싶은 콘텐츠 유형을 선택하세요
            </p>
            <Select value={mediaPreference} onValueChange={setMediaPreference}>
              <SelectTrigger className="w-full rounded-xl bg-muted border-0 h-12">
                <SelectValue placeholder="미디어 유형 선택" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="youtube">YouTube 영상 위주</SelectItem>
                <SelectItem value="spotify">Spotify 음악 위주</SelectItem>
                <SelectItem value="podcast">팟캐스트 위주</SelectItem>
                <SelectItem value="mixed">혼합 추천</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="rounded-xl border border-border p-4 space-y-3">
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
          <div className="flex items-center justify-between p-4 bg-muted/50 rounded-xl">
            <div>
              <p className="font-medium text-foreground">내 상담 기록</p>
              <p className="text-sm text-muted-foreground">
                총 {totalSessions}회의 상담 기록이 저장되어 있습니다
              </p>
            </div>
            <Button variant="outline" className="rounded-xl">
              기록 내보내기
            </Button>
          </div>

          <div className="flex items-center justify-between p-4 bg-destructive/5 rounded-xl border border-destructive/20">
            <div>
              <p className="font-medium text-foreground">내 상담 기록 초기화</p>
              <p className="text-sm text-muted-foreground">
                모든 상담 기록과 감정 데이터가 영구적으로 삭제됩니다
              </p>
            </div>
            <Button
              variant="outline"
              className="rounded-xl border-destructive text-destructive hover:bg-destructive hover:text-destructive-foreground"
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

const surveyMoodOptions = [
  { emoji: "😊", label: "아주 좋아요", value: "great" },
  { emoji: "🙂", label: "괜찮아요", value: "good" },
  { emoji: "😐", label: "그저 그래요", value: "neutral" },
  { emoji: "😔", label: "조금 힘들어요", value: "low" },
  { emoji: "😢", label: "많이 힘들어요", value: "bad" },
]

function PreSurveyOverlay({
  selectedMood,
  setSelectedMood,
  onStart,
  onClose,
}: {
  selectedMood: string | null
  setSelectedMood: (value: string | null) => void
  onStart: () => void
  onClose: () => void
}) {
  return (
    <div className="fixed inset-0 z-50 bg-background/95 backdrop-blur-sm flex items-center justify-center p-4">
      <Card className="w-full max-w-lg border-0 shadow-2xl">
        <CardContent className="p-8">
          {/* Close Button */}
          <button
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
            <p className="text-muted-foreground">상담 시작 전, 지금의 마음 상태를 알려주세요</p>
          </div>

          {/* Question */}
          <div className="mb-8">
            <h3 className="text-lg font-semibold text-center text-foreground mb-6">
              지금 마음의 온도는 어떤가요?
            </h3>
            <div className="flex flex-wrap justify-center gap-3">
              {surveyMoodOptions.map((option) => (
                <button
                  key={option.value}
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

          {/* Start Button */}
          <Button
            onClick={onStart}
            disabled={!selectedMood}
            className="w-full h-12 rounded-xl text-base font-medium"
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
  onComplete,
}: {
  selectedMood: string | null
  setSelectedMood: (value: string | null) => void
  onComplete: () => void
}) {
  return (
    <div className="fixed inset-0 z-50 bg-background/95 backdrop-blur-sm flex items-center justify-center p-4">
      <Card className="w-full max-w-lg border-0 shadow-2xl">
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
              {surveyMoodOptions.map((option) => (
                <button
                  key={option.value}
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
            onClick={onComplete}
            disabled={!selectedMood}
            className="w-full h-12 rounded-xl text-base font-medium"
          >
            완료 및 홈으로
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
