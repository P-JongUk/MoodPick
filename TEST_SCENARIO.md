# MoodPick 테스트 시나리오 가이드

이 문서는 현재 구현된 기능 기준으로 로컬 실행, 데이터 준비, 핵심 플로우 검증을 빠르게 수행하기 위한 테스트 가이드입니다.

## 1. 테스트 범위

- 비AI 핵심 플로우(인증, 세션, 문진, 콘텐츠 피드백, 대시보드)
- 회원가입 시 표시 이름(display name) 입력/저장
- 리마인더 설정 저장/조회 및 수동 dispatch
- 실데이터 기반 화면 검증(더미 의존 최소화)

## 3. 설치 및 실행 준비

### 3-0. 기존 clone 팀원용: 최신 브랜치로 테스트 환경 맞추기

이미 이전 브랜치를 clone 해둔 팀원은 아래 순서로 최신 코드 기준 테스트 환경을 맞춥니다.

빠른 순서 요약:

1. 원격 최신 정보 갱신(`git fetch`)
2. 테스트할 최신 브랜치로 전환(`git switch`)
3. 최신 커밋 동기화(`git pull`)
4. 백엔드/프론트 의존성 재설치

#### A) 로컬에 이미 해당 브랜치가 있는 경우

```bash
cd MoodPick
git fetch origin
git switch <최신_브랜치명>
git pull --rebase origin <최신_브랜치명>
```

#### B) 로컬에 해당 브랜치가 아직 없는 경우

```bash
cd MoodPick
git fetch origin
git switch -c <최신_브랜치명> --track origin/<최신_브랜치명>
```

브랜치 확인:

```bash
git branch --show-current
git log --oneline -n 3
```

#### C) 터미널에서 설치(재설치)해야 하는 것

백엔드(권장: venv 사용):

```bash
cd backend
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

프론트엔드:

```bash
cd ../frontend
npm install
```

설치 후 실행:

```bash
# backend
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# frontend (새 터미널)
cd frontend
npm run dev
```

#### D) 자주 발생하는 문제 빠른 점검

- 브랜치가 꼬였으면: `git status`로 로컬 변경사항 먼저 확인
- 의존성 충돌 시: `frontend/node_modules`, `frontend/package-lock.json` 삭제 후 `npm install` 재실행
- 파이썬 패키지 충돌 시: 기존 가상환경 삭제 후 `.venv` 재생성

### 3-1. 설치

```bash
git clone <repo-url>
cd MoodPick

cd backend
python -m pip install -r requirements.txt

cd ../frontend
npm install
```

### 3-2. 환경변수

- 백엔드: `backend/.env.local` (또는 프로젝트 규칙 파일)
- 프론트: `frontend/.env.local`

### 3-3. 실행

```bash
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

cd ../frontend
npm run dev
```

확인 주소:

- 프론트: `http://localhost:3000`
- 백엔드 헬스: `http://127.0.0.1:8000/health`
- OpenAPI: `http://127.0.0.1:8000/docs`

## 4. DB 준비 순서

아래 순서대로 Supabase SQL Editor에서 실행합니다.

1. `db/migrations/001_initial_schema.sql`
2. `db/migrations/002_vector_tables.sql` (RAG 테스트가 필요할 때)
3. `db/migrations/003_reminder_preferences.sql`
4. `db/migrations/004_reminder_dispatch_logs.sql`
5. `db/migrations/005_user_profiles.sql`
6. `db/seed_data/002_frontend_dev_sample_seed.sql` (개발 확인용 선택)

시드 주의사항:

- `db/seed_data/002_frontend_dev_sample_seed.sql`에서 `target_user_id` 한 곳만 실제 `auth.users.id`로 바꿔 실행
- 재실행 가능하도록 seed-dev 데이터 정리 로직 포함

## 5. 핵심 검증 시나리오

### 5-1. 인증 및 이름 입력

목표: 회원가입 시 이메일/비밀번호와 함께 표시 이름을 입력하고 저장되는지 확인

체크 포인트:

- 회원가입 모드에서 `서비스에서 불릴 이름` 입력칸이 표시된다.
- 이름 미입력 상태에서는 회원가입 진행이 차단된다.
- 회원가입 후 로그인 시 사용자 메타데이터에 `display_name`이 존재한다.
- `user_profiles` 테이블에 해당 `user_id`의 `display_name`이 upsert 된다.

### 5-2. 온보딩

목표: 신규 사용자 온보딩 1회 노출 확인

체크 포인트:

- 신규 가입 후 첫 로그인에서 온보딩이 노출된다.
- 온보딩 완료 후 재로그인 시 온보딩이 다시 뜨지 않는다.

### 5-3. 상담 세션 및 문진

목표: 세션 생성부터 사전/사후 문진, 종료, Delta 반영까지 검증

체크 포인트:

- 세션 시작 시 `currentSessionId` 생성
- 사전 문진 저장
- 문진 키 일치: `mood_general`, `energy_level`, `stress_level`
- 사전 문진 직후 초기 상담 메시지가 세션 상태 기반으로 생성
- 사후 문진 저장 후 세션 종료
- 대시보드에 Delta 반영

### 5-4. 콘텐츠 피드백

목표: 시청 기록/피드백 저장 및 히스토리 반영 검증

체크 포인트:

- 좋아요/아쉬워요 클릭 시 저장 에러가 없어야 함
- `watched_content_records`, `content_feedback` 데이터 저장
- 대시보드/기록 화면에서 사용자별 히스토리 확인 가능

### 5-5. 대시보드 실데이터

목표: 통계/캘린더/그래프/기록이 백엔드 데이터로 표시되는지 확인

체크 포인트:

- 총 상담 횟수, 시청 수, 피드백 수 표시
- 감정 그래프/캘린더가 survey 기반 데이터로 렌더링
- 상담 히스토리와 콘텐츠 히스토리가 사용자별로 분리

### 5-6. 리마인더 (현재 기본 비활성 운영)

목표: 기능은 구현해두되, 서비스 부하를 고려해 자동 실행은 보류하고 운영 시점에 활성화 여부를 결정

운영 정책(현재):

- 리마인더 API/DB 스키마는 구현 완료
- 자동 스케줄러는 기본 비활성(`REMINDER_SCHEDULER_ENABLED=False`)
- 즉시 운영 전환하지 않고, 트래픽/장애 지표 확인 후 활성화 여부 재결정
- 필요 시 수동 dispatch 중심으로 검증/운영

체크 포인트:

- 마이페이지에서 리마인더 설정(on/off, 시간, 타임존) 저장 가능
- `/reminder/preferences/{user_id}` 저장/조회 정상
- `/reminder/dispatch` 수동 실행 가능
- `reminder_dispatch_logs`, `last_sent_at` 갱신 정상


## 6. 감정 수집/점수 체계 및 RAG 점수 정리

이 섹션은 "지금 감정을 어떻게 받고 있는지", "RAG에서 어떤 점수와 항목을 쓰는지"를 코드 기준으로 정리한 내용입니다.

### 6-1. 감정 수집 경로 (현재)

1. 세션 기반 사전/사후 문진(핵심)

- 엔드포인트: `GET /survey/questions`, `POST /survey/submit`, `GET /survey/delta/{session_id}`
- 문항 키: `mood_general`, `energy_level`, `stress_level`
- 저장 테이블: `public.survey_responses`

2. 텍스트 기반 임시 감정 분석(보조)

- 엔드포인트: `POST /emotion/analyze`
- 현재는 AI 모델 기반이 아니라 키워드 매칭 임시 로직(스트레스/우울/불안 등)
- 반환: `emotion`, `intensity`, `recommendations`

3. 감정 기록/요약 조회

- 엔드포인트: `GET /emotion/records/{user_id}`, `GET /emotion/summary/{user_id}`
- 실제 요약 값은 최근 N일 `survey_responses.score` 집계 기반

### 6-2. 문진 점수 변환 규칙

문진은 이모지 값을 수치 점수로 변환해서 저장합니다.

- `great` -> `5`
- `good` -> `4`
- `neutral` -> `3`
- `low` -> `2`
- `bad` -> `1`

Delta 계산 방식:

- 항목별 `delta = post_score - pre_score`
- 전체 개선 여부 `improved = average(delta) > 0`

### 6-3. 감정 요약(트렌드) 계산 방식

- 평균 점수: 최근 N일 응답의 `score` 평균
- 추이 판단:
  - 최근 3개 평균 > 그 이전 3개 평균 + 0.5 -> `improving`
  - 최근 3개 평균 < 그 이전 3개 평균 - 0.5 -> `declining`
  - 그 외 -> `stable`

### 6-4. RAG 검색 점수와 사용 항목

RAG 검색은 `match_rag_chunks` 함수와 `vector_cosine_ops` 기반으로 동작합니다.

입력 항목:

- `query_embedding` (1536차원)
- `top_k` (1~20)
- `user_id` (선택, 사용자 스코프 필터)

검색/정렬 기준:

- 거리: `c.embedding <=> query_embedding` (cosine distance)
- 정렬: 거리 오름차순(가까운 벡터 우선)
- 노출 점수: `similarity = 1 - distance`

반환 항목:

- `chunk_id`
- `document_id`
- `content`
- `similarity`

참고:

- 현재 구현에는 별도 최소 similarity threshold 컷오프가 없습니다.
- 따라서 상위 `top_k`를 항상 반환하며, 품질 필터링은 이후 AI 응답 결합 단계에서 강화할 계획입니다.

## 7. 최초 1회 사용자 정보 수집(온보딩) 저장 구조

이 섹션은 "처음 한 번 진행하는 사용자 정보 수집"이 어디에 어떤 형태로 저장되는지 설명합니다.

### 7-1. 첫 상태(회원가입 직후)

회원가입 시 Auth 메타데이터에 아래 값이 초기화됩니다.

- `display_name`: 사용자가 입력한 표시 이름
- `onboarding_completed: false`
- `onboarding_profile: null`

### 7-2. 1회 온보딩 문진 항목

프론트 온보딩 화면에서 수집하는 값:

- 고민/스트레스 카테고리(`concerns[]`): 예) `study`, `relationship`, `future`, `work`, `other`
- 선호 위로 방식(`comfort_style[]`): 예) `listen`, `advice`, `music`, `video`

### 7-3. 저장 시점과 저장 위치

저장 시점:

- 사용자가 온보딩 화면에서 `시작하기` 또는 `나중에 설정할게요`를 눌러 완료할 때

저장 위치:

- Supabase Auth 사용자 메타데이터(`user.user_metadata`)에 업데이트
- 저장 구조:
  - `onboarding_completed: true`
  - `onboarding_profile: { concerns: string[], comfort_style: string[], collected_at: ISO datetime }`

### 7-4. 1회 노출 제어 방식

- 로그인 후 `user_metadata.onboarding_completed`를 읽어 온보딩 노출 여부를 결정
- 기존 사용자 호환:
  - 해당 키가 없는 기존 계정은 기본적으로 완료 처리(`true`)하여 재노출 방지

## 8. AI 구조 정리 (현재 구현 vs 다음 단계)

### 8-1. 현재 구현 상태

1. 상담 응답

- `POST /counseling/message`는 현재 비AI 임시 가이드 응답(룰 기반)
- 메시지 길이 기반으로 간단한 안내 문구 분기

2. 초기 상담 메시지

- `GET /counseling/initial-message/{session_id}`
- 사전문진의 `mood_general` 값을 읽어 초기 문장을 맞춤 생성(맵핑 기반)

3. 감정 분석

- `POST /emotion/analyze`는 키워드 기반 임시 분석

4. RAG

- `POST /rag/search`, `POST /rag/search-by-text` 제공
- `search-by-text`는 OpenAI 임베딩(`text-embedding-3-small`, 1536차원) 생성 후 벡터 검색

### 8-2. 현재 아키텍처 흐름

1. 사용자 입력/세션 정보 수집
2. 사전문진/기록 데이터 축적
3. 필요 시 RAG 검색으로 관련 컨텍스트 조회
4. 현재는 룰 기반 응답 반환, 이후 GPT 응답 생성기로 대체 예정

### 8-3. 다음 단계 목표 구조 (AI 연동 시)

1. Intent/안전 분기 -> 2) RAG 검색/요약 -> 3) GPT 답변 생성 -> 4) 응답/근거 로깅

필수 강화 포인트:

- 프롬프트/안전 정책(위기 징후 대응) 분리
- RAG 검색 결과에 score threshold 및 재랭킹 도입
- 대화 히스토리 요약 메모리(토큰 비용/지연 관리)
- 실패 fallback(모델 오류 시 규칙형 응답)

### 8-4. Function Calling 방식 (권장 구현안)

목표:

- 채팅 입력 1건마다 "필요한 도구만" 호출하고, 결과를 근거로 상담 응답/위로/콘텐츠 추천을 생성

권장 함수 목록:

- `analyze_text_emotion(text, session_id)`
- `search_rag_context(query_text, user_id, top_k)`
- `get_user_profile_and_history(user_id)`
- `recommend_contents(emotion, concerns, comfort_style, history)`
- `save_feedback(content_id, feedback, session_id, user_id)`

권장 실행 순서:

1. 사용자 메시지 수신
2. LLM이 Function Calling으로 필요 함수 선택
3. 서버가 함수 실행 후 결과를 LLM에 재주입
4. LLM이 최종 상담 답변 + 추천 콘텐츠 + 근거 요약 생성
5. 사용자의 좋아요/아쉬워요 피드백 저장 후 다음 추천에 반영

안전/품질 규칙:

- 고위험 신호 감지 시 일반 응답 대신 안전 시나리오 우선
- 함수 실패 시 fallback 메시지 + 재시도 안내
- RAG 근거가 약하면 단정형 표현 금지

간단한 의사코드:

```text
user_message -> llm(tool_choice=auto)
if tool_calls:
  execute tools
  llm(tools_result)
return final_response
```

## 9. 이후 할 일 상세 체크리스트

### 9-1. 1단계: AI 연결 기반 만들기

- [ ] `POST /counseling/message`를 LLM 호출 구조로 전환
- [ ] 모델/토큰/타임아웃/재시도 정책 환경변수화
- [ ] Function Calling용 tool schema 정의 및 서버 실행기 연결
- [ ] 실패 시 룰 기반 fallback 응답 유지

### 9-2. 2단계: 프롬프트 체계화

- [ ] 시스템 프롬프트 초안 작성(공감 톤, 금지 표현, 한계 고지)
- [ ] 상담 목적별 보조 프롬프트 분리(위로/코칭/요약)
- [ ] 위험 상황 프롬프트(자해/타해/응급) 별도 분기
- [ ] 프롬프트 버전 관리(`v1`, `v2`) 및 A/B 기록

### 9-3. 3단계: RAG 상담 매뉴얼 연동

- [ ] 상담 전문 매뉴얼 문서 수집 및 저작권/사용권 확인
- [ ] 청크 규칙 설계(길이, 오버랩, 메타데이터)
- [ ] 임베딩 적재 파이프라인 구축
- [ ] 검색 threshold, top_k, 재랭킹 규칙 확정
- [ ] 응답에 근거 요약 포함(출처/문서 ID)

### 9-4. 4단계: 텍스트 감정 분석 + 개인화 추천 고도화

- [ ] 채팅 텍스트 감정 분석 결과를 세션 상태에 반영
- [ ] 온보딩(`concerns`, `comfort_style`) + 히스토리 기반 추천 로직 강화
- [ ] 콘텐츠 추천 결과와 피드백(`like/dislike`) 연계 학습 규칙 정의
- [ ] 개인화 규칙의 최소 보장 로직(콜드스타트 fallback) 추가

### 9-5. 5단계: 문진 항목 리서치 및 업데이트

- [ ] 공개 검증 문항(예: WHO-5, PHQ-2/9, GAD-2/7 등) 리서치
- [ ] 서비스 목적에 맞는 문항 후보 선정 및 축약 버전 작성
- [ ] 의료행위 오해 방지 문구/동의 문구 반영
- [ ] `mood_general`, `energy_level`, `stress_level`와의 호환 매핑 설계
- [ ] 문진 업데이트 후 Delta/대시보드 계산 회귀 테스트

### 9-6. 6단계: MCP 전환(선택) 상세

왜 지금 MCP가 필수는 아닌가:

- 현재 핵심 목표는 사용자 플로우 완성도(상담/추천/피드백 반영) 안정화이며, MCP 전환은 기능 추가보다 운영 복잡도를 먼저 올릴 수 있음
- FastAPI + Function Calling + RAG 조합으로 현 단계 요구사항 구현이 가능함
- MCP를 추가하면 도구 노출/권한 경계/배포 경로/장애 분석 포인트가 늘어나 테스트 비용이 커짐
- AI 응답 품질과 회귀 테스트 자동화가 먼저 갖춰져야 안전하게 전환 가능함

언제 바꾸는 게 좋은가(권장 시점):

- 아래 조건이 충족된 뒤 점진 전환
  - AI 상담 + RAG + 추천 + 피드백 루프가 실사용 시나리오에서 안정 동작
  - 핵심 E2E/회귀 테스트 자동화 완료
  - MCP 도입 이점(다중 에이전트 재사용, 도구 표준화)이 운영 복잡도 증가보다 큼

권장 전환 순서:

1. 현 구조 안정화(FastAPI 중심)
2. 조회성 기능부터 MCP 1차 전환(`rag search`, `history summary`)
3. 쓰기 기능 2차 전환(`feedback save`, `session end`)
4. 성능/장애/운영 지표 비교 후 최종 확대 여부 결정

- [ ] MCP 도입 목표 정의(다중 에이전트 재사용, 툴 표준화)
- [ ] FastAPI 서비스 레이어를 MCP tool로 노출하는 어댑터 작성
- [ ] 1차 MCP 대상: 조회성(`rag search`, `history summary`)
- [ ] 2차 MCP 대상: 쓰기 기능(`feedback save`, `session end`)
- [ ] 성능/장애/보안 점검 후 단계적 전환

### 9-7. 7단계: 검증/운영

- [ ] 비AI/AI 통합 E2E 시나리오 분리 및 자동화
- [ ] 핵심 API 회귀 테스트 자동화(CI)
- [ ] 관측 지표 구축(응답시간, 실패율, 검색 적중률, 추천 클릭률)
- [ ] 릴리즈 게이트 충족 시 배포

## 10. 실패 상황 점검

1. 백엔드 중단 후 프론트에서 로그인/세션 시작 시도
2. 기대 결과

- 사용자에게 오류/경고가 노출됨
- 화면이 완전히 멈추지 않음
- 재시도 가능한 상태 유지

## 11. 기본 합격 기준

- 프론트/백엔드 실행 및 헬스체크 정상
- 회원가입/로그인 정상
- 회원가입 시 표시 이름 입력/저장 정상
- 온보딩 1회 노출 정상
- 상담 세션 + 사전/사후 문진 + Delta 정상
- 콘텐츠 피드백/시청 기록 정상
- 대시보드 실데이터 렌더링 정상
- 리마인더 설정 저장/조회 및 수동 dispatch 정상

## 12. 빠른 체크리스트

- [ ] 환경변수 설정 완료
- [ ] 마이그레이션 적용 완료
- [ ] 백엔드 실행 확인
- [ ] 프론트 실행 확인
- [ ] 인증/이름 입력 확인
- [ ] 온보딩 1회 노출 확인
- [ ] 세션/문진/Delta 확인
- [ ] 콘텐츠 피드백/기록 확인
- [ ] 대시보드 실데이터 확인
- [ ] 리마인더 설정/dispatch 확인

## 13. 참고 파일

- `PLAN.md`
- `backend/.env.example`
- `frontend/.env.example`
- `db/migrations/001_initial_schema.sql`
- `db/migrations/002_vector_tables.sql`
- `db/migrations/003_reminder_preferences.sql`
- `db/migrations/004_reminder_dispatch_logs.sql`
- `db/migrations/005_user_profiles.sql`
- `db/seed_data/002_frontend_dev_sample_seed.sql`
- `scripts/non_ai_smoke_check.mjs`
- `frontend/scripts/e2e_user_flow_rehearsal.mjs`

