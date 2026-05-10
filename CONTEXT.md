# MoodPick Development Context

이 파일은 컨텍스트가 새로 갱신되어도 개발 방향을 잃지 않기 위한 짧은 인수인계 노트입니다.
새 작업을 시작할 때는 `PLAN.md` 전체를 읽기 전에 이 파일을 먼저 확인하세요.

## 현재 실제 구조

- 프론트엔드: `frontend/`
  - Next.js 16, React 19, TypeScript, shadcn/ui, Supabase Auth.
  - 메인 앱 화면은 대부분 `frontend/components/moodpick-dashboard.tsx`에 집중되어 있음.
  - API 클라이언트는 `frontend/lib/api.ts`.
  - Auth 상태와 회원가입/로그인은 `frontend/components/auth-provider.tsx`.
  - 서버 전용 Supabase profile API는 `frontend/app/api/user/profile/route.ts`.
- 백엔드: `backend/`
  - FastAPI.
  - 라우터는 `backend/app/routers/`.
  - Supabase 클라이언트는 `backend/app/services/supabase_service.py`.
  - 설정은 `backend/app/config.py`, 기본 env 파일은 `backend/.env.local`.
- AI: `ai/`
  - 3-agent 구조: Orchestrator, Counselor, Content Recommender.
  - 진입점은 `ai/pipeline.py`.
  - 백엔드에서는 `backend/app/services/ai_service.py`가 AI pipeline을 감쌈.
- DB: `db/migrations/`
  - Supabase/Postgres SQL 마이그레이션으로 스키마 관리.
  - 이미 적용된 DB에 컬럼을 추가할 때는 기존 migration만 수정하지 말고 새 `NNN_*.sql` 파일을 추가한다.
- Docker 개발 환경
  - `docker-compose.yml`은 frontend/backend/db를 함께 띄운다.
  - 프론트는 `pnpm exec next dev --webpack --hostname 0.0.0.0`로 실행한다.
  - Windows Docker bind mount 변경 감지를 위해 frontend는 `WATCHPACK_POLLING`, `CHOKIDAR_USEPOLLING`을 켠다.
  - Docker dev에서는 Turbopack보다 webpack polling이 더 안정적이라 `--webpack`을 명시한다.
  - 백엔드는 `uvicorn ... --reload`와 `WATCHFILES_FORCE_POLLING=true`를 사용한다.
  - Docker 설정을 바꾼 뒤에는 기존 컨테이너를 재생성해야 적용된다.

## 개발 원칙

- `PLAN.md`는 방향 문서지만 오래된 Vite 설명이 섞여 있다. 실제 구현 기준은 현재 코드 구조(Next.js/FastAPI/Supabase)를 따른다.
- DB 스키마 변경은 `db/migrations/`에 새 migration으로 남긴다.
- 이미 적용됐을 가능성이 있는 migration 파일은 함부로 의미를 바꾸지 않는다. 필요한 경우 `alter table ... add column if not exists ...` 같은 보정 migration을 추가한다.
- 기존 워킹트리에 사용자/이전 작업 변경이 있을 수 있다. 관련 없는 변경은 되돌리지 않는다.
- 프론트는 `moodpick-dashboard.tsx`가 매우 크므로 기능 추가 시 상태, API 호출, 렌더링 위치를 좁혀서 수정한다.
- API 응답 필드 이름은 프론트와 백엔드/Next API 사이에서 꼭 맞춘다. 예: `display_name` vs `name`.
- UI 텍스트는 한국어로 유지한다.
- Docker에서 코드 저장 후 반영이 안 되면 먼저 `docker compose up -d --build --force-recreate frontend backend`로 dev 컨테이너를 재생성한다.

## CONTEXT 자동 갱신

