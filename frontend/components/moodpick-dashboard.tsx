"use client"

import { useState } from "react"
import {
  Home,
  MessageCircle,
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

const emotions: Emotion[] = [
  { emoji: "😊", label: "기쁨", color: "bg-amber-100 hover:bg-amber-200 border-amber-300" },
  { emoji: "😐", label: "평온", color: "bg-sky-100 hover:bg-sky-200 border-sky-300" },
  { emoji: "😢", label: "슬픔", color: "bg-blue-100 hover:bg-blue-200 border-blue-300" },
  { emoji: "😡", label: "분노", color: "bg-rose-100 hover:bg-rose-200 border-rose-300" },
  { emoji: "😫", label: "불안", color: "bg-orange-100 hover:bg-orange-200 border-orange-300" },
]

const initialMessages: Message[] = [
  {
    id: 1,
    sender: "ai",
    text: "안녕하세요, 저는 무드픽 상담사입니다. 오늘 하루 어떠셨나요? 편하게 이야기해 주세요.",
    timestamp: "오후 2:30",
  },
  {
    id: 2,
    sender: "user",
    text: "요즘 스트레스를 많이 받아서 힘들어요. 잠도 잘 못 자고...",
    timestamp: "오후 2:32",
  },
  {
    id: 3,
    sender: "ai",
    text: "많이 힘드셨군요. 스트레스와 수면 문제가 함께 오면 정말 지치시죠. 어떤 상황이 가장 스트레스를 주나요? 그리고 지금 기분을 달래줄 편안한 음악을 틀어드릴게요.",
    timestamp: "오후 2:33",
  },
]

const emotionData = [
  { date: "3/1", score: 65, label: "기쁨" },
  { date: "3/5", score: 45, label: "평온" },
  { date: "3/10", score: 30, label: "슬픔" },
  { date: "3/15", score: 55, label: "평온" },
  { date: "3/20", score: 70, label: "기쁨" },
  { date: "3/22", score: 60, label: "평온" },
]

const sessionHistory: SessionHistory[] = [
  {
    id: 1,
    date: "2026년 3월 20일",
    concern: "학업 스트레스",
    media: "집중력을 높이는 로파이 음악",
  },
  {
    id: 2,
    date: "2026년 3월 15일",
    concern: "대인관계 고민",
    media: "자존감을 높이는 명상 가이드",
  },
  {
    id: 3,
    date: "2026년 3월 10일",
    concern: "불면증",
    media: "숙면을 위한 ASMR 빗소리",
  },
]

const calendarMoods: Record<number, { emoji: string; color: string }> = {
  1: { emoji: "😊", color: "bg-amber-200" },
  3: { emoji: "😐", color: "bg-sky-200" },
  5: { emoji: "😢", color: "bg-blue-200" },
  8: { emoji: "😊", color: "bg-amber-200" },
  10: { emoji: "😫", color: "bg-orange-200" },
  12: { emoji: "😐", color: "bg-sky-200" },
  15: { emoji: "😊", color: "bg-amber-200" },
  18: { emoji: "😐", color: "bg-sky-200" },
  20: { emoji: "😊", color: "bg-amber-200" },
  22: { emoji: "😐", color: "bg-sky-200" },
}

export function MoodPickDashboard() {
  const [isLoggedIn, setIsLoggedIn] = useState(false)
  const [hasCompletedOnboarding, setHasCompletedOnboarding] = useState(false)
  const [activeTab, setActiveTab] = useState<TabType>("home")
  const [messages, setMessages] = useState<Message[]>(initialMessages)
  const [inputMessage, setInputMessage] = useState("")
  const [selectedEmotion, setSelectedEmotion] = useState<string | null>(null)
  const [isPlaying, setIsPlaying] = useState(true)
  const [currentMonth, setCurrentMonth] = useState(3)
  const [contentFeedback, setContentFeedback] = useState<string | null>(null)

  // Login form state
  const [loginEmail, setLoginEmail] = useState("")
  const [loginPassword, setLoginPassword] = useState("")

  // Onboarding state
  const [selectedConcerns, setSelectedConcerns] = useState<string[]>([])
  const [selectedComfortStyle, setSelectedComfortStyle] = useState<string[]>([])

  // My page settings state
  const [autoPlayEnabled, setAutoPlayEnabled] = useState(true)
  const [mediaPreference, setMediaPreference] = useState("youtube")

  const handleLogin = () => {
    if (loginEmail && loginPassword) {
      setIsLoggedIn(true)
    }
  }

  const handleCompleteOnboarding = () => {
    setHasCompletedOnboarding(true)
  }

  const handleLogout = () => {
    setIsLoggedIn(false)
    setLoginEmail("")
    setLoginPassword("")
  }

  const handleSendMessage = () => {
    if (!inputMessage.trim()) return

    const newMessage: Message = {
      id: messages.length + 1,
      sender: "user",
      text: inputMessage,
      timestamp: new Date().toLocaleTimeString("ko-KR", {
        hour: "numeric",
        minute: "2-digit",
        hour12: true,
      }),
    }

    setMessages([...messages, newMessage])
    setInputMessage("")

    setTimeout(() => {
      const aiResponse: Message = {
        id: messages.length + 2,
        sender: "ai",
        text: "말씀해 주셔서 감사해요. 그런 감정을 느끼시는 게 충분히 이해가 돼요. 잠시 마음을 진정시킬 수 있는 영상을 추천해 드릴게요.",
        timestamp: new Date().toLocaleTimeString("ko-KR", {
          hour: "numeric",
          minute: "2-digit",
          hour12: true,
        }),
      }
      setMessages((prev) => [...prev, aiResponse])
    }, 1500)
  }

  const handleEmotionSelect = (emoji: string) => {
    setSelectedEmotion(emoji)
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

  // Show login screen if not logged in
  if (!isLoggedIn) {
    return (
      <LoginScreen
        email={loginEmail}
        setEmail={setLoginEmail}
        password={loginPassword}
        setPassword={setLoginPassword}
        onLogin={handleLogin}
      />
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
          />
        )}
        {activeTab === "counseling" && (
          <CounselingView
            messages={messages}
            inputMessage={inputMessage}
            setInputMessage={setInputMessage}
            onSendMessage={handleSendMessage}
            isPlaying={isPlaying}
            setIsPlaying={setIsPlaying}
            contentFeedback={contentFeedback}
            setContentFeedback={setContentFeedback}
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
          />
        )}
        {activeTab === "mypage" && (
          <MyPageView
            autoPlayEnabled={autoPlayEnabled}
            setAutoPlayEnabled={setAutoPlayEnabled}
            mediaPreference={mediaPreference}
            setMediaPreference={setMediaPreference}
            onLogout={handleLogout}
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
}: {
  emotions: Emotion[]
  selectedEmotion: string | null
  onEmotionSelect: (emoji: string) => void
}) {
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
                  마음을 편안하게 하는 자연 소리 모음
                </h3>
                <p className="text-muted-foreground text-sm leading-relaxed">
                  바쁜 일상 속에서 잠시 멈추고, 자연의 소리로 마음의 평화를 찾아보세요.
                  숲속 새소리와 시냇물 소리가 당신의 하루를 치유해 드립니다.
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
            <p className="text-3xl font-bold text-primary mb-1">7</p>
            <p className="text-sm text-muted-foreground">이번 주 기록일</p>
          </CardContent>
        </Card>
        <Card className="border-0 bg-secondary/50">
          <CardContent className="p-6 text-center">
            <p className="text-3xl font-bold text-primary mb-1">12</p>
            <p className="text-sm text-muted-foreground">총 상담 횟수</p>
          </CardContent>
        </Card>
        <Card className="border-0 bg-secondary/50">
          <CardContent className="p-6 text-center">
            <p className="text-3xl font-bold text-primary mb-1">😊</p>
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
  isPlaying,
  setIsPlaying,
  contentFeedback,
  setContentFeedback,
}: {
  messages: Message[]
  inputMessage: string
  setInputMessage: (value: string) => void
  onSendMessage: () => void
  isPlaying: boolean
  setIsPlaying: (value: boolean) => void
  contentFeedback: string | null
  setContentFeedback: (value: string | null) => void
}) {
  const feedbackOptions = [
    { emoji: "love", label: "아주 좋아요" },
    { emoji: "good", label: "조금 나아졌어요" },
    { emoji: "neutral", label: "그저 그래요" },
    { emoji: "sad", label: "아쉬워요" },
  ]
  return (
    <div className="flex h-full">
      {/* Chat Section */}
      <div className="flex-1 flex flex-col border-r border-border">
        <div className="p-4 border-b border-border bg-card">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-primary flex items-center justify-center">
              <MessageCircle className="w-5 h-5 text-primary-foreground" />
            </div>
            <div>
              <h3 className="font-semibold text-foreground">무드픽 상담사</h3>
              <p className="text-xs text-muted-foreground">AI 심리 상담</p>
            </div>
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
          <div className="flex gap-3">
            <Input
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              placeholder="메시지를 입력하세요..."
              className="flex-1 rounded-xl bg-muted border-0"
              onKeyDown={(e) => e.key === "Enter" && onSendMessage()}
            />
            <Button onClick={onSendMessage} size="icon" className="rounded-xl">
              <Send className="w-4 h-4" />
            </Button>
          </div>
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
              우울함을 달래주는 따뜻한 장작 소리
            </h4>
            <p className="text-sm text-muted-foreground mb-4">
              포근한 벽난로 옆에서 마음의 위안을 찾아보세요
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

        {/* Content Feedback Section */}
        <Card className="border-0 shadow-md mt-4 bg-secondary/30">
          <CardContent className="p-4">
            <p className="text-sm text-center text-muted-foreground mb-3">
              이 콘텐츠가 감정 환기에 도움이 되었나요?
            </p>
            <div className="flex items-center justify-center gap-2">
              {feedbackOptions.map((option) => (
                <button
                  key={option.emoji}
                  onClick={() => setContentFeedback(option.emoji)}
                  className={`flex flex-col items-center p-2 rounded-xl transition-all duration-200 ${
                    contentFeedback === option.emoji
                      ? "bg-primary/10 ring-2 ring-primary scale-105"
                      : "hover:bg-muted"
                  }`}
                >
                  <span className="text-2xl mb-1">
                    {option.emoji === "love" && "\uD83D\uDE0D"}
                    {option.emoji === "good" && "\uD83D\uDE42"}
                    {option.emoji === "neutral" && "\uD83D\uDE10"}
                    {option.emoji === "sad" && "\uD83D\uDE14"}
                  </span>
                  <span className="text-xs text-muted-foreground whitespace-nowrap">
                    {option.label}
                  </span>
                </button>
              ))}
            </div>
            {contentFeedback && (
              <p className="text-xs text-center text-primary mt-3 font-medium">
                피드백을 보내주셔서 감사합니다!
              </p>
            )}
          </CardContent>
        </Card>

        {/* Recommended Queue */}
        <div className="mt-6">
          <h4 className="text-sm font-medium text-foreground mb-3">다음 추천 콘텐츠</h4>
          <div className="space-y-3">
            {["빗소리와 함께하는 명상 음악", "숲속 새소리 1시간"].map((title, idx) => (
              <div
                key={idx}
                className="flex items-center gap-3 p-3 rounded-xl bg-muted/50 hover:bg-muted transition-colors cursor-pointer"
              >
                <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center">
                  <Play className="w-4 h-4 text-primary" />
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium text-foreground">{title}</p>
                  <p className="text-xs text-muted-foreground">
                    {idx === 0 ? "30:00" : "1:00:00"}
                  </p>
                </div>
              </div>
            ))}
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
}: {
  currentMonth: number
  setCurrentMonth: (value: number) => void
  getDaysInMonth: () => (number | null)[]
  calendarMoods: Record<number, { emoji: string; color: string }>
  emotionData: { date: string; score: number; label: string }[]
  sessionHistory: SessionHistory[]
}) {
  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-foreground mb-2">나의 감정 기록</h2>
        <p className="text-muted-foreground">
          당신의 감정 여정을 한눈에 확인하세요
        </p>
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
                  } ${day === 22 ? "ring-2 ring-primary" : ""}`}
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
        </CardContent>
      </Card>
    </div>
  )
}

function LoginScreen({
  email,
  setEmail,
  password,
  setPassword,
  onLogin,
}: {
  email: string
  setEmail: (value: string) => void
  password: string
  setPassword: (value: string) => void
  onLogin: () => void
}) {
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
                  onKeyDown={(e) => e.key === "Enter" && onLogin()}
                />
              </div>
            </div>

            {/* Login Button */}
            <Button
              onClick={onLogin}
              className="w-full h-12 rounded-xl text-base font-medium mb-6"
            >
              로그인
            </Button>

            {/* Divider */}
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

            {/* Social Login Buttons */}
            <div className="space-y-3">
              <Button
                variant="outline"
                className="w-full h-12 rounded-xl border-2 bg-[#FEE500] hover:bg-[#FEE500]/90 border-[#FEE500] text-[#191919] font-medium"
              >
                <svg
                  className="w-5 h-5 mr-2"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                >
                  <path d="M12 3C6.477 3 2 6.463 2 10.762c0 2.753 1.814 5.173 4.563 6.572l-.862 3.193c-.06.222.2.404.392.273l3.788-2.538c.669.089 1.359.136 2.063.136 5.523 0 10-3.463 10-7.636C22 6.463 17.523 3 12 3z" />
                </svg>
                카카오로 시작하기
              </Button>
              <Button
                variant="outline"
                className="w-full h-12 rounded-xl border-2 hover:bg-muted font-medium"
              >
                <svg
                  className="w-5 h-5 mr-2"
                  viewBox="0 0 24 24"
                >
                  <path
                    fill="#4285F4"
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                  />
                  <path
                    fill="#34A853"
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  />
                  <path
                    fill="#FBBC05"
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                  />
                  <path
                    fill="#EA4335"
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                  />
                </svg>
                Google로 시작하기
              </Button>
            </div>

            {/* Sign Up Link */}
            <p className="text-center text-sm text-muted-foreground mt-6">
              계정이 없으신가요?{" "}
              <button className="text-primary font-medium hover:underline">
                회원가입
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
}: {
  selectedConcerns: string[]
  setSelectedConcerns: (value: string[]) => void
  selectedComfortStyle: string[]
  setSelectedComfortStyle: (value: string[]) => void
  onComplete: () => void
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
              disabled={selectedConcerns.length === 0 && selectedComfortStyle.length === 0}
            >
              시작하기
            </Button>

            {/* Skip Option */}
            <button
              onClick={onComplete}
              className="w-full mt-4 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              나중에 설정할게요
            </button>
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
}: {
  autoPlayEnabled: boolean
  setAutoPlayEnabled: (value: boolean) => void
  mediaPreference: string
  setMediaPreference: (value: string) => void
  onLogout: () => void
}) {
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
              <h3 className="text-xl font-semibold text-foreground mb-1">김학생</h3>
              <p className="text-muted-foreground">student.kim@university.ac.kr</p>
              <div className="flex items-center gap-2 mt-3">
                <span className="px-3 py-1 bg-primary/10 text-primary text-xs rounded-full font-medium">
                  일반 회원
                </span>
                <span className="text-xs text-muted-foreground">
                  가입일: 2026년 1월 15일
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
                총 12회의 상담 기록이 저장되어 있습니다
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
