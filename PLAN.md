# MoodPick 개발 계획 및 아키텍처 문서

## 1. 프로젝트 개요

**MoodPick(무드픽)**은 AI 기반의 실시간 정서 상태 분석과 심리 상담을 제공하고, 사용자의 감정에 맞는 맞춤형 미디어(YouTube 영상)를 자동으로 재생해주는 웹 서비스입니다.

### 핵심 가치
- **실시간 감정 분석**: 사용자의 입력과 상호작용을 통해 감정 상태를 파악
- **세션 단위 상담 흐름**: 사용자가 상담 시작하기를 누를 때마다 새 세션을 열고 이전 화면은 즉시 초기화
- **AI 기반 상담**: GPT-4o-mini 단일 모델과 Function Calling 라우팅으로 개인화된 심리 상담 제공
- **오버레이 문진**: 사전문진과 사후문진을 전체화면 오버레이로 진행하고 동일 문항으로 감정 변화 측정
- **자동 콘텐츠 재생 및 피드백**: 추천 YouTube 영상 재생, 전체화면 토글, 👍/👎 피드백과 시청 기록 저장

---

## 2. 프로젝트 폴더 구조

```
MoodPick/
├── frontend/                    # React (Vite) 프론트엔드
│   ├── src/
│   │   ├── components/          # UI 컴포넌트 (기존 shadcn/ui 통합)
│   │   │   ├── ui/              # 기본 UI 컴포넌트
│   │   │   ├── pages/           # 페이지 컴포넌트
│   │   │   └── layout/          # 레이아웃 컴포넌트
│   │   ├── pages/               # 메인 페이지들
│   │   ├── hooks/               # React 커스텀 훅
│   │   ├── context/             # Context API 상태 관리
│   │   ├── services/            # API 호출 함수들
│   │   ├── types/               # TypeScript 타입 정의
│   │   ├── lib/                 # 유틸 함수
│   │   ├── styles/              # 전역 스타일
│   │   └── App.tsx              # 메인 App 컴포넌트
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── package.json
│
├── backend/                     # FastAPI 백엔드 서버
│   ├── app/
│   │   ├── main.py              # FastAPI 애플리케이션 진입점
│   │   ├── routers/             # API 라우트
│   │   │   ├── auth.py          # 인증 관련 API
│   │   │   ├── counseling.py    # 상담 관련 API
│   │   │   ├── emotion.py       # 감정 분석 API
│   │   │   └── user.py          # 사용자 API
│   │   ├── schemas/             # Pydantic 스키마
│   │   ├── models/              # 데이터베이스 모델
│   │   ├── services/            # 비즈니스 로직
│   │   │   ├── ai_service.py    # AI 처리 로직
│   │   │   ├── emotion_service.py # 감정 분석 로직
│   │   │   └── recommendation_service.py # 콘텐츠 추천
│   │   ├── config.py            # 설정 파일
│   │   └── dependencies.py      # 의존성 주입
│   ├── requirements.txt
│   └── .env.example
│
├── ai/                          # AI 프롬프트 및 Function Calling 정의
│   ├── prompts/
│   │   ├── system_prompt.md     # GPT-4o-mini 시스템 프롬프트
│   │   ├── counseling_prompt.txt # 상담 프롬프트
│   │   └── analysis_prompt.txt   # 감정 분석 프롬프트
│   ├── function_definitions.py  # Function Calling 도구 정의
│   ├── tools/
│   │   ├── youtube_search.py    # YouTube API 통합
│   │   └── emotion_mapper.py    # 감정 매핑 로직
│   └── README.md                # AI 모듈 사용 가이드
│
├── db/                          # Supabase 데이터베이스 관리
│   ├── migrations/              # 마이그레이션 파일
│   │   ├── 001_initial_schema.sql
│   │   ├── 002_vector_tables.sql
│   │   └── 003_indexes.sql
│   ├── seed_data/               # 초기 데이터
│   │   └── seed.sql
│   ├── functions/               # Supabase Edge Functions (선택사항)
│   └── schema.md                # 데이터베이스 스키마 문서
│
└── PLAN.md                      # 이 문서
```

---

## 3. 빠른 개요: 3단계 개발 로드맵

| Phase | 이름 | 소요 시간 | 목표 |
|-------|------|---------|------|
| **Phase 0** | 프로젝트 초기화 | 30분 | 폴더 구조 생성, Git 설정, 환경 변수 |
| **🟢 Phase 1** | 프론트엔드 기본 구축 | 3-5시간 | React + Vite + Context API 완성 |
| **🟡 Phase 2** | 백엔드 기본 구축 | 4-6시간 | FastAPI + Supabase + 기본 라우트 |
| **🟠 Phase 3** | AI 통합 & Function Calling | 4-6시간 | GPT-4o-mini 단일 라우팅 + 세션 문맥 처리 |
| **🔴 Phase 4** | 프론트↔백 통합 & 인증 | 3-4시간 | 세션 흐름, 문진 오버레이, 시청 기록 연동 |
| **🟣 Phase 5** | 안정화 & 최적화 | 2-3시간 | 버그 수정 + 10시 알림 + 배포 준비 |

**전체 소요 시간**: 약 16-26시간 (약 2-3주)

> 📌 **상세한 Phase별 체크리스트는 아래 "Section 4"를 참고하세요!**

---

## 4. 세부 개발 체크리스트 (Phase별)

> **📌 사용법**: 각 Phase는 순차적으로 진행됩니다. Phase 내 모든 체크리스트를 완료한 후 다음 Phase로 진행하세요.  
> 사용자가 "Phase 1의 1번 작업 시작" 또는 "Phase 2 준비 작업해줘" 등으로 요청하면, 해당 Phase의 구체적인 구현을 진행합니다.

---

## 🔵 Phase 0: 프로젝트 초기화 및 기본 설정
   - 기존 UI 컴포넌트 (`components/`) 폴더에 통합
   - shadcn/ui 컴포넌트 정리

2. **핵심 페이지 구현** (SPA 구조)
   - `로그인 페이지` (Supabase Auth 연동 대기)
   - `온보딩/사전 문진 페이지` (기본 폼 입력, 상태 저장만)
   - `메인 대시보드 페이지` (홈, 상담, 기록, 마이페이지 탭)

3. **상태 관리 구현**
   - Context API로 전역 상태 관리 구조 설계
   - `UserContext`: 로그인 사용자 정보
   - `EmotionContext`: 현재 감정 상태 저장
   - `CounselingContext`: 상담 대화 이력 저장

4. **라우팅 구현**
   - React Router 또는 수동 상태 기반 화면 전환
   - 페이지 간 부드러운 네비게이션

#### 요구되는 라이브러리
```json
{
  "react": "^18.0",
  "typescript": "^5.0",
  "tailwindcss": "^3.0",
  "lucide-react": "^1.0",
  "@supabase/supabase-js": "^2.36"
}
```

#### 완료 기준
- [ ] 모든 페이지가 로드되고 화면 전환이 가능
- [ ] Context API를 통해 상태가 전역으로 공유됨
- [ ] 브라우저 콘솔에 오류가 없음

---

### 📍 2단계: 백엔드 및 AI 연동 (1-2주일)
**목표**: FastAPI 서버와 GPT-4o-mini의 Function Calling을 통해 핵심 기능 구현

#### 작업 항목

1. **Supabase 설정**
   - 프로젝트 생성 및 인증 설정
   - 테이블 생성 (사용자, 감정 기록, 상담 기록)
   - pgvector 확장 활성화 (감정 벡터 저장)

2. **FastAPI 백엔드 구축**
   - 기본 CORS 설정
   - Pydantic 스키마 정의
   - `/auth` 라우트: 사용자 로그인/회원가입
   - `/counseling` 라우트: 상담 요청/응답
   - `/emotion` 라우트: 감정 분석 및 저장
   - `/user` 라우트: 사용자 정보 조회/수정

3. **AI 통합 (Single LLM Pattern)**
   - GPT-4o-mini 시스템 프롬프트 작성
   - Function Calling 도구 정의:
     - `search_youtube_video()`: YouTube API를 통해 영상 검색
     - `analyze_emotion()`: 사용자 입력에서 감정 추출
     - `get_user_history()`: 사용자의 과거 상담 기록 조회
   - 프롬프트 라우팅: 사용자 입력 유형에 따라 적절한 함수 호출

4. **YouTube 자동 재생**
   - YouTube Data API v3 토큰 설정
   - 프론트엔드: 미디어 플레이어 컴포넌트 구현
   - 백엔드 → 프론트엔드: WebSocket 또는 API 폴링으로 영상 정보 전달
   - 자동 재생 로직: AI가 추천한 영상 URL을 받으면 즉시 플레이

5. **Supabase 인증 연동**
   - 프론트엔드에서 소셜 로그인 (Google/GitHub)
   - 백엔드에서 JWT 토큰 검증

#### 요구되는 라이브러리 (Backend)
```
fastapi==0.104.0
uvicorn==0.24.0
pydantic==2.4.0
pydantic-settings==2.0.0
python-dotenv==1.0.0
openai==1.3.0
google-api-python-client==1.12.0
supabase==2.4.0
python-jose==3.3.0
passlib==1.7.4
python-multipart==0.0.6
```

#### 완료 기준
- [ ] 백엔드 서버가 정상 실행됨
- [ ] Supabase 연결 확인됨
- [ ] GPT-4o-mini의 Function Calling이 작동함
- [ ] YouTube 영상이 자동으로 재생됨

---

### 📍 3단계: 기능 안정화 및 고도화 (1주일+)
**목표**: 버그 수정, 성능 최적화, 데이터 시각화 추가

#### 작업 항목
1. **감정 기록 시각화**
   - 간단한 선 그래프로 감정 변화 추적
   - 라이브러리: `recharts` (필요시만 추가)

2. **보안 강화**
   - 환경 변수 관리
   - API 레이트 제한
   - 입력 검증 강화

3. **성능 최적화**
   - 이미지 최적화
   - API 응답 캐싱
   - 데이터베이스 인덱싱

4. **사용자 경험 개선**
   - 로딩 상태 표시
   - 에러 메시지 개선
   - 반응형 디자인 최적화

#### 완료 기준
- [ ] 핵심 기능이 모두 정상 작동
- [ ] 모든 페이지가 모바일/데스크톱에서 잘 보임
- [ ] API 응답 시간이 2초 이내

---

## 5. 기술 스택 상세 설명

### 프론트엔드 (Frontend)
| 기술 | 용도 | 선택 이유 |
|-----|-----|----------|
| **React 18** | UI 구성 및 상태 관리 | 학습곡선이 낮고 널리 사용됨 |
| **Vite** | 번들러 및 개발 서버 | Fast HMR, 빠른 빌드 속도 |
| **TypeScript** | 타입 안정성 | 개발 초기부터 버그 예방 |
| **Tailwind CSS** | 스타일링 | 기존 프로젝트에서 활용 중 |
| **shadcn/ui** | UI 컴포넌트 라이브러리 | 기존 컴포넌트 재사용 |
| **lucide-react** | 아이콘 | 경량, 접근성 우수 |
| **Supabase JS** | 백엔드 인증/DB | 관리형 서비스, 빠른 통합 |
| **Context API** | 전역 상태관리 | React 기본 기능, 추가 라이브러리 불필요 |