- `scripts/update-context.ps1`가 이 파일 아래의 `Auto Snapshot` 섹션을 자동 갱신한다.
- 커밋 직전에는 `.githooks/pre-commit`이 `scripts/update-context.ps1`를 실행하고 `CONTEXT.md`를 다시 stage한다.
- 수동으로 최신화하려면 아래 명령을 실행한다.

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\update-context.ps1
```

- 자동 생성 섹션은 직접 오래 편집하지 않는다. 오래 남아야 하는 지식은 이 섹션 위쪽에 적는다.
- Windows PowerShell 인코딩 문제를 피하기 위해 자동 생성 섹션은 영어/ASCII 중심으로 유지한다.

## 최근 중요 작업

회원가입 시 성별/출생년도 저장 흐름을 연결했다.

- `frontend/components/moodpick-dashboard.tsx`
  - 회원가입 폼에 성별, 출생년도 입력 추가.
  - 출생년도 1900년~현재 연도 검증 추가.
  - `signUpWithPassword`에 `gender`, `birthYear` 전달.
- `frontend/components/auth-provider.tsx`
  - Supabase Auth metadata와 profile upsert에 `gender`, `birth_year` 전달.
- `frontend/lib/api.ts`
  - `upsertUserProfile(userId, displayName, gender, birthYear)` 형태로 확장.
  - profile 조회/저장은 Next API route(`/api/user/profile`)를 사용.
- `frontend/app/api/user/profile/route.ts`
  - service role로 `user_profiles` upsert.
  - Auth metadata도 display name, gender, birth year 동기화.
- `backend/app/routers/user.py`
  - FastAPI profile endpoint도 `gender`, `birth_year`를 입출력하도록 확장.
- `ai/tools/user_profile.py`
  - AI 프로필 조회에 `gender`, `birth_year` 포함.
- `db/migrations/010_add_user_profile_demographics.sql`
  - 이미 존재하는 Supabase `user_profiles` 테이블에 `gender`, `birth_year`를 추가하는 보정 migration.

## 검증 명령

프론트 빌드:

```bash
cd frontend
npm run build
```

백엔드/AI 문법 확인:

```bash
python -m compileall backend\app ai -q
```

비AI 스모크 체크는 서버가 떠 있을 때:

```bash
node scripts/non_ai_smoke_check.mjs
```

## 다음 작업자가 주의할 점

- Supabase 실제 DB에는 `010_add_user_profile_demographics.sql`을 적용해야 성별/출생년도 컬럼이 생긴다.
- `frontend/next-env.d.ts`는 Next 빌드가 자동 변경할 수 있다. 의미 없는 변경이면 커밋하지 않는다.
- `PLAN.md`의 체크리스트를 갱신할 때는 현재 구현 상태와 맞지 않는 Vite/구버전 설명을 Next.js 기준으로 정리하는 것이 좋다.

## 배포 노트

- 배포 전에는 backend CORS의 `allow_origins=["*"]`를 실제 프론트엔드 도메인 목록으로 바꿔야 한다. `allow_credentials=True`와 와일드카드 origin은 운영 환경에서 함께 쓰지 않는 것이 안전하다. 개발용 localhost origin은 별도로 유지하고, 운영 도메인을 명시한다.
- 2026-05-09 안정화 메모: 상담/콘텐츠 저장 경로는 사용자에게 안전한 한국어 오류 문구를 반환하고, 저장 전에 `session_id`가 해당 `user_id` 소유인지 확인한다. 같은 사용자/세션/콘텐츠의 중복 시청 기록을 피하고, 로그에는 원문 상담 내용 대신 짧은 id와 예외 타입만 남긴다.

### 배포 체크리스트

- [ ] CORS: `allow_credentials=True`를 쓸 때 와일드카드 origin을 제거하고 운영 프론트엔드 도메인을 명시한다.
- [ ] 환경변수: 프론트엔드/백엔드 운영 환경의 Supabase, OpenAI, YouTube/MCP, 허용 origin 값을 확인한다. `.env.local`은 커밋하지 않는다.
- [ ] Supabase 마이그레이션: `db/migrations/`의 모든 파일을 운영 Supabase 프로젝트에 순서대로 적용한다. 최신 스키마에 프로필 성별/출생년도, 콘텐츠 미디어 필드, 콘텐츠 피드백 unique 제약, 사용자 취향 벡터, 추천 로그 ambiguity 필드가 포함됐는지 확인한다.
- [ ] API quota/rate limits (일부 완료): OpenAI, YouTube, Supabase, MCP 실패 시 동작을 정의한다. 가능하면 자연스러운 fallback 응답, 사용자 친화적인 재시도 안내, 깨지지 않는 UI 상태를 유지한다.
- [ ] Logging (일부 완료): 요청 경로, 안전한 범위의 user/session id, 외부 API 상태, 지연 시간, 예외 타입을 구조화 로그로 남기는지 확인한다. API key, access token, 비밀번호, 민감한 상담 원문은 로그에 남기지 않는다.
- [ ] 오류 모니터링: 플랫폼 로그, Sentry, Logtail, Supabase logs 등 운영 로그/알림 대상을 정한다. 반복되는 5xx, AI pipeline 실패, YouTube quota 오류, DB write 실패에 알림을 건다.
- [ ] DB 오류 처리: session 시작/종료, 사전/사후 문진 제출, 상담 메시지, 콘텐츠 피드백, 시청 기록, 사용자 프로필, 알림 설정 저장 경로에서 사용자에게 보여줄 fallback 처리를 확인한다.
- [ ] API 연동 실패 처리 (일부 완료): 백엔드 연결 실패, AI timeout, 추천 실패, YouTube 재생 실패, Supabase auth/session 만료 상황에서 프론트가 안정적인 한국어 메시지를 보여주는지 확인한다.
- [ ] 재시도/타임아웃 정책: 외부 API에 적절한 백엔드 timeout을 두고 무한 대기를 피한다. retry는 안전한/idempotent 호출 또는 보호된 background job에만 적용한다.
- [ ] 중복 데이터 방지 (일부 완료): 필요한 곳에 unique/upsert 제약을 유지한다. 특히 `content_feedback(user_id, content_id)`와 같은 제약, 같은 session/content의 중복 시청 기록 방지를 확인한다.
- [ ] 인증/보안: placeholder auth route가 제거된 상태를 유지하고, 보호가 필요한 API가 Supabase auth/service-role/RLS 정책에 맞게 동작하는지 확인한다. 운영 전 RLS 정책을 다시 점검한다.
- [ ] 개인정보/상담 내용 보호 (일부 완료): 상담 로그, 요약, 분석 데이터가 민감한 원문 대화 내용을 로그나 analytics에 노출하지 않는지 확인한다.
- [ ] 프론트엔드 운영 빌드: `frontend/`에서 `npm run build`, `npm run lint`를 실행한다.
- [ ] 백엔드 smoke check: `python -m compileall backend\app ai -q`와 운영 유사 환경의 최소 API smoke test를 실행한다.
- [ ] Docker/배포 이미지: 고정된 Node/pnpm 버전으로 재현 가능한 빌드가 되는지 확인하고, 백엔드 이미지에 AI/MCP 추천에 필요한 파일이 포함됐는지 확인한다.
- [ ] 롤백 계획: 마지막 안정 커밋/이미지, DB migration rollback 전략, 외부 API 장애 시 AI 추천 기능을 끄는 방법을 정리한다.

<!-- AUTO_CONTEXT_START -->
## Auto Snapshot

This section is generated by scripts/update-context.ps1. Keep stable project knowledge above this section.

- Last updated: 2026-05-10 22:51:43 +09:00
- Branch: `feat/phase2-integration`
- Commit: `e716a3e`
- Frontend stack: Next.js 16.2.0, React 19.2.4

### Recent Migrations

- `db/migrations/011_content_embeddings.sql`
- `db/migrations/012_user_taste_vectors.sql`
- `db/migrations/013_recommendation_log.sql`
- `db/migrations/014_content_feedback_unique.sql`
- `db/migrations/015_add_user_profile_demographics.sql`
- `db/migrations/016_recommendation_log_ambiguity.sql`
- `db/migrations/017_allow_podcast_media_provider.sql`
- `db/migrations/018_watched_content_media_supabase_apply.sql`
- `db/migrations/019_counseling_session_meditation_audio_format.sql`
- `db/migrations/020_session_summary.sql`

### Working Tree

- `M  CONTEXT.md`
- `M  ai/agents/content_recommender.py`
- `M  ai/meditation_audio_signals.py`
- `M  mcp_servers/server.py`
- `?? EMOTION_ANALYSIS_NOTES.md`

### Refresh

~~~bash
powershell -ExecutionPolicy Bypass -File .\scripts\update-context.ps1
~~~

Before each commit, .githooks/pre-commit runs this script and stages CONTEXT.md again.
<!-- AUTO_CONTEXT_END -->
