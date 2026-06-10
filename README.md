# MoodPick

MoodPick은 사용자의 감정 흐름을 바탕으로 상담, 감정 기록, 콘텐츠 추천을 제공하는 웹 서비스입니다. 공개 배포용으로 정리된 이 저장소는 Next.js 프론트엔드, FastAPI 백엔드, Supabase 데이터 계층, AI 상담/추천 모듈로 구성됩니다.

## 한눈에 보기

- 상담 세션 기반으로 대화를 진행하고, 사전/사후 문진으로 변화량을 기록합니다.
- 감정 기록과 사용자 히스토리를 바탕으로 맞춤형 콘텐츠를 추천합니다.
- Supabase Auth와 PostgreSQL로 사용자 데이터와 세션 데이터를 관리합니다.
- Docker 개발 환경과 로컬 실행 환경을 모두 지원합니다.

## 기술 스택

- 프론트엔드: Next.js, React, TypeScript
- 백엔드: FastAPI, Python
- 데이터: Supabase, PostgreSQL, pgvector
- AI: GPT 기반 상담/추천 파이프라인, YouTube 연동
- 배포: Vercel, Cloudtype, Docker

## 프로젝트 구조

```text
MoodPick/
├── frontend/        # Next.js 앱
├── backend/         # FastAPI 서버
├── ai/              # 상담/추천 AI 모듈
├── db/              # Supabase SQL 마이그레이션 및 시드
├── docs/            # 아키텍처/설명 문서
├── mcp_servers/     # 외부 콘텐츠 검색용 MCP 서버
├── scripts/         # 운영/검증 스크립트
└── docker-compose.yml
```

## 핵심 기능

- 회원가입, 로그인, 프로필 저장
- 상담 세션 시작/종료 및 문진 저장
- 감정 기록 조회, 대시보드 통계, 히스토리 확인
- 콘텐츠 피드백 및 시청 기록 저장
- RAG 기반 상담 보조와 개인화 추천

## 빠른 시작

### 1. 로컬 실행

백엔드:

```bash
cd backend
python -m venv .venv
\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

프론트엔드:

```bash
cd frontend
npm install
npm run dev
```

### 2. Docker 실행

```bash
docker compose up --build
```

자세한 Docker 안내는 이 README 아래의 Docker 섹션을 참고하세요.

## 환경 변수

- 백엔드: `backend/.env.local`
- 프론트엔드: `frontend/.env.local`

주요 값:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_JWT_SECRET`
- `OPENAI_API_KEY`
- `YOUTUBE_API_KEY`
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `NEXT_PUBLIC_API_BASE_URL`

## 문서

- [백엔드 안내](backend/README.md)
- [AI 모듈 안내](ai/README.md)
- [DB / 마이그레이션 안내](db/README.md)
- [아키텍처 개요](docs/ARCHITECTURE.md)
- [이론적 계산 및 RAG 설명](docs/REPORT_SECTION3.md)

## Docker

이 저장소는 `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml`로 로컬 개발 환경을 제공합니다.

- 프론트엔드: `npm exec next dev --webpack --hostname 0.0.0.0`
- 백엔드: `uvicorn app.main:app --reload`
- Windows bind mount 환경에서는 polling 기반 감지를 사용합니다.

### 자주 쓰는 명령

```bash
docker compose up --build
docker compose down
docker compose up --build -d
```

### 참고

- 프론트엔드 변경이 바로 보이지 않으면 브라우저 새로고침을 먼저 시도하세요.
- 백엔드 변경이 반영되지 않으면 컨테이너 재시작이 필요할 수 있습니다.
- 의존성이나 Dockerfile을 바꿨다면 `docker compose up --build -d`로 다시 올리세요.

## 상태

이 저장소는 공개 배포를 기준으로 정리된 상태입니다. 내부 계획서와 개발용 보조 문서는 제거했고, 외부 공개에 필요한 개요와 실행 안내만 남겼습니다.