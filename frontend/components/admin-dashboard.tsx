"use client"

import { useEffect, useMemo, useState } from "react"
import {
  Clock,
  Heart,
  LogOut,
  MessageCircle,
  RefreshCw,
  ThumbsDown,
  ThumbsUp,
  Users,
  Video,
} from "lucide-react"
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { useAuth } from "@/components/auth-provider"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { getAdminOverview, type AdminOverview } from "@/lib/api"
import { cn } from "@/lib/utils"


function formatNumber(value: number | null | undefined) {
  return new Intl.NumberFormat("ko-KR").format(value ?? 0)
}

function formatDateTime(value?: string | null) {
  if (!value) return "-"
  try {
    return new Date(value).toLocaleString("ko-KR", {
      month: "numeric",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    })
  } catch {
    return "-"
  }
}

function statusLabel(status?: string | null) {
  if (status === "active") return "진행 중"
  if (status === "completed") return "완료"
  return status ?? "-"
}

function metricDeltaText(overview: AdminOverview | null) {
  if (!overview) return "최근 30일 기준"
  const sessions = overview.metrics.total_sessions
  const completed = overview.metrics.completed_sessions
  if (!sessions) return "아직 세션 기록 없음"
  return `완료율 ${Math.round((completed / sessions) * 100)}%`
}

function AdminMetricCard({
  title,
  value,
  helper,
  icon: Icon,
  tone = "blue",
}: {
  title: string
  value: number
  helper: string
  icon: typeof Users
  tone?: "blue" | "green" | "amber" | "rose"
}) {
  const toneClass = {
    blue: "bg-blue-500/10 text-blue-700",
    green: "bg-emerald-500/10 text-emerald-700",
    amber: "bg-amber-500/10 text-amber-700",
    rose: "bg-rose-500/10 text-rose-700",
  }[tone]

  return (
    <Card className="border-0 shadow-sm">
      <CardContent className="flex items-center justify-between gap-4 p-5">
        <div>
          <p className="text-sm text-muted-foreground">{title}</p>
          <p className="mt-2 text-3xl font-bold tracking-tight">{formatNumber(value)}</p>
          <p className="mt-1 text-xs text-muted-foreground">{helper}</p>
        </div>
        <div className={cn("flex h-12 w-12 items-center justify-center rounded-2xl", toneClass)}>
          <Icon className="h-6 w-6" />
        </div>
      </CardContent>
    </Card>
  )
}

function EmptyPanel({ message }: { message: string }) {
  return (
    <div className="flex h-56 items-center justify-center rounded-xl bg-muted/30 text-sm text-muted-foreground">
      {message}
    </div>
  )
}

export function AdminDashboard() {
  const { user, signOut } = useAuth()
  const [overview, setOverview] = useState<AdminOverview | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const loadOverview = async () => {
    setIsLoading(true)
    setErrorMessage(null)
    try {
      setOverview(await getAdminOverview())
    } catch {
      setErrorMessage("관리자 데이터를 불러오지 못했습니다. 권한 또는 서버 상태를 확인해 주세요.")
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    void loadOverview()
  }, [])

  const feedbackRate = useMemo(() => {
    if (!overview?.metrics.feedback_30d) return 0
    return Math.round((overview.metrics.likes_30d / overview.metrics.feedback_30d) * 100)
  }, [overview])

  const dailyData = overview?.daily_activity ?? []
  const personaData = overview?.persona_distribution ?? []
  const activeSessionRate = overview?.metrics.total_sessions
    ? Math.round((overview.metrics.active_sessions / overview.metrics.total_sessions) * 100)
    : 0

  return (
    <div className="min-h-screen bg-slate-50 text-slate-950">
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-medium text-primary">MoodPick Admin</p>
            <h1 className="text-2xl font-bold tracking-tight">운영 분석 대시보드</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              관리자 계정으로 로그인되어 일반 사용자 화면 대신 이 페이지가 표시됩니다.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="rounded-full bg-muted px-3 py-1.5 text-xs text-muted-foreground">
              {user?.email ?? "관리자"}
            </div>
            <Button variant="outline" size="sm" onClick={() => void loadOverview()} disabled={isLoading}>
              <RefreshCw className={cn("mr-2 h-4 w-4", isLoading && "animate-spin")} />
              새로고침
            </Button>
            <Button variant="ghost" size="sm" onClick={() => void signOut()}>
              <LogOut className="mr-2 h-4 w-4" />
              로그아웃
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-6 px-5 py-6">
        {errorMessage && (
          <div className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            {errorMessage}
          </div>
        )}

        {isLoading && !overview ? (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {Array.from({ length: 8 }).map((_, index) => (
              <Card key={index} className="border-0 shadow-sm">
                <CardContent className="h-32 animate-pulse rounded-xl bg-muted/50" />
              </Card>
            ))}
          </div>
        ) : (
          <>
            <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <AdminMetricCard
                title="전체 사용자"
                value={overview?.metrics.total_users ?? 0}
                helper={`최근 30일 활성 ${formatNumber(overview?.metrics.active_users_30d)}`}
                icon={Users}
              />
              <AdminMetricCard
                title="전체 상담 세션"
                value={overview?.metrics.total_sessions ?? 0}
                helper={metricDeltaText(overview)}
                icon={MessageCircle}
                tone="green"
              />
              <AdminMetricCard
                title="오늘 시작된 세션"
                value={overview?.metrics.today_sessions ?? 0}
                helper={`현재 active ${formatNumber(overview?.metrics.active_sessions)}`}
                icon={Clock}
                tone="amber"
              />
              <AdminMetricCard
                title="콘텐츠 피드백"
                value={overview?.metrics.feedback_30d ?? 0}
                helper={`좋아요 비율 ${feedbackRate}%`}
                icon={Heart}
                tone="rose"
              />
              <AdminMetricCard
                title="상담 메시지"
                value={overview?.metrics.messages_30d ?? 0}
                helper="최근 30일 저장 메시지"
                icon={MessageCircle}
              />
              <AdminMetricCard
                title="콘텐츠 시청 기록"
                value={overview?.metrics.watched_content_30d ?? 0}
                helper="최근 30일 앱 내 재생"
                icon={Video}
                tone="amber"
              />
              <AdminMetricCard
                title="활성 세션 비율"
                value={activeSessionRate}
                helper={`진행 중 ${formatNumber(overview?.metrics.active_sessions)} / 전체 ${formatNumber(overview?.metrics.total_sessions)}`}
                icon={Clock}
                tone="green"
              />
            </section>

            <section className="grid gap-6 xl:grid-cols-[1.35fr_0.65fr]">
              <Card className="border-0 shadow-sm">
                <CardHeader>
                  <CardTitle>최근 14일 활동 추이</CardTitle>
                </CardHeader>
                <CardContent>
                  {dailyData.length ? (
                    <div>
                      <div className="h-80">
                        <ResponsiveContainer width="100%" height="100%">
                          <LineChart data={dailyData}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                            <YAxis tick={{ fontSize: 12 }} />
                            <Tooltip />
                            <Line type="monotone" dataKey="sessions" name="세션" stroke="#2563eb" strokeWidth={3} />
                            <Line type="monotone" dataKey="messages" name="메시지" stroke="#16a34a" strokeWidth={2} />
                            <Line type="monotone" dataKey="watched" name="시청" stroke="#f59e0b" strokeWidth={2} />
                            <Line type="monotone" dataKey="feedback" name="피드백" stroke="#ef4444" strokeWidth={2} />
                          </LineChart>
                        </ResponsiveContainer>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-4 text-sm">
                        <div className="flex items-center gap-2">
                          <span className="h-3 w-3 rounded-full" style={{ background: "#2563eb" }} />
                          <span>세션</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="h-3 w-3 rounded-full" style={{ background: "#16a34a" }} />
                          <span>메시지</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="h-3 w-3 rounded-full" style={{ background: "#f59e0b" }} />
                          <span>시청</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="h-3 w-3 rounded-full" style={{ background: "#ef4444" }} />
                          <span>피드백</span>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <EmptyPanel message="표시할 활동 데이터가 없습니다." />
                  )}
                </CardContent>
              </Card>

              <Card className="border-0 shadow-sm">
                <CardHeader>
                  <CardTitle>대화 방식 선택</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {personaData.length ? (
                    personaData.map((item) => (
                      <div key={item.persona} className="flex items-center justify-between rounded-xl bg-muted/50 px-4 py-3">
                        <span className="text-sm font-medium">{item.persona}</span>
                        <span className="text-sm text-muted-foreground">{formatNumber(item.count)}회</span>
                      </div>
                    ))
                  ) : (
                    <EmptyPanel message="대화 방식 데이터가 없습니다." />
                  )}
                </CardContent>
              </Card>
            </section>

            <section className="grid gap-6 xl:grid-cols-2">
              <Card className="border-0 shadow-sm">
                <CardHeader>
                  <CardTitle>상위 콘텐츠</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {(overview?.top_content ?? []).length ? (
                    overview?.top_content.map((item, index) => (
                      <div key={item.content_id} className="flex items-center gap-3 rounded-xl bg-muted/40 p-3">
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-sm font-bold text-primary">
                          {index + 1}
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium">{item.title}</p>
                        </div>
                        <div className="flex shrink-0 items-center gap-3 text-xs text-muted-foreground">
                          <span>재생 {formatNumber(item.watched_count)}</span>
                          <span className="inline-flex items-center gap-1">
                            <ThumbsUp className="h-3 w-3" />
                            {formatNumber(item.likes)}
                          </span>
                          <span className="inline-flex items-center gap-1">
                            <ThumbsDown className="h-3 w-3" />
                            {formatNumber(item.dislikes)}
                          </span>
                        </div>
                      </div>
                    ))
                  ) : (
                    <EmptyPanel message="콘텐츠 기록이 없습니다." />
                  )}
                </CardContent>
              </Card>

              <Card className="border-0 shadow-sm">
                <CardHeader>
                  <CardTitle>최근 상담 세션 (최대 10건 표시)</CardTitle>
                </CardHeader>
                <CardContent className="overflow-x-auto">
                  {(overview?.recent_sessions ?? []).length ? (
                    <table className="w-full min-w-[760px] text-sm">
                      <thead>
                        <tr className="border-b text-left text-xs text-muted-foreground">
                          <th className="py-2 pr-4 font-medium">사용자</th>
                          <th className="py-2 pr-4 font-medium">상태</th>
                          <th className="py-2 pr-4 font-medium">방식</th>
                          <th className="py-2 pr-4 font-medium">시작</th>
                          <th className="py-2 pr-4 font-medium">메시지</th>
                          <th className="py-2 pr-4 font-medium">콘텐츠</th>
                          <th className="py-2 font-medium">최근 기분</th>
                        </tr>
                      </thead>
                      <tbody>
                        { (overview?.recent_sessions ?? []).slice(0, 10).map((session) => (
                          <tr key={session.session_id} className="border-b last:border-b-0">
                            <td className="py-3 pr-4 font-medium">{session.user_label}</td>
                            <td className="py-3 pr-4">{statusLabel(session.status)}</td>
                            <td className="py-3 pr-4">{session.persona}</td>
                            <td className="py-3 pr-4 text-muted-foreground">{formatDateTime(session.started_at)}</td>
                            <td className="py-3 pr-4">{formatNumber(session.message_count)}</td>
                            <td className="py-3 pr-4">{formatNumber(session.watched_count)}</td>
                            <td className="py-3">{session.latest_mood ?? "-"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <EmptyPanel message="최근 상담 세션이 없습니다." />
                  )}
                </CardContent>
              </Card>
            </section>
          </>
        )}
      </main>
    </div>
  )
}