### 백엔드 (Backend)
| 기술 | 용도 | 선택 이유 |
|-----|-----|----------|
| **FastAPI** | REST API 구축 | Python, 빠른 성능, 자동 문서화 |
| **Pydantic** | 데이터 검증 | FastAPI 기본 제공, 강력한 검증 |
| **Uvicorn** | ASGI 서버 | 가볍고 빠름 |
| **OpenAI API** | AI 모델 (GPT-4o-mini) | 안정적이고 강력한 성능 |
| **YouTube Data API v3** | 영상 검색 | 공식 API, 신뢰성 높음 |
| **Supabase SDK** | 데이터베이스 | PostgreSQL 관리형, pgvector 지원 |

### 데이터베이스 (Database)
| 기술 | 용도 | 선택 이유 |
|-----|-----|----------|
| **Supabase (PostgreSQL)** | 관계형 데이터 저장 | 사용자, 감정 기록, 상담 이력 |
| **pgvector** | 벡터 저장 및 검색 | 감정 분석 결과의 유사도 검색 |
| **Edge Functions** | 백엔드 로직 (선택) | 추후 필요시 확장 |

### AI/LLM
| 기술 | 용도 | 선택 이유 |
|-----|-----|----------|
| **GPT-4o-mini** | 상담 및 감정 분석 | 한국어 이해도 높음, 저비용 |
| **Function Calling** | 도구 호출 | AI가 적절히 YouTube 검색, 감정 분석 등을 수행 |

---

## 6. 핵심 아키텍처

### 시스템 다이어그램

```
┌─────────────────────────────────────────────────────────────────┐
│                        프론트엔드 (React)                         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  로그인 → 상담 시작 → 사전 오버레이 → 상담 → 사후 오버레이│   │
│  │  Context API로 전역 상태 관리 (사용자, 세션, 문진, 이력)  │   │
│  │  우측 YouTube 플레이어 (자동 재생, 전체화면 토글, 피드백) │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                    │ HTTP/REST API
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                       백엔드 (FastAPI)                           │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  라우트: /auth, /session, /counseling, /emotion, /user    │   │
│  │  서비스: 세션 관리, 문진 비교, AI, 추천, 알림 스케줄러     │   │
│  │  검증: Pydantic 스키마                                    │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────┬──────────────────────────────┬────────────────────┘
         │                              │
         ▼                              ▼
   ┌─────────────────┐          ┌──────────────────────┐
   │  Supabase       │          │  OpenAI API          │
   │  (PostgreSQL)   │          │  (GPT-4o-mini)       │
   │  - 사용자       │◄────────►│  Function Calling:   │
   │  - 세션         │          │  - 감정 분석         │
   │  - 문진 응답    │          │  - YouTube 검색      │
   │  - 상담 기록    │          │  - 세션 요약         │
   │  - 시청 기록    │          │  - 콘텐츠 피드백     │
   └─────────────────┘          └──────────────────────┘
                            │
                            ▼
                       ┌──────────────────────┐
                       │  YouTube Data API v3 │
                       │  (영상 검색)         │
                       └──────────────────────┘
```

### 데이터 흐름

#### 시나리오: 사용자가 상담 세션 시작

```
1. 사용자가 프론트엔드에서 "상담 시작하기" 버튼 클릭
  ↓
2. 프론트엔드 → 백엔드: POST /session/start
  {
    "user_id": "xyz123",
    "context": "업무 스트레스"
  }
  ↓
3. 백엔드 → Supabase: 새 세션 생성 및 이전 세션 이력 보존
  ↓
4. 프론트엔드에서 사전문진 Full-screen Overlay 표시
  - 동일한 이모지 기반 질문 세트를 사용
  - 응답을 세션 시작 데이터와 함께 저장
  ↓
5. 백엔드 → OpenAI: GPT-4o-mini 단일 모델로 Function Calling 요청
  - System Prompt: "당신은 한국의 친절한 심리 상담사입니다..."
  - User Message: "요새 업무 스트레스가 많아요"
  - Available Functions:
    * analyze_emotion(text) → 감정 추출
    * search_youtube_video(query) → 영상 검색
    * get_session_summary(session_id) → 세션 맥락 요약
  ↓
6. GPT-4o-mini가 응답 생성:
  - 상담 메시지 작성
  - analyze_emotion() 호출 → {"emotion": "스트레스", "intensity": 0.8}
  - search_youtube_video("명상 음악") 호출
  ↓
7. 백엔드 → Supabase: 세션, 감정 기록, 문진 응답, 상담 기록 저장
  ↓
8. 백엔드 → 프론트엔드: 응답 반환
  {
    "counselor_message": "업무 스트레스는 흔한 일입니다...",
    "emotion_analysis": {
     "emotion": "스트레스",
     "intensity": 0.8,
     "recommendations": ["명상", "운동", "휴식"]
    },
    "recommended_video": {
     "title": "30분 명상 음악",
     "url": "https://www.youtube.com/watch?v=xxxxx",
     "duration": 1800
    }
  }
  ↓
9. 프론트엔드에서:
  - 상담 메시지 화면에 표시
  - 우측 플레이어에 영상 로드 후 전체화면 토글 제공
  - 하단 👍/👎 피드백 저장
  - 세션 종료 시 사후문진 Full-screen Overlay 표시
  - 사전/사후 응답 차이로 감정 변화(Delta) 계산
10. 사용자가 명시적으로 종료하지 않으면 매일 밤 10시 스케줄러 알림이 사후문진을 유도
```

---

## 7. 각 폴더별 개발 가이드

### Frontend 폴더

#### 폴더 구조
```
frontend/src/
├── components/
│   ├── pages/               # 전체 페이지 컴포넌트
│   │   ├── LoginPage.tsx
│   │   ├── SessionPage.tsx
│   │   ├── CounselingPage.tsx
│   │   ├── ContentHistoryPage.tsx
│   │   ├── EmotionHistoryPage.tsx
│   │   └── MyPage.tsx
│   ├── layout/              # 레이아웃 컴포넌트
│   │   ├── RootLayout.tsx
│   │   ├── DashboardLayout.tsx
│   │   └── Header.tsx
│   ├── ui/                  # shadcn/ui 컴포넌트 (기존)
│   ├── common/              # 공통 컴포넌트
│   │   ├── LoadingSpinner.tsx
│   │   ├── ErrorAlert.tsx
│   │   └── ConfirmDialog.tsx
│   └── features/            # 기능별 컴포넌트
│       ├── ChatBox.tsx      # 상담 메시지 표시
│       ├── MediaPlayer.tsx  # YouTube 플레이어, 전체화면 토글
│       ├── OverlaySurvey.tsx # 사전/사후 문진 오버레이
│       ├── ContentFeedbackButtons.tsx # 👍/👎 피드백
│       ├── ContentHistoryCard.tsx # 시청 기록 카드
│       └── SessionStarter.tsx # 상담 시작 버튼
│
├── context/                 # Context API
│   ├── UserContext.tsx      # 사용자 정보
│   ├── SessionContext.tsx   # 세션 상태
│   ├── EmotionContext.tsx   # 감정 상태
│   ├── SurveyContext.tsx    # 문진 상태
│   ├── CounselingContext.tsx # 상담 대화
│   └── AppProvider.tsx      # 모든 Context 통합
│
├── hooks/
│   ├── useUser.ts           # 사용자 정보 접근 훅
│   ├── useSession.ts        # 세션 접근 훅
│   ├── useEmotion.ts        # 감정 상태 접근 훅
│   ├── useSurvey.ts         # 문진 상태 접근 훅
│   ├── useCounseling.ts     # 상담 기능 훅
│   └── useFetch.ts          # API 호출 훅
│
├── services/
│   ├── api.ts               # API 클라이언트 (axios 또는 fetch)
│   ├── sessionService.ts    # 세션 API
│   ├── authService.ts       # 인증 API
│   ├── counselingService.ts # 상담 API
│   ├── emotionService.ts    # 감정 API
│   ├── contentService.ts    # 콘텐츠 피드백/시청 기록 API
│   └── userService.ts       # 사용자 API
│
├── types/
│   ├── index.ts             # 공통 타입
│   ├── user.ts              # 사용자 타입
│   ├── session.ts           # 세션 타입
│   ├── emotion.ts           # 감정 타입
│   ├── survey.ts            # 문진 타입
│   └── counseling.ts        # 상담 타입
│
├── lib/
│   ├── utils.ts             # 유틸 함수
│   ├── constants.ts         # 상수
│   └── supabaseClient.ts    # Supabase 클라이언트
│
├── styles/
│   └── globals.css          # 전역 스타일
│
├── App.tsx                  # 메인 App 컴포넌트
└── main.tsx                 # 진입점
```

#### Context 설계 예시 (1단계)

```typescript
// UserContext.tsx
interface User {
  id: string;
  email: string;
  name: string;
  createdAt: string;
}

interface UserContextType {
  user: User | null;
  isLoading: boolean;
  setUser: (user: User | null) => void;
}

const UserContext = React.createContext<UserContextType | undefined>(undefined);

// 사용 예시
const { user } = useUser();
if (!user) {
  return <LoginPage />;
}
```

#### UI 구성 포인트
- 상담 시작 시 세션을 생성하고 이전 대화는 화면에서 즉시 비움
- 사전/사후 문진은 동일한 문항 세트로 Full-screen Overlay 처리
- 우측 미디어 플레이어에는 전체화면 토글과 이모지 피드백 버튼 배치
- 마이페이지 또는 대시보드 하위에 "내가 위로받은 콘텐츠" 기록 뷰 추가

---

### Backend 폴더

#### 폴더 구조
```
backend/
├── app/
│   ├── main.py
│   │   # FastAPI 앱 초기화
│   │   # CORS 설정
│   │   # 라우트 등록
│   │   # 시작/종료 이벤트
│   │
│   ├── routers/
│   │   ├── auth.py          # /auth/* 라우트
│   │   ├── session.py       # /session/* 라우트
│   │   ├── counseling.py    # /counseling/* 라우트
│   │   ├── emotion.py       # /emotion/* 라우트
│   │   ├── content.py       # /content/* 라우트
│   │   ├── notification.py  # /notification/* 라우트
│   │   └── user.py          # /user/* 라우트
│   │
│   ├── schemas/             # Pydantic 모델 (요청/응답)
│   │   ├── session_schema.py
│   │   ├── auth_schema.py
│   │   ├── emotion_schema.py
│   │   ├── survey_schema.py
│   │   ├── counseling_schema.py
│   │   ├── content_schema.py
│   │   └── common_schema.py
│   │
│   ├── models/              # 데이터 모델 (데이터베이스)
│   │   ├── session.py
│   │   ├── user.py
│   │   ├── emotion_record.py
│   │   ├── survey_response.py
│   │   ├── content_feedback.py
│   │   └── counseling_history.py
│   │
│   ├── services/
│   │   ├── ai_service.py           # GPT-4o-mini 단일 라우팅
│   │   ├── session_service.py      # 세션 관리
│   │   ├── emotion_service.py      # 감정 분석
│   │   ├── recommendation_service.py # 추천
│   │   ├── notification_service.py # 10시 알림
│   │   ├── scheduler_service.py    # 스케줄러 실행
│   │   └── supabase_service.py     # DB 접근
│   │
│   ├── config.py            # 환경 변수 및 설정
│   └── dependencies.py      # 의존성 주입 함수
│
└── requirements.txt
```

#### API 엔드포인트 설계

```
인증 (Authentication)
  POST /auth/register         # 회원가입 (소셜 로그인)
  POST /auth/login            # 로그인
  POST /auth/logout           # 로그아웃
  GET  /auth/me               # 현재 사용자 정보

세션 (Session)
  POST /session/start         # 세션 시작
  POST /session/end           # 세션 종료
  GET  /session/current       # 현재 세션 조회

상담 (Counseling)
  POST /counseling/message    # 메시지 전송
  GET  /counseling/history    # 상담 이력 조회

감정 분석 (Emotion)
  POST /emotion/analyze       # 감정 분석
  GET  /emotion/records       # 감정 기록 조회
  POST /emotion/save          # 감정 기록 저장

문진 (Survey)
  GET  /survey/questions      # 사전/사후 문진 질문 조회
  POST /survey/submit         # 문진 응답 저장
  GET  /survey/delta          # 사전/사후 감정 변화 조회

콘텐츠 (Content)
  POST /content/feedback      # 영상 피드백 저장
  GET  /content/history       # 위로받은 콘텐츠 기록 조회

사용자 (User)
  GET  /user/profile          # 프로필 조회
  PUT  /user/profile          # 프로필 수정
  GET  /user/preferences      # 설정 조회
  PUT  /user/preferences      # 설정 수정

알림 (Notification)
  POST /notification/evening-reminder  # 10시 알림 발송
```

#### AI Service 구조

- 단일 `gpt-4o-mini` 모델이 상담, 세션 요약, 콘텐츠 피드백, YouTube 추천을 모두 라우팅한다.
- 자세한 `FUNCTION_DEFINITIONS` 예시는 아래 `3-3` 섹션을 따른다.

---

### AI 폴더

#### 시스템 프롬프트 구조

```
ai/prompts/system_prompt.md

---

당신은 MoodPick이라는 AI 심리 상담 서비스의 상담사입니다.

역할:
- 사용자의 감정 상태를 공감하고 세심하게 들어주기
- 심리학 기반의 따뜻한 조언 제공
- 감정 분석과 맞춤 추천 제공

행동 규칙:
1. 사용자의 입력을 먼저 공감으로 시작하기 ("그 심정 정말 어렵겠네요")
2. 내가 이해한 상황을 요약해 주기
3. 필요시 analyze_emotion() 함수로 감정을 정확히 파악하기
4. 사용자의 기분에 맞는 음악/콘텐츠를 추천하기 위해 search_youtube_video() 호출
5. 과거 상담 기록과 세션 요약이 필요하면 get_session_summary() 호출
6. 영상 피드백은 상담과 분리된 가벼운 흐름으로 처리하기

응답 형식:
- 항상 따뜻하고 인간적인 톤 유지
- 상담사의 말 = 공감 + 조언 + 추천
- 정확한 감정 분석 결과 제시

---
```

#### Function Definitions

```python
# ai/function_definitions.py

FUNCTION_DEFINITIONS = [
    {
    "name": "analyze_emotion",
        "description": "사용자의 텍스트 입력에서 감정을 분석하고 강도를 평가합니다",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "분석할 텍스트"
                }
            },
            "required": ["text"]
        }
    },
    {
        "name": "search_youtube_video",
        "description": "사용자의 감정과 기분에 맞는 유튜브 영상을 검색합니다",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "검색 키워드 (예: '명상 음악', '긍정 영상')"
                },
            "emotion": {
                    "type": "string",
                    "description": "현재 사용자의 감정"
                }
          },
          "required": ["query"]
        }
      },
      {
        "name": "search_youtube_video",
        "description": "현재 세션의 상담 기록과 사전/사후 문진 차이를 조회합니다",
        "parameters": {
          "type": "object",
          "properties": {
            "session_id": {
              "type": "string",
              "description": "세션 ID"
            },
            "emotion": {
              "type": "integer",
              "description": "조회할 기간 (일 단위, 기본값: 7)"
            }
          "type": "string",
          "required": ["session_id"]
        }
      },
      {
        "name": "get_session_summary",
        "description": "현재 세션의 상담 기록과 사전/사후 문진 차이를 조회합니다",
        "parameters": {
          "type": "object",
          "properties": {
            "session_id": {
              "type": "string",
              "description": "세션 ID"
            },
            "feedback": {
              "type": "string",
              "description": "좋아요 또는 싫어요"
            }
          },
          "required": ["content_id", "feedback"]
          "type": "string",
          "description": "좋아요 또는 싫어요"
        }
      },
      "required": ["content_id", "feedback"]
    }
  }
-- db/migrations/001_initial_schema.sql

-- 사용자 테이블
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(255) UNIQUE NOT NULL,
  name VARCHAR(255) NOT NULL,
  profile_image_url TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- 세션 테이블
CREATE TABLE counseling_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  status VARCHAR(50) NOT NULL DEFAULT 'active',
  started_at TIMESTAMP DEFAULT NOW(),
  ended_at TIMESTAMP NULL,
  created_at TIMESTAMP DEFAULT NOW()
);

-- 문진 응답 테이블
CREATE TABLE survey_responses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID NOT NULL REFERENCES counseling_sessions(id) ON DELETE CASCADE,
  phase VARCHAR(20) NOT NULL,          -- 'pre' 또는 'post'
  question_key VARCHAR(100) NOT NULL,
  emoji_value VARCHAR(10) NOT NULL,
  score FLOAT NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);

-- 감정 기록 테이블
CREATE TABLE emotion_records (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  emotion VARCHAR(100) NOT NULL,       -- "기쁨", "슬픔", "불안감" 등
  intensity FLOAT CHECK (intensity >= 0 AND intensity <= 1),
  context TEXT,                         -- 감정이 발생한 맥락
  timestamp TIMESTAMP DEFAULT NOW(),
  created_at TIMESTAMP DEFAULT NOW()
);

-- 상담 기록 테이블
CREATE TABLE counseling_histories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  session_id UUID NOT NULL REFERENCES counseling_sessions(id) ON DELETE CASCADE,
  user_message TEXT NOT NULL,
  counselor_response TEXT NOT NULL,
  recommended_video_id VARCHAR(255),    -- YouTube 비디오 ID
  recommended_video_title TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

-- 콘텐츠 피드백 테이블
CREATE TABLE content_feedback (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID REFERENCES counseling_sessions(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  content_id VARCHAR(255) NOT NULL,
  feedback VARCHAR(10) NOT NULL,        -- 'like' 또는 'dislike'
  created_at TIMESTAMP DEFAULT NOW()
);

-- 시청 기록 테이블
CREATE TABLE watched_content_records (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  session_id UUID REFERENCES counseling_sessions(id) ON DELETE CASCADE,
  content_id VARCHAR(255) NOT NULL,
  content_title TEXT NOT NULL,
  thumbnail_url TEXT,
  watched_at TIMESTAMP DEFAULT NOW()
);

-- 알림 스케줄 테이블
CREATE TABLE scheduled_notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  notification_type VARCHAR(50) NOT NULL,
  scheduled_for TIMESTAMP NOT NULL,
  sent_at TIMESTAMP NULL,
  created_at TIMESTAMP DEFAULT NOW()
);

-- 인덱스
CREATE INDEX idx_counseling_sessions_user_id ON counseling_sessions(user_id);
CREATE INDEX idx_survey_responses_session_id ON survey_responses(session_id);
CREATE INDEX idx_emotion_records_user_id ON emotion_records(user_id);
CREATE INDEX idx_emotion_records_timestamp ON emotion_records(timestamp);
CREATE INDEX idx_counseling_user_id ON counseling_histories(user_id);
CREATE INDEX idx_counseling_session_id ON counseling_histories(session_id);
CREATE INDEX idx_content_feedback_user_id ON content_feedback(user_id);
CREATE INDEX idx_watched_content_records_user_id ON watched_content_records(user_id);
```

#### 벡터 스토리지 (pgvector) - 선택사항

```sql
-- db/migrations/002_vector_tables.sql

CREATE EXTENSION IF NOT EXISTS vector;

-- 감정 임베딩 테이블
CREATE TABLE emotion_embeddings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  emotion_record_id UUID REFERENCES emotion_records(id),
  embedding vector(1536),  -- OpenAI 임베딩 크기
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX ON emotion_embeddings USING ivfflat (embedding vector_cosine_ops);
```

---

## 4. 세부 개발 체크리스트 (Phase별)

> **📌 사용법**: 각 Phase는 순차적으로 진행됩니다. Phase 내 모든 체크리스트를 완료한 후 다음 Phase로 진행하세요.  
> 사용자가 "Phase 1의 1번 작업 시작" 또는 "Phase 2 준비 작업해줘" 등으로 요청하면, 해당 Phase의 구체적인 구현을 진행합니다.

---

## 🔵 Phase 0: 프로젝트 초기화 및 기본 설정

**목표**: 전체 프로젝트 폴더 구조 생성, 환경 변수 설정, Git 초기화  
**소요 시간**: 약 30분

### Phase 0 체크리스트

- [x] **0-1. 프로젝트 루트 폴더 구조 생성**
  - 프로젝트 루트에서 다음 폴더들 생성:
    - `frontend/` (React 프로젝트용)
    - `backend/` (FastAPI 프로젝트용)
    - `ai/` (AI 프롬프트 및 Function Calling 정의)
    - `db/` (Supabase 스키마 및 마이그레이션)
  - 각 폴더에 `README.md` 파일 생성 (기본 설명 작성)

- [x] **0-2. Git 초기화**
  ```bash
  cd MoodPick
  git init
  git config user.name "Your Name"
  git config user.email "your.email@example.com"
  ```
  - `.gitignore` 파일 생성 (node_modules, __pycache__, .env, .venv 등)
  - 초기 커밋: `git add . && git commit -m "Initial project structure"`

- [x] **0-3. 환경 변수 파일 생성**
  - `backend/.env.example` 생성 (예시)
    ```
    # Supabase
    SUPABASE_URL=your_supabase_url_here
    SUPABASE_KEY=your_supabase_key_here
    
    # OpenAI
    OPENAI_API_KEY=your_openai_api_key_here
    
    # YouTube
    YOUTUBE_API_KEY=your_youtube_api_key_here
    
    # Server
    SERVER_PORT=8000
    SERVER_HOST=0.0.0.0
    DEBUG=True
    ```
  - `backend/.env` 생성 (`.env.example` 기반, 실제 값 입력)

- [x] **0-4. PLAN.md와 일관성 확인**
  - PLAN.md의 폴더 구조와 실제 생성된 폴더 비교
  - 누락된 폴더나 파일 있는지 확인

- [x] **0-5. 프로젝트 워크스페이스 설정 (선택사항)**
  - VS Code에서 Multi-root Workspace 설정 (필요시)
  - IDE 확장 프로그램 설치 검토

**Phase 0 완료 체크**:
- [x] 모든 메인 폴더가 생성됨
- [x] .env 파일이 준비됨
- [x] Git 리포지토리 초기화됨

---

## 🟢 Phase 1: 프론트엔드 기본 구축 (React + Vite + Context API)

**목표**: UI 프레임워크 설정, 기존 컴포넌트 통합, 기본 페이지 및 상태 관리 구현  
**소요 시간**: 약 3-5시간  
**선행 조건**: Phase 0 완료

### Phase 1 세부 체크리스트

#### 1-1. Vite + React + TypeScript 프로젝트 생성
- [ ] **1-1-1. Vite 프로젝트 생성**
  ```bash
  npm create vite@latest -- --template react-ts
  # 프로젝트명: frontend
  cd frontend
  npm install
  ```

- [ ] **1-1-2. Tailwind CSS 및 필수 라이브러리 설치**
  ```bash
  npm install -D tailwindcss postcss autoprefixer
  npx tailwindcss init -p
  npm install lucide-react @supabase/supabase-js
  ```

- [ ] **1-1-3. 기본 파일 구조 확인**
  - `src/` 폴더 존재 확인
  - `src/main.tsx`, `src/App.tsx` 존재 확인
  - `package.json` 스크립트 확인: `npm run dev`, `npm run build`, `npm run preview`

#### 1-2. Tailwind CSS 초기화
- [ ] **1-2-1. tailwind.config.js 설정**
  - `content` 경로 확인: `["./index.html", "./src/**/*.{js,ts,jsx,tsx}"]`

- [ ] **1-2-2. src/index.css 설정 (또는 styles/globals.css)**
  ```css
  @tailwind base;
  @tailwind components;
  @tailwind utilities;
  ```

- [ ] **1-2-3. main.tsx에 CSS import 확인**
  ```typescript
  import './index.css'
  ```

#### 1-3. 폴더 구조 정리
- [ ] **1-3-1. src/ 하위 폴더 생성**
  ```
  src/
  ├── components/
  │   ├── pages/
  │   ├── layout/
  │   ├── common/
  │   ├── features/
  │   └── ui/
  ├── context/
  ├── hooks/
  ├── services/
  ├── types/
  ├── lib/
  ├── styles/
  ├── App.tsx
  └── main.tsx
  ```

- [ ] **1-3-2. 각 폴더에 index.ts 파일 생성** (필요시)
  ```typescript
  // index.ts 예시
  export { useUser } from './useUser';
  export { useEmotion } from './useEmotion';
  ```

#### 1-4. 기존 UI 컴포넌트 통합
- [ ] **1-4-1. 현재 frontend/components/ 파일 검토**
  - 기존 shadcn/ui 컴포넌트 목록 확인
  - 호환성 확인 (Vite 프로젝트와 맞는지)

- [ ] **1-4-2. 기존 컴포넌트를 새 구조로 이동**
  - 기본 UI 컴포넌트들 → `src/components/ui/`
  - 페이지 컴포넌트들 → 별도 폴더로 분류

- [ ] **1-4-3. import 경로 수정**
  - 상대 경로 검토 및 필요시 수정

#### 1-5. TypeScript 타입 정의
- [ ] **1-5-1. src/types/index.ts 작성**
  ```typescript
  // 공통 타입들
  export interface User {
    id: string;
    email: string;
    name: string;
    profileImageUrl?: string;
    createdAt: string;
  }
  
  export interface EmotionRecord {
    id: string;
    emotion: string;
    intensity: number;
    context?: string;
    timestamp: string;
  }
  
  export interface CounselingMessage {
    id: string;
    role: 'user' | 'counselor';
    content: string;
    timestamp: string;
  }
  ```

- [ ] **1-5-2. 추가 타입 정의 파일 생성**
  - `src/types/user.ts` (사용자 관련)
  - `src/types/emotion.ts` (감정 관련)
  - `src/types/counseling.ts` (상담 관련)

#### 1-6. Context API 설계 및 구현
- [ ] **1-6-1. UserContext 작성**
  ```typescript
  // src/context/UserContext.tsx
  interface UserContextType {
    user: User | null;
    isLoading: boolean;
    isAuthenticated: boolean;
    setUser: (user: User | null) => void;
    logout: () => void;
  }
  ```

- [ ] **1-6-2. SessionContext 작성**
  ```typescript
  // src/context/SessionContext.tsx
  interface SessionContextType {
    currentSession: Session | null;
    isSessionActive: boolean;
    startSession: (context: string) => Promise<void>;
    endSession: () => Promise<void>;
  }
  ```

- [ ] **1-6-3. EmotionContext 작성**
  ```typescript
  // src/context/EmotionContext.tsx
  interface EmotionContextType {
    currentEmotion: string | null;
    emotionIntensity: number;
    emotionHistory: EmotionRecord[];
    setCurrentEmotion: (emotion: string, intensity: number) => void;
    addEmotionRecord: (record: EmotionRecord) => void;
  }
  ```

- [ ] **1-6-4. SurveyContext 작성**
  ```typescript
  // src/context/SurveyContext.tsx
  interface SurveyContextType {
    preSurveyAnswers: Record<string, string>;
    postSurveyAnswers: Record<string, string>;
    surveyDelta: number | null;
    setSurveyAnswer: (phase: 'pre' | 'post', questionKey: string, value: string) => void;
  }
  ```

- [ ] **1-6-5. CounselingContext 작성**
  ```typescript
  // src/context/CounselingContext.tsx
  interface CounselingContextType {
    messages: CounselingMessage[];
    isLoading: boolean;
    addMessage: (message: CounselingMessage) => void;
    clearMessages: () => void;
  }
  ```

- [ ] **1-6-6. AppProvider 작성 (모든 Context 통합)**
  ```typescript
  // src/context/AppProvider.tsx
  export function AppProvider({ children }) {
    return (
      <SessionProvider>
      <UserProvider>
        <EmotionProvider>
          <SurveyProvider>
          <CounselingProvider>
            {children}
          </CounselingProvider>
          </SurveyProvider>
        </EmotionProvider>
      </UserProvider>
      </SessionProvider>
    );
  }
  ```

#### 1-7. 커스텀 훅 작성
- [ ] **1-7-1. useUser 훅 작성**
  ```typescript
  // src/hooks/useUser.ts
  export function useUser() {
    const context = useContext(UserContext);
    if (!context) throw new Error('useUser must be used within UserProvider');
    return context;
  }
  ```

- [ ] **1-7-2. useSession 훅 작성**
- [ ] **1-7-3. useEmotion 훅 작성**
- [ ] **1-7-4. useSurvey 훅 작성**
- [ ] **1-7-5. useCounseling 훅 작성**
- [ ] **1-7-6. useFetch 훅 작성**
  ```typescript
  // src/hooks/useFetch.ts
  // API 호출을 쉽게 하는 커스텀 훅
  ```

#### 1-8. API 서비스 레이어 구축
- [ ] **1-8-1. API 클라이언트 설정**
  ```typescript
  // src/services/api.ts
  const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
  
  export const apiClient = {
    get: (url: string) => fetch(`${API_BASE_URL}${url}`),
    post: (url: string, data: any) => fetch(`${API_BASE_URL}${url}`, { ... }),
    // ...
  };
  ```

- [ ] **1-8-2. 서비스 함수들 작성**
  - `src/services/sessionService.ts` (세션 시작/종료)
  - `src/services/authService.ts` (로그인/회원가입)
  - `src/services/counselingService.ts` (상담 API)
  - `src/services/emotionService.ts` (감정 API)
  - `src/services/contentService.ts` (피드백/시청 기록 API)
  - `src/services/userService.ts` (사용자 API)

#### 1-9. 페이지 컴포넌트 구현
- [ ] **1-9-1. LoginPage 컴포넌트**
  - 로그인 폼 UI (이메일, 비밀번호 입력)
  - 현재는 더미 로그인 처리
  - UserContext에 사용자 정보 저장

- [ ] **1-9-2. SessionPage 컴포넌트**
  - 상담 시작하기 버튼
  - 새 세션 생성 후 이전 대화 초기화
  - 세션 상태 표시

- [ ] **1-9-3. OverlaySurvey 컴포넌트**
  - Full-screen Overlay 형태
  - 사전문진/사후문진 동일 문항 사용
  - 이모지 기반 간단 응답 저장

- [ ] **1-9-4. DashboardLayout 컴포넌트**
  - 좌측 사이드바 (메뉴: 홈, 상담, 기록, 마이페이지)
  - 상단 헤더 (사용자 정보, 로그아웃 버튼)
  - 메인 콘텐츠 영역

- [ ] **1-9-5. DashboardPage (탭별 페이지)**
  ```typescript
  // 홈 탭
  - 오늘의 감정 요약 표시
  - 현재 세션 상태와 사전/사후 Delta 표시
  - 최근 상담 내용 표시
  
  // 상담 탭
  - 상담 시작 버튼
  - 대화 박스 영역 (메시지 표시)
  - 사전/사후 문진 오버레이 진입
  
  // 기록 탭
  - 감정 기록 목록 (더미 데이터)
  - 날짜별 감정 필터링
  - 내가 위로받은 콘텐츠 기록
  
  // 마이페이지 탭
  - 프로필 정보 수정
  - 설정 변경
  ```

#### 1-10. 라우팅 구현
- [ ] **1-10-1. 인덱스 기반 라우팅 설정**
  ```typescript
  // src/App.tsx
  const [currentPage, setCurrentPage] = useState('login');
  
  return (
    <>
      {currentPage === 'login' && <LoginPage />}
      {currentPage === 'session' && <SessionPage />}
      {currentPage === 'survey' && <OverlaySurvey />}
      {currentPage === 'dashboard' && <DashboardPage />}
    </>
  );
  ```

  또는 React Router 사용 (선택)

- [ ] **1-10-2. 보호된 페이지 구현**
  - 로그인하지 않으면 LoginPage로 리다이렉트

#### 1-11. 스타일 및 레이아웃 폴리싱
- [ ] **1-11-1. 전역 스타일 설정**
  - `src/styles/globals.css` 작성

- [ ] **1-11-2. 반응형 디자인 검토**
  - 모바일 (375px) / 태블릿 (768px) / 데스크톱 (1024px) 확인

#### 1-12. 테스트 실행
- [ ] **1-12-1. 개발 서버 실행**
  ```bash
  npm run dev
  ```
  - http://localhost:5173 접속 확인

- [ ] **1-12-2. 페이지 로딩 확인**
  - 모든 페이지 로드 성공
  - 페이지 간 네비게이션 정상 작동

- [ ] **1-12-3. 콘솔 오류 확인**
  - 브라우저 개발자 도구에서 오류 없음

- [ ] **1-12-4. Context 상태 확인**
  - 사용자 정보 저장/로드 확인
  - 감정 상태 업데이트 확인

**Phase 1 완료 체크**:
- [x] Vite + React + TypeScript 환경 완성
- [x] Tailwind CSS 설정 완료
- [x] Context API로 전역 상태 관리 시스템 구축
- [x] 모든 주요 페이지 UI 구현
- [x] 개발 서버에서 오류 없이 실행됨

---

## 🟡 Phase 2: 백엔드 기본 구축 (FastAPI + Supabase)

**목표**: FastAPI 서버 설정, Supabase 연결, 기본 API 엔드포인트 구현  
**소요 시간**: 약 4-6시간  
**선행 조건**: Phase 1 완료

### Phase 2 세부 체크리스트

#### 2-1. Python 환경 설정
- [ ] **2-1-1. Python 버전 확인**
  ```bash
  python --version
  # Python 3.9 이상 권장
  ```

- [ ] **2-1-2. 가상 환경 생성**
  ```bash
  cd backend
  python -m venv venv
  venv\Scripts\activate  # Windows
  # source venv/bin/activate  # macOS/Linux
  ```

- [ ] **2-1-3. requirements.txt 생성**
  ```
  fastapi==0.104.0
  uvicorn==0.24.0
  pydantic==2.4.0
  pydantic-settings==2.0.0
  python-dotenv==1.0.0
  openai==1.3.0
  google-api-python-client==1.12.0
  supabase==2.4.0
  python-jose==3.3.0
  passlib==1.7.4
  python-multipart==0.0.6
  ```

- [ ] **2-1-4. 라이브러리 설치**
  ```bash
  pip install -r requirements.txt
  ```

#### 2-2. FastAPI 프로젝트 구조 생성
- [ ] **2-2-1. backend/ 하위 폴더 생성**
  ```
  backend/
  ├── app/
  │   ├── routers/
  │   │   ├── __init__.py
  │   │   ├── auth.py
  │   │   ├── session.py
  │   │   ├── counseling.py
  │   │   ├── emotion.py
  │   │   ├── content.py
  │   │   ├── notification.py
  │   │   └── user.py
  │   ├── schemas/
  │   │   ├── __init__.py
  │   │   ├── auth_schema.py
  │   │   ├── emotion_schema.py
  │   │   ├── counseling_schema.py
  │   │   └── common_schema.py
  │   ├── services/
  │   │   ├── __init__.py
  │   │   ├── ai_service.py
  │   │   ├── session_service.py
  │   │   ├── emotion_service.py
  │   │   ├── recommendation_service.py
  │   │   ├── notification_service.py
  │   │   ├── scheduler_service.py
  │   │   └── supabase_service.py
  │   ├── __init__.py
  │   ├── main.py
  │   ├── config.py
  │   └── dependencies.py
  ├── venv/
  ├── .env
  ├── requirements.txt
  └── README.md
  ```

#### 2-3. FastAPI 메인 앱 설정
- [ ] **2-3-1. app/main.py 작성**
  ```python
  from fastapi import FastAPI
  from fastapi.middleware.cors import CORSMiddleware
  from app.routers import auth, session, counseling, emotion, content, notification, user
  
  app = FastAPI(
      title="MoodPick API",
      description="AI 기반 심리 상담 서비스",
      version="1.0.0"
  )
  
  # CORS 설정
  app.add_middleware(
      CORSMiddleware,
      allow_origins=[
          "http://localhost:5173",
          "http://localhost:3000",
      ],
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )
  
  # 라우트 등록
  app.include_router(auth.router)
  app.include_router(session.router)
  app.include_router(counseling.router)
  app.include_router(emotion.router)
  app.include_router(content.router)
  app.include_router(notification.router)
  app.include_router(user.router)
  
  @app.get("/")
  async def root():
      return {"message": "MoodPick API is running"}
  
  if __name__ == "__main__":
      import uvicorn
      uvicorn.run(app, host="0.0.0.0", port=8000)
  ```

#### 2-4. 환경 설정 및 의존성
- [ ] **2-4-1. app/config.py 작성**
  ```python
  from pydantic_settings import BaseSettings
  
  class Settings(BaseSettings):
      SUPABASE_URL: str
      SUPABASE_KEY: str
      OPENAI_API_KEY: str
      YOUTUBE_API_KEY: str
      SERVER_PORT: int = 8000
      SERVER_HOST: str = "0.0.0.0"
      DEBUG: bool = True
      
      class Config:
          env_file = ".env"
  
  settings = Settings()
  ```

- [ ] **2-4-2. app/dependencies.py 작성**
  ```python
  from app.config import settings
  from app.services.supabase_service import SupabaseService
  from app.services.ai_service import AIService
  
  def 가져오기_수파베이스_서비스():
      return SupabaseService(settings.SUPABASE_URL, settings.SUPABASE_KEY)
  
  def 가져오기_에이아이_서비스():
      return AIService(settings.OPENAI_API_KEY)
  ```

#### 2-5. Pydantic 스키마 작성
- [ ] **2-5-1. app/schemas/common_schema.py**
  ```python
  from pydantic import BaseModel
  
  class 응답_기본(BaseModel):
      success: bool
      message: str
      data: dict | None = None
  ```

- [ ] **2-5-2. app/schemas/auth_schema.py**
  ```python
  class 회원가입_요청(BaseModel):
      email: str
      password: str
      name: str
  
  class 로그인_요청(BaseModel):
      email: str
      password: str
  
  class 사용자_응답(BaseModel):
      id: str
      email: str
      name: str
      created_at: str
  ```

- [ ] **2-5-3. app/schemas/emotion_schema.py**
  ```python
  class 감정분석_요청(BaseModel):
      text: str
  
  class 감정분석_응답(BaseModel):
      emotion: str
      intensity: float
      recommendations: list[str]
  ```

- [ ] **2-5-4. app/schemas/counseling_schema.py**
  ```python
  class 상담_메시지_요청(BaseModel):
      user_id: str
      message: str
  
  class 상담_메시지_응답(BaseModel):
      counselor_message: str
      emotion_analysis: dict
      recommended_video: dict | None = None
  ```

#### 2-6. Supabase 연결 서비스
- [ ] **2-6-1. app/services/supabase_service.py 작성**
  ```python
  from supabase import create_client
  
  class SupabaseService:
      def __init__(self, url: str, key: str):
          self.client = create_client(url, key)
      
      def 사용자_조회(self, user_id: str):
          return self.client.table("users").select("*").eq("id", user_id).execute()
      
      def 사용자_생성(self, email: str, name: str):
          return self.client.table("users").insert({
              "email": email,
              "name": name
          }).execute()
      
      def 감정_기록_저장(self, user_id: str, emotion: str, intensity: float, context: str):
          return self.client.table("emotion_records").insert({
              "user_id": user_id,
              "emotion": emotion,
              "intensity": intensity,
              "context": context
          }).execute()
      
      def 감정_기록_조회(self, user_id: str, limit: int = 10):
          return self.client.table("emotion_records").select("*").eq(
              "user_id", user_id
          ).order("timestamp", desc=True).limit(limit).execute()
      
      def 상담_기록_저장(self, user_id: str, session_id: str, user_msg: str, 
                         counselor_msg: str, video_id: str = None):
          return self.client.table("counseling_histories").insert({
              "user_id": user_id,
              "session_id": session_id,
              "user_message": user_msg,
              "counselor_response": counselor_msg,
              "recommended_video_id": video_id
          }).execute()
  ```

#### 2-7. 인증 라우트 작성
- [ ] **2-7-1. app/routers/auth.py 작성**
  ```python
  from fastapi import APIRouter, Depends
  
  router = APIRouter(prefix="/auth", tags=["인증"])
  
  @router.post("/register")
  async def 회원가입(요청: 회원가입_요청, db: SupabaseService = Depends(...)):
      # 이메일 중복 확인
      # 사용자 생성
      # 토큰 반환
      pass
  
  @router.post("/login")
  async def 로그인(요청: 로그인_요청, db: SupabaseService = Depends(...)):
      # 사용자 조회
      # 비밀번호 확인
      # 토큰 반환
      pass
  
  @router.get("/me")
  async def 현재_사용자_정보():
      # 토큰 검증
      # 사용자 정보 반환
      pass
  
  @router.post("/logout")
  async def 로그아웃():
      pass
  ```

#### 2-8. 감정 분석 라우트 작성
- [ ] **2-8-1. app/routers/emotion.py 작성**
  ```python
  @router.post("/emotion/analyze")
  async def 감정분석(요청: 감정분석_요청, db: SupabaseService = Depends(...)):
      # AI로 감정 분석
      # DB에 저장
      # 결과 반환
      pass
  
  @router.get("/emotion/records")
  async def 감정_기록_조회(user_id: str, db: SupabaseService = Depends(...)):
      # 사용자의 감정 기록 조회
      # 최근 10개 반환
      pass
  ```

#### 2-9. 상담 라우트 작성
- [ ] **2-9-1. app/routers/counseling.py 작성**
  ```python
  @router.post("/counseling/message")
  async def 상담_메시지(요청: 상담_메시지_요청):
      # AI 서비스 호출
      # Function Calling 처리
      # 결과 저장 및 반환
      pass
  
  @router.get("/counseling/history")
  async def 상담_이력_조회(user_id: str, db: SupabaseService = Depends(...)):
      # 사용자의 상담 이력 조회
      pass
  ```

#### 2-10. 사용자 라우트 작성
- [ ] **2-10-1. app/routers/user.py 작성**
  ```python
  @router.get("/user/profile")
  async def 프로필_조회(user_id: str, db: SupabaseService = Depends(...)):
      pass
  
  @router.put("/user/profile")
  async def 프로필_수정(user_id: str, 이름: str, 프로필_이미지: str = None):
      pass
  
  @router.get("/user/preferences")
  async def 설정_조회(user_id: str):
      pass
  
  @router.put("/user/preferences")
  async def 설정_수정(user_id: str, 설정: dict):
      pass
  ```

#### 2-11. 세션 및 알림 라우트 작성
- [ ] **2-11-1. app/routers/session.py 작성**
  ```python
  @router.post("/session/start")
  async def 세션_시작(user_id: str):
      pass

  @router.post("/session/end")
  async def 세션_종료(session_id: str):
      pass
  ```

- [ ] **2-11-2. app/routers/notification.py 작성**
  ```python
  @router.post("/notification/evening-reminder")
  async def 저녁_알림_발송():
      # 매일 밤 10시 사후문진 유도 알림
      pass
  ```

#### 2-12. AI Service 기초 구현
- [ ] **2-12-1. app/services/ai_service.py 작성**
  ```python
  from openai import OpenAI
  
  class AIService:
      def __init__(self, api_key: str):
          self.client = OpenAI(api_key=api_key)
          self.model = "gpt-4o-mini"
      
      def 상담_실행(self, user_message: str, user_history: list = None):
          # 시스템 프롬프트 설정
          # 메시지 구성
          # GPT-4o-mini 호출
          # 응답 반환
          pass
      
      def 감정_분석(self, text: str):
          # 텍스트에서 감정 추출
          # 강도 계산
          # 결과 반환
          pass
  ```

#### 2-13. Supabase 데이터베이스 스키마 생성
- [ ] **2-13-1. Supabase 대시보드에서 테이블 생성**
  - `users` 테이블
  - `counseling_sessions` 테이블
  - `survey_responses` 테이블
  - `emotion_records` 테이블
  - `counseling_histories` 테이블
  - `content_feedback` 테이블
  - `watched_content_records` 테이블
  - `scheduled_notifications` 테이블

- [ ] **2-13-2. 인덱스 생성**
  ```sql
  CREATE INDEX idx_counseling_sessions_user_id ON counseling_sessions(user_id);
  CREATE INDEX idx_survey_responses_session_id ON survey_responses(session_id);
  CREATE INDEX idx_emotion_records_user_id ON emotion_records(user_id);
  CREATE INDEX idx_emotion_records_timestamp ON emotion_records(timestamp);
  CREATE INDEX idx_counseling_user_id ON counseling_histories(user_id);
  CREATE INDEX idx_content_feedback_user_id ON content_feedback(user_id);
  ```

#### 2-14. API 문서 확인
- [ ] **2-14-1. 개발 서버 실행**
  ```bash
  python -m uvicorn app.main:app --reload --port 8000
  ```

- [ ] **2-14-2. Swagger UI 확인**
  - http://localhost:8000/docs 접속
  - 모든 엔드포인트 나열됨 확인

- [ ] **2-14-3. ReDoc 확인**
  - http://localhost:8000/redoc 접속

#### 2-15. 기본 테스트
- [ ] **2-15-1. POST /session/start 테스트**
- [ ] **2-15-2. POST /auth/register 테스트**
- [ ] **2-15-3. POST /auth/login 테스트**
- [ ] **2-15-4. GET /auth/me 테스트**
- [ ] **2-15-5. POST /emotion/analyze 테스트**
- [ ] **2-15-6. GET /emotion/records 테스트**

**Phase 2 완료 체크**:
- [x] FastAPI 프로젝트 구조 완성
- [x] 모든 주요 라우트 구현 (인증, 감정, 상담, 사용자)
- [x] Supabase 연결 완료
- [x] Swagger UI에서 모든 엔드포인트 확인 가능
- [x] 개발 서버에서 오류 없이 실행됨

---

## 🟠 Phase 3: AI 통합 및 Function Calling 구현

**목표**: GPT-4o-mini 완전 연동, Function Calling 도구 정의, YouTube 검색 통합  
**소요 시간**: 약 4-6시간  
**선행 조건**: Phase 2 완료

### Phase 3 세부 체크리스트

#### 3-1. AI 폴더 구조 생성
- [ ] **3-1-1. ai/ 하위 폴더 생성**
  ```
  ai/
  ├── prompts/
  │   ├── system_prompt.md
  │   ├── counseling_prompt.txt
  │   └── analysis_prompt.txt
  ├── function_definitions.py
  ├── tools/
  │   ├── __init__.py
  │   ├── youtube_search.py
  │   └── emotion_mapper.py
  ├── __init__.py
  └── README.md
  ```

#### 3-2. 시스템 프롬프트 작성
- [ ] **3-2-1. ai/prompts/system_prompt.md 작성**
  ```
  당신은 MoodPick이라는 AI 심리 상담 서비스의 상담사입니다.
  
  역할:
  - 사용자의 감정 상태를 공감하고 세심하게 들어주기
  - 심리학 기반의 따뜻한 조언 제공
  - 감정 분석과 맞춤 추천 제공
  
  행동 규칙:
  1. 사용자의 입력을 공감으로 시작하기
  2. 상황을 정확히 이해하도록 요약해 주기
  3. analyze_emotion() 함수로 감정을 정확히 파악하기
  4. search_youtube_video() 호출로 추천 콘텐츠 제공하기
  5. 필요시 get_session_summary()로 맥락 파악하기
  
  응답 형식:
  - 항상 따뜻하고 인간적인 톤 유지
  - 공감 + 조언 + 추천의 구조
  ```

#### 3-3. Function Definitions 작성
- [ ] **3-3-1. ai/function_definitions.py 작성**
  ```python
  FUNCTION_DEFINITIONS = [
    {
      "name": "analyze_emotion",
      "description": "사용자의 텍스트 입력에서 감정을 분석하고 강도를 평가합니다",
      "parameters": {
        "type": "object",
        "properties": {
          "text": {
            "type": "string",
            "description": "분석할 텍스트"
          }
        },
        "required": ["text"]
      }
    },
    {
      "name": "search_youtube_video",
      "description": "사용자의 감정과 기분에 맞는 유튜브 영상을 검색합니다",
      "parameters": {
        "type": "object",
        "properties": {
          "query": {
            "type": "string",
            "description": "검색 키워드"
          },
          "emotion": {
            "type": "string",
            "description": "현재 사용자의 감정"
          }
        },
        "required": ["query"]
      }
    },
    {
      "name": "get_session_summary",
      "description": "세션의 상담 기록과 사전/사후 문진 변화를 조회합니다",
      "parameters": {
        "type": "object",
        "properties": {
          "session_id": {
            "type": "string",
            "description": "세션 ID"
          },
          "days": {
            "type": "integer",
            "description": "조회할 기간 (일 단위, 기본값: 7)"
          }
        },
        "required": ["session_id"]
      }
    },
    {
      "name": "record_content_feedback",
      "description": "추천 영상에 대한 좋아요/싫어요 피드백을 저장합니다",
      "parameters": {
        "type": "object",
        "properties": {
          "content_id": {
            "type": "string",
            "description": "유튜브 콘텐츠 ID"
          },
          "feedback": {
            "type": "string",
            "description": "좋아요 또는 싫어요"
          }
        },
        "required": ["content_id", "feedback"]
      }
    }
  ]

  def 함수_가져오기():
    return FUNCTION_DEFINITIONS
  ```

#### 3-4. YouTube API 통합
- [ ] **3-4-1. ai/tools/youtube_search.py 작성**
  ```python
  from googleapiclient.discovery import build
  
  def 유튜브영상검색(query: str, api_key: str, max_results: int = 3):
      """
      YouTube Data API v3를 사용하여 영상 검색
      """
      youtube = build("youtube", "v3", developerKey=api_key)
      request = youtube.search().list(
          part="snippet",
          q=query,
          maxResults=max_results,
          type="video",
          order="relevance"
      )
      results = request.execute()
      
      video_list = []
      for item in results.get("items", []):
          video_list.append({
              "id": item["id"]["videoId"],
              "title": item["snippet"]["title"],
              "description": item["snippet"]["description"],
              "thumbnail": item["snippet"]["thumbnails"]["default"]["url"]
          })
      
      return video_list
  ```

#### 3-5. 감정 분석 도구
- [ ] **3-5-1. ai/tools/emotion_mapper.py 작성**
  ```python
  def 감정분석(text: str):
      """
      텍스트에서 감정을 분석하고 강도를 계산
      """
      # 간단한 임시 구현 (실제로는 AI로 처리)
      emotions_keywords = {
          "행복": ["좋아", "기쁘", "행복", "즐거워"],
          "슬픔": ["슬프", "외로워", "힘들어", "우울"],
          "불안": ["불안", "걱정", "두려워", "긴장"],
          "화남": ["화나", "짜증", "화나", "열받아"],
          "스트레스": ["스트레스", "피곤", "힘들어", "압박"]
      }
      
      emotion = "중립"
      intensity = 0.5
      
      for emotion_name, keywords in emotions_keywords.items():
          if any(kw in text for kw in keywords):
              emotion = emotion_name
              intensity = min(1.0, len([kw for kw in keywords if kw in text]) / 2)
              break
      
      return {
          "emotion": emotion,
          "intensity": intensity,
          "recommendations": ["명상", "음악 감상", "산책"]
      }
  ```

#### 3-6. AI Service 완전 구현
- [ ] **3-6-1. app/services/ai_service.py 전체 작성**
  ```python
  from openai import OpenAI
  from ai.function_definitions import FUNCTION_DEFINITIONS
  from ai.tools.youtube_search import 유튜브영상검색
  from ai.tools.emotion_mapper import 감정분석
  
  class AIService:
      def __init__(self, api_key: str, youtube_api_key: str):
          self.client = OpenAI(api_key=api_key)
          self.youtube_api_key = youtube_api_key
          self.model = "gpt-4o-mini"
      
      def 상담_실행(self, user_message: str, user_history: list = None):
          """
          사용자 메시지를 받아서 AI 상담 응답과 함수 호출 결과 반환
          """
          # 시스템 프롬프트 로드
          with open("ai/prompts/system_prompt.md", "r", encoding="utf-8") as f:
              system_prompt = f.read()
          
          # 이전 대화 내역 처리
          messages = [{"role": "user", "content": user_message}]
          if user_history:
              messages = user_history + messages
          
          # Function Calling을 사용하여 GPT 호출
          response = self.client.chat.completions.create(
              model=self.model,
              messages=[
                  {"role": "system", "content": system_prompt},
                  *messages
              ],
              functions=FUNCTION_DEFINITIONS,
              function_call="auto"
          )
          
          # 응답 처리
          return self._처리_함수_응답(response)
      
      def _처리_함수_응답(self, response):
          """
          Function Calling 응답 처리
          """
          result = {
              "counselor_message": "",
              "emotion_analysis": None,
              "recommended_video": None,
              "functions_called": []
          }
          
          if response.choices[0].finish_reason == "function_call":
              function_call = response.choices[0].message.function_call
              
                if function_call.name == "analyze_emotion":
                  emotion_result = analyze_emotion(function_call.arguments["text"])
                  result["emotion_analysis"] = emotion_result
                  result["functions_called"].append("analyze_emotion")
              
                elif function_call.name == "search_youtube_video":
                  query = function_call.arguments["query"]
                  videos = search_youtube_video(query, self.youtube_api_key)
                  if videos:
                      result["recommended_video"] = videos[0]
                  result["functions_called"].append("search_youtube_video")
              
                elif function_call.name == "get_session_summary":
                  # DB에서 조회 (별도 구현)
                  result["functions_called"].append("get_session_summary")
          
          else:
              # 일반 메시지 응답
              result["counselor_message"] = response.choices[0].message.content
          
          return result
  ```

#### 3-7. 상담 엔드포인트 완성
- [ ] **3-7-1. app/routers/counseling.py 완전 구현**
  ```python
  from app.services.ai_service import AIService
  
  @router.post("/counseling/message")
  async def 상담_메시지(
      요청: 상담_메시지_요청,
      ai_service: AIService = Depends(가져오기_에이아이_서비스),
      db: SupabaseService = Depends(가져오기_수파베이스_서비스)
  ):
      # AI 서비스에서 상담 실행
      ai_response = ai_service.run_counseling(요청.message)
      
      # DB에 기록 저장
        db.save_counseling_history(
          user_id=요청.user_id,
          session_id="session-id",
          user_msg=요청.message,
          counselor_msg=ai_response["counselor_message"],
          video_id=ai_response["recommended_video"]["id"] if ai_response.get("recommended_video") else None
      )
      
      # 감정 분석 결과가 있으면 저장
      if ai_response.get("emotion_analysis"):
            db.save_emotion_record(
              user_id=요청.user_id,
              emotion=ai_response["emotion_analysis"]["emotion"],
              intensity=ai_response["emotion_analysis"]["intensity"],
              context=요청.message
          )
      
      return ai_response
  ```

#### 3-8. 프론트엔드 연동 준비
- [ ] **3-8-1. 백엔드 API 응답 형식 확인**
  - `/counseling/message` 응답이 프론트엔드와 일치하는지 검증

- [ ] **3-8-2. 프론트엔드 서비스 업데이트**
  ```typescript
  // src/services/counselingService.ts
  export async function sendCounselingMessage(userId: string, message: string) {
      const response = await fetch('http://localhost:8000/counseling/message', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
              user_id: userId,
              message: message
          })
      });
      return response.json();
  }
  ```

#### 3-9. Function Calling 테스트
- [ ] **3-9-1. Swagger UI에서 /counseling/message 테스트**
  - 요청: `{"user_id": "test-user", "message": "요새 일이 너무 많아서 스트레스받아"}`
  - 응답 확인: 상담 메시지, 감정 분석, YouTube 추천

- [ ] **3-9-2. YouTube 영상 반환 확인**
  - 서버 응답에 영상 ID, 제목, 썸네일 포함 확인

#### 3-10. AI 응답 품질 개선
- [ ] **3-10-1. 시스템 프롬프트 재조정**
  - 한국어 더 자연스럽게
  - 공감 부분 강화

- [ ] **3-10-2. 감정 분석 개선**
  - 더 정확한 감정 분석을 위해 OpenAI Embeddings 사용 (선택)

**Phase 3 완료 체크**:
- [x] AI 폴더 구조 완성
- [x] Function Calling 정의 및 구현 완료
- [x] YouTube API 통합 완료
- [x] 감정 분석 서비스 완료
- [x] 프론트엔드 ↔ 백엔드 상담 기능 작동 확인

---

## 🔴 Phase 4: 프론트엔드 ↔ 백엔드 통합 및 Supabase 인증

**목표**: 실제 데이터 저장 및 조회, Supabase 인증 연동, 전체 기능 테스트  
**소요 시간**: 약 3-4시간  
**선행 조건**: Phase 3 완료

### Phase 4 세부 체크리스트

#### 4-1. Supabase 인증 설정
- [ ] **4-1-1. Supabase 대시보드에서 소셜 로그인 설정**
  - Google OAuth 활성화
  - GitHub OAuth 활성화

- [ ] **4-1-2. 리다이렉트 URL 설정**
  - `http://localhost:5173/callback`

- [ ] **4-1-3. 클라이언트 ID/시크릿 복사**

#### 4-2. 프론트엔드 Supabase 인증 연동
- [x] **4-2-1. src/lib/supabaseClient.ts 작성**
  ```typescript
  import { createClient } from '@supabase/supabase-js';
  
  const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
  const supabaseKey = import.meta.env.VITE_SUPABASE_KEY;
  
  export const supabase = createClient(supabaseUrl, supabaseKey);
  ```

- [x] **4-2-2. .env 파일 추가**
  ```
  NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
  NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
  NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_key
  ```

- [x] **4-2-3. 세션 시작/종료 흐름 연결**
  - 로그인 직후 세션 시작하기 버튼이 보이도록 설정
  - 상담 종료 시 사후문진 오버레이로 전환

- [x] **4-2-4. LoginPage에서 Supabase Auth 구현**
  ```typescript
  const 소셜로그인_처리 = async (provider: 'google' | 'github') => {
      const { data, error } = await supabase.auth.signInWithOAuth({
          provider: provider,
          options: { redirectTo: `${window.location.origin}/callback` }
      });
  };
  ```

#### 4-3. 콜백 페이지 작성
- [ ] **4-3-1. CallbackPage 컴포넌트 작성**
  ```typescript
  // src/components/pages/CallbackPage.tsx
  useEffect(() => {
      supabase.auth.onAuthStateChange(async (event, session) => {
          if (session) {
              setUser(session.user);
              navigate('/onboarding');
          }
      });
  }, []);
  ```

#### 4-4. 데이터 저장 및 조회 테스트
- [x] **4-4-1. 사전문진 완료 후 세션/문진 정보 DB에 저장**
  ```typescript
  const 사전문진_완료 = async (answers: Record<string, string>) => {
      const response = await surveyService.문진_저장(user.id, 'pre', answers);
      setSurveyState(response);
  };
  ```

- [ ] **4-4-2. 대시보드 로드 시 사용자 데이터 조회**
  ```typescript
  useEffect(() => {
      const 사용자_데이터_로드 = async () => {
          const 감정_기록 = await emotionService.감정_기록_조회(user.id);
          const 상담_이력 = await counselingService.상담_이력_조회(user.id);
          const 시청_기록 = await contentService.시청_기록_조회(user.id);
          setEmotionHistory(감정_기록);
          setCounselingHistory(상담_이력);
          setContentHistory(시청_기록);
      };
      사용자_데이터_로드();
  }, [user]);
  ```

#### 4-5. 상담 기능 완전 테스트
- [ ] **4-5-1. 프론트엔드에서 상담 메시지 전송**
  ```typescript
  const 상담_메시지_전송 = async (message: string) => {
      const response = await counselingService.상담_메시지_전송(user.id, message);
      
      // 상담사 응답 표시
      setCounselingMessages([
          ...counselingMessages,
          { role: 'user', content: message },
          { role: 'counselor', content: response.counselor_message }
      ]);
      
      // 감정 업데이트
      if (response.emotion_analysis) {
          setCurrentEmotion(response.emotion_analysis);
      }
      
      // 영상 재생
      if (response.recommended_video) {
          playVideo(response.recommended_video);
      }
  };
  ```

- [ ] **4-5-2. YouTube 영상 자동 재생 및 전체화면 토글**
  ```typescript
  // src/components/features/MediaPlayer.tsx
  const playVideo = (video: VideoInfo) => {
      const embedUrl = `https://www.youtube.com/embed/${video.id}`;
      setCurrentVideo(embedUrl);
      // autoplay 속성으로 자동 재생
  };
  ```

- [x] **4-5-3. 콘텐츠 피드백 저장**
  - 영상 하단 👍/👎 선택 시 content_feedback 테이블에 저장

#### 4-6. 감정 기록 저장 및 표시
- [ ] **4-6-1. 감정 기록 테이블에 저장 확인**
  - Supabase 대시보드에서 emotion_records 테이블 확인
  - 데이터가 제대로 저장되는지 검증

- [ ] **4-6-2. 감정 기록 페이지에서 표시**
  ```typescript
  // src/components/pages/EmotionHistoryPage.tsx
  useEffect(() => {
      const 감정_기록_로드 = async () => {
          const records = await emotionService.감정_기록_조회(user.id);
          setEmotionRecords(records);
      };
      감정_기록_로드();
  }, []);
  ```

#### 4-7. 상담 이력 저장 및 표시
- [ ] **4-7-1. 상담 기록 테이블에 저장 확인**
  - Supabase 대시보드에서 counseling_histories 테이블 확인

- [ ] **4-7-2. 기록 페이지에서 상담 이력 및 시청 기록 표시**
  ```typescript
  // src/components/pages/EmotionHistoryPage.tsx - 상담 탭
  상담 기록 목록 표시
  날짜, 상담 내용, 감정, 피드백, 시청 콘텐츠 표시
  ```

- [ ] **4-7-3. "내가 위로받은 콘텐츠" 뷰 확인**
  - 마이페이지 또는 대시보드 하위에서 영상 기록 모아보기

#### 4-8. 에러 처리 추가
- [ ] **4-8-1. 네트워크 오류 처리**
  - API 응답 오류 시 사용자 피드백

- [ ] **4-8-2. 인증 오류 처리**
  - 토큰 만료 시 재로그인 유도

- [ ] **4-8-3. 데이터 검증**
  - 입력값 검증 추가

#### 4-9. 전체 플로우 테스트
- [ ] **4-9-1. 로그인 → 상담 시작 → 사전문진 → 상담 → 사후문진 전체 흐름 테스트**

- [ ] **4-9-2. 각 페이지 데이터 저장 및 로드 확인**

- [ ] **4-9-3. YouTube 영상 자동 재생 및 전체화면 확인**

- [ ] **4-9-4. 밤 10시 알림이 사후문진으로 유도하는지 확인**

#### 4-10. 성능 최적화
- [ ] **4-10-1. 불필요한 API 재요청 제거**
  - React.memo, useMemo 활용

- [ ] **4-10-2. 이미지 최적화**
  - 썸네일 이미지 캐싱

**Phase 4 완료 체크**:
- [ ] Supabase 인증 완전 연동
- [ ] 데이터 저장 및 조회 확인
- [ ] YouTube 자동 재생 작동
- [ ] 전체 기능 테스트 완료
- [ ] 오류 처리 구현
- [x] 세션/사전문진/사후문진/콘텐츠 피드백 저장 로직 1차 구현

#### Phase 4 진행 메모 (2026-04-03)
- 프론트에 Supabase 클라이언트 및 로그인/로그아웃/OAuth 버튼 연동 완료
- 세션 시작/종료 시 DB 저장 로직 연결 완료
- 사전문진/사후문진 저장 로직 연결 완료
- 콘텐츠 👍/👎 피드백 저장 및 시청 기록 저장 로직 연결 완료
- 남은 작업: Supabase 프로젝트 실제 설정, OAuth 공급자 콘솔 설정, 실환경 E2E 테스트

---

## 🟣 Phase 5: 안정화 및 최적화

**목표**: 버그 수정, 사용자 경험 개선, 배포 준비  
**소요 시간**: 약 2-3시간  
**선행 조건**: Phase 4 완료

### Phase 5 세부 체크리스트

#### 5-1. 버그 찾기 및 수정
- [ ] **5-1-1. 콘솔 오류 제거**
  - 브라우저 개발자 도구에서 모든 오류 확인 및 수정

- [ ] **5-1-2. API 응답 오류 처리**
  - 타임아웃, 500 에러 등 처리

- [ ] **5-1-3. 상태 관리 버그 수정**
  - Context 스테이트 불일치 문제

#### 5-2. 로깅 및 모니터링
- [ ] **5-2-1. 백엔드 로깅 추가**
  ```python
  import logging
  logger = logging.getLogger(__name__)
  logger.info(f"사용자 {user_id}가 상담을 시작했습니다")
  ```

- [ ] **5-2-2. 프론트엔드 에러 로깅**
  ```typescript
  try {
      // ...
  } catch (error) {
      console.error("상담 메시지 전송 실패:", error);
      // 에러 트래킹 서비스에 보냄
  }
  ```

#### 5-3. 보안 강화
- [ ] **5-3-1. JWT 토큰 검증 구현**
  - 백엔드에서 모든 엔드포인트에 인증 추가

- [ ] **5-3-2. CORS 설정 검토**
  - 프로덕션에서는 특정 도메인만 허용

- [ ] **5-3-3. 환경 변수 보안**
  - API 키를 서버에서만 관리

#### 5-4. 사용자 경험 개선
- [ ] **5-4-1. 로딩 상태 표시**
  ```typescript
  if (isLoading) {
      return <LoadingSpinner />;
  }
  ```

- [ ] **5-4-2. 에러 메시지 개선**
  - 사용자 친화적인 메시지

- [ ] **5-4-3. 반응형 디자인 최종 확인**
  - 모바일 (375px) / 태블릿 (768px) / 데스크톱 (1024px)

#### 5-5. 성능 측정
- [ ] **5-5-1. API 응답 시간 측정**
  - 모든 엔드포인트가 2초 이내 응답

- [ ] **5-5-2. 프론트엔드 성능**
  - Lighthouse 스코어 80 이상

- [ ] **5-5-3. 데이터베이스 쿼리 최적화**
  - 불필요한 조인 제거

#### 5-6. 문서화
- [ ] **5-6-1. API 문서 완성**
  - Swagger UI에서 모든 엔드포인트 설명

- [ ] **5-6-2. 프론트엔드 컴포넌트 문서**
  - 주요 컴포넌트의 props, 사용 예시

- [ ] **5-6-3. 배포 가이드 작성**

#### 5-7. 배포 준비
- [ ] **5-7-1. 프론트엔드 빌드 및 최적화**
  ```bash
  npm run build
  npm run preview
  ```

- [ ] **5-7-2. 백엔드 배포 환경 설정**
  - Render.com 또는 Railway 등에서 배포 준비

- [ ] **5-7-3. Supabase 프로덕션 설정**
  - 백업, 보안 규칙 설정

#### 5-8. 최종 통합 테스트
- [ ] **5-8-1. 각 페이지 재방문하여 테스트**

- [ ] **5-8-2. 상담 기능 다양한 입력으로 테스트**

- [ ] **5-8-3. 데이터 저장 및 조회 재확인**

#### 5-9. 배포
- [ ] **5-9-1. 프론트엔드 배포** (Vercel)
  ```bash
  vercel deploy
  ```

- [ ] **5-9-2. 백엔드 배포** (Render)
  - 환경 변수 설정
  - 데이터베이스 마이그레이션

- [ ] **5-9-3. 도메인 설정** (선택)

#### 5-10. 배포 후 테스트
- [ ] **5-10-1. 프로덕션에서 전체 플로우 테스트**

- [ ] **5-10-2. 오류 모니터링**

- [ ] **5-10-3. 사용자 피드백 수집**

**Phase 5 완료 체크**:
- [x] 모든 버그 수정 완료
- [x] 보안 강화 완료
- [x] 성능 최적화 완료
- [x] 배포 완료
- [x] 프로덕션 모니터링 시작

---

## 8. 개발 환경 설정

---

## 8. 개발 환경 설정

### 프론트엔드 시작

```bash
cd frontend
npm install
npm run dev
```

### 백엔드 시작

```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

### Supabase 설정

1. [Supabase](https://supabase.com) 접속
2. 새 프로젝트 생성
3. 프로젝트 URL과 키 복사
4. `backend/.env`에 저장

### OpenAI API 및 YouTube API

1. [OpenAI](https://openai.com/api) 및 [Google Cloud Console](https://console.cloud.google.com)에서 API 키 발급
2. `.env` 파일에 저장

---

## 9. 코딩 규칙 및 네이밍 컨벤션

### 필수 규칙

1. **설명 텍스트는 한국어로, 코드의 함수명/변수명은 축약 없는 전체 영단어로 작성**
  - ✅ 좋은 예: `analyzeEmotion()`, `getSessionSummary()`, `recordContentFeedback()`
  - ❌ 나쁜 예: `fetch_user()`, `init_session()`, `getUsrHist()` (축약 금지)

2. **함수명: 동사 + 목적어로 명확하게**
   ```python
   # ✅ 좋은 예
   def 사용자_조회(user_id):
   def 감정_분석(text):
   def 유튜브_영상_검색(query):
   
   # ❌ 나쁜 예
   def get_user(user_id):
   def analyze(text):
   def search_video(query):
   ```

3. **변수명: 명확하고 직관적으로**
   ```python
   # ✅ 좋은 예
  currentUserEmotion = "행복"
  counselingResponseMessage = "..."
  youtubeVideoList = [...]
   
   # ❌ 나쁜 예
  cur_emotion = "행복"
  resp_msg = "..."
  video_list = [...]
   ```

4. **상수는 대문자로**
   ```python
   MAX_EMOTION_INTENSITY = 1.0
   DEFAULT_CONVERSATION_LIMIT = 10
   YOUTUBE_API_TIMEOUT = 5
   ```

5. **TypeScript/JavaScript에서도 동일**
   ```typescript
   // ✅ 좋은 예
  const currentUser = userContext.user;
  const calculateEmotionIntensity = (text: string) => { ... };
   
   // ❌ 나쁜 예
   const curr_user = userContext.user;
   const calc_intensity = (text: string) => { ... };
   ```

6. **에러 메시지와 UI 텍스트는 모두 한국어**
   ```python
   raise ValueError("사용자 정보를 찾을 수 없습니다")
   response = {"message": "상담이 저장되었습니다"}
   ```

---

## 10. Git 브랜치 전략

### `main`: 최종 배포 브랜치
- **역할**: 오류 없이 안정적으로 구동되는 최종 완성본 코드가 유지되는 최상위 브랜치
- **규칙**: 해당 브랜치에는 **직접 커밋(Direct Commit) 금지**. 반드시 `develop` 브랜치에서 충분한 테스트를 거친 코드만 병합(Merge)
- **머지 승인 정책**: `main`으로의 병합은 반드시 Pull Request 기반으로 진행하며, **작성자 본인을 제외한 팀원 1명 이상 승인(Approve) 후에만 Merge 가능**

### GitHub 보호 규칙 (필수)
- `main` 브랜치 보호(Branch protection) 활성화
- `Require a pull request before merging` 활성화
- `Require approvals` 값을 **1 이상**으로 설정
- `Restrict who can push to matching branches`를 설정해 직접 푸시 제한

### `develop`: 통합 및 테스트 브랜치
- **역할**: 프론트엔드, 백엔드, AI 모델링 등 각 파트에서 개발된 기능이 하나로 모이는 통합 베이스 브랜치
- **규칙**: 모든 신규 기능 브랜치(`feat/`)는 이 브랜치에서 파생되고, 작업 완료 후에도 이 브랜치로 병합. `main`으로 넘어가기 전 전체 시스템 연동 테스트를 이 브랜치에서 수행

### `feat/`: 신규 기능 개발 브랜치
- **역할**: 개별 팀원이 새로운 기능을 개발할 때 사용하는 개인 작업 브랜치
- **네이밍 규칙**: `feat/기능명`
- **예시**: `feat/chat-ui`, `feat/youtube-mcp`

### `fix/`: 버그 수정 브랜치
- **역할**: `develop` 브랜치 연동 테스트 중 에러가 발생하거나 긴급 수정이 필요할 때 사용하는 브랜치
- **네이밍 규칙**: `fix/수정내용`
- **예시**: `fix/calendar-rendering-error`

### 브랜치 전략 자동화 (로컬 스크립트)
- **초기 1회 설정**
  ```bash
  powershell -ExecutionPolicy Bypass -File .\scripts\setup-git-automation.ps1 -InitializeDevelop
  ```
  - `.githooks`를 Git hooks 경로로 설정
  - `develop` 브랜치가 없으면 자동 생성 및 원격 푸시
  - `main` 직접 커밋 차단, `feat/*`/`fix/*` 커밋 메시지 규칙 적용

- **기능 개발 브랜치 자동화 (`feat/*`)**
  ```bash
  powershell -ExecutionPolicy Bypass -File .\scripts\git-flow.ps1 -Type feat -Name chat-ui -Message "채팅 UI 구현" -Push
  ```

- **버그 수정 브랜치 자동화 (`fix/*`)**
  ```bash
  powershell -ExecutionPolicy Bypass -File .\scripts\git-flow.ps1 -Type fix -Name calendar-rendering-error -Message "캘린더 렌더링 오류 수정" -Push
  ```

- **커밋 메시지 형식 규칙**
  - `feat/브랜치`에서: `feat(scope): 내용`
  - `fix/브랜치`에서: `fix(scope): 내용`
  - 예시: `feat(chat-ui): 채팅 UI 구현`
  - 예시: `fix(calendar-rendering-error): 캘린더 렌더링 오류 수정`

---

## 11. 주요 체크리스트

### 프로젝트 시작 전
- [ ] Supabase 프로젝트 생성
- [ ] OpenAI API 키 발급
- [ ] YouTube Data API 활성화
- [ ] `.env` 파일 작성
- [ ] GitHub 저장소 초기화 (선택)
- [x] Git 브랜치 자동화 설정 (`setup-git-automation.ps1`, `.githooks`)

### 1단계 완료 기준
- [ ] 모든 페이지가 렌더링됨
- [ ] Context API로 상태 관리됨
- [ ] Supabase 연결 (인증만)
- [ ] 콘솔 오류 없음

### 2단계 완료 기준
- [ ] FastAPI 서버 실행됨
- [ ] Supabase 데이터베이스 연결됨
- [ ] GPT-4o-mini 호출 성공
- [ ] YouTube 영상 검색 작동
- [ ] 프론트엔드 ↔ 백엔드 통신 성공

### 3단계 완료 기준
- [ ] 모든 기능이 안정적으로 작동
- [ ] 에러 처리 완료
- [ ] 모바일 반응형 완성
- [ ] 배포 준비 완료

---

## 12. 참고 자료 및 공식 문서

### 프론트엔드
- [React 공식 문서](https://react.dev)
- [Vite 가이드](https://vitejs.dev)
- [Tailwind CSS](https://tailwindcss.com)
- [shadcn/ui](https://ui.shadcn.com)

### 백엔드
- [FastAPI 문서](https://fastapi.tiangolo.com)
- [Supabase 문서](https://supabase.com/docs)
- [OpenAI API](https://platform.openai.com/docs)
- [YouTube Data API](https://developers.google.com/youtube/v3)

### 배포
- [Vercel (프론트엔드)](https://vercel.com)
- [Railway 또는 Render (백엔드)](https://render.com)
- [Supabase 호스팅](https://supabase.com)

---

## 13. FAQ 및 트러블슈팅

### Q: 팀원이 새로운 라이브러리를 추가하고 싶어요
**A**: 1단계가 완료될 때까지는 절대 추가하지 마세요. 3단계부터 필요성을 함께 검토합니다.

### Q: 기존 UI 컴포넌트가 안 맞아요
**A**: 커스터마이징하되, shadcn/ui의 기본 구조는 유지하세요.

### Q: API 응답이 너무 느려요
**A**: 캐싱, 데이터베이스 쿼리 최적화, 백그라운드 작업 처리 등을 검토하세요.

### Q: Supabase 비용이 걱정돼요
**A**: 무료 티어에서 충분히 테스트 가능합니다. 프로덕션 배포 시 비용 확인하세요.

---

**문서 작성일**: 2024년 3월 31일  
**담당팀**: MoodPick 개발팀  
**버전**: 1.0
