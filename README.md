# MoodPick

MoodPick은 감정을 기록하고, 대화하고, 바로 추천받는 AI 심리 케어 서비스입니다.
사용자가 지금 어떤 상태인지 빠르게 파악하고, 상담 흐름을 이어가며, 그 순간에 맞는 콘텐츠를 바로 연결해 주는 것이 핵심입니다. 단순한 기록 앱이 아니라, 감정 변화와 추천 결과가 서로 이어지는 개인화된 케어 경험을 제공합니다.

## 서비스 소개

- 감정이 쌓이는 방식으로 대화를 이어가고, 상담 세션마다 변화를 기록합니다.
- 사전/사후 문진과 감정 기록을 묶어서 현재 상태와 변화 흐름을 함께 봅니다.
- 상담 맥락, 사용자 히스토리, 선호 데이터를 바탕으로 콘텐츠를 추천합니다.
- 로그인부터 대시보드, 기록, 추천까지 한 흐름으로 자연스럽게 이어집니다.

## 한눈에 보기

- 상담 세션과 문진으로 감정 변화를 쌓고, 흐름을 한눈에 봅니다.
- 감정 기록과 사용자 히스토리를 바탕으로 맞춤 콘텐츠를 추천합니다.
- Supabase Auth, PostgreSQL, pgvector로 데이터와 검색을 관리합니다.
- 로컬 실행과 Docker 개발 환경을 모두 지원합니다.

## 기술 스택

- 프론트엔드: Next.js, React, TypeScript
- 백엔드: FastAPI, Python
- 데이터: Supabase, PostgreSQL, pgvector
- AI: GPT 기반 상담/추천 파이프라인, YouTube 연동
- 배포: Vercel, Cloudtype, Docker

# MoodPick

![Status](https://img.shields.io/badge/status-production-brightgreen)
![Python](https://img.shields.io/badge/python-3.10-blue)
![License](https://img.shields.io/badge/license-MIT-green)

AI 상담과 개인화된 콘텐츠 추천을 하나로 연결한 심리 케어 플랫폼 — 지금의 기분에 맞춘 즉각적 케어를 제공합니다.

한줄 요약: AI 기반 상담 흐름과 RAG 기반 추천이 결합된 간편한 개인 심리 케어 서비스.
## 프로젝트 구조

├── ai/              # 상담/추천 AI 모듈
├── db/              # Supabase SQL 마이그레이션 및 시드
├── docs/            # 아키텍처/설명 문서
## 한눈에 보기

- 빠른 상담 흐름: 문진과 대화로 감정 변화를 기록하고 요약합니다.
- 개인화 추천: 사용자 히스토리·선호·문맥을 반영한 콘텐츠 연결.
- 확장 가능한 RAG 검색: pgvector(1536) 기반 임베딩과 Supabase로 운영.
- 로컬 개발 및 Docker 환경 지원.

## 핵심 기능
- RAG 기반 상담 보조

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

이 저장소는 `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml`로 로컬 개발 환경을 제공합니다.

docker compose down
docker compose up --build -d
```

## 데모 계정 (샘플 데이터)

- 아이디: moodpick1@gmail.com
- 비밀번호: moodpick1!

이 계정은 데모/테스트용 샘플 데이터로만 제공됩니다. 민감한 정보나 실제 개인정보는 업로드하지 마세요.

---

## Docker (요약)

- 프론트엔드: `frontend/Dockerfile`
- 백엔드: `backend/Dockerfile`
- 로컬 실행: `docker compose up --build`

---

더 자세한 설정과 엔드포인트는 각 하위 README를 참고하세요.
- 의존성이나 Dockerfile을 바꿨다면 `docker compose up --build -d`로 다시 올리세요.