# MoodPick

![Status](https://img.shields.io/badge/status-production-brightgreen)
![Python](https://img.shields.io/badge/python-3.10-blue)
![License](https://img.shields.io/badge/license-MIT-green)

AI 상담과 개인화된 콘텐츠 추천을 결합한 심리 케어 플랫폼 — 지금의 기분에 맞춘 즉각적이고 지속적인 케어.

한줄 요약: 상담 흐름, 감정 기록, 그리고 RAG 기반 추천이 연결된 개인 심리 케어 서비스.

## 핵심 포인트

- 빠른 상담 흐름: 문진과 대화로 감정 변화를 기록하고 요약합니다.
- 개인화 추천: 사용자 히스토리·선호·문맥을 반영한 콘텐츠 연결.
- 확장 가능한 RAG 검색: pgvector(1536) 기반 임베딩과 Supabase로 운영.
- 로컬 개발 및 Docker 환경 지원.

## 프로젝트 구조 (요약)

```
MoodPick/
├── frontend/        # Next.js 앱
├── backend/         # FastAPI 서버
├── ai/              # 상담/추천 AI 모듈
├── db/              # Supabase SQL 마이그레이션 및 시드
├── docs/            # 아키텍처/설명 문서
└── docker-compose.yml
```

## 빠른 시작

### 1) 로컬 개발

백엔드 (Windows PowerShell):

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

프론트엔드:

```bash
cd frontend
npm install
npm run dev
```

### 2) Docker (로컬 통합)

```bash
docker compose up --build
```

## 환경 변수 (주요)

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_JWT_SECRET`
- `OPENAI_API_KEY`
- `YOUTUBE_API_KEY`
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `NEXT_PUBLIC_API_BASE_URL`

백엔드는 `backend/.env.local`, 프론트엔드는 `frontend/.env.local`을 사용합니다.

## 문서

- [백엔드 안내](backend/README.md)
- [AI 모듈 안내](ai/README.md)
- [DB / 마이그레이션 안내](db/README.md)
- [아키텍처 개요](docs/ARCHITECTURE.md)
- [이론적 계산 및 RAG 설명](docs/REPORT_SECTION3.md)

## 데모 계정 (샘플 데이터)

- 아이디: moodpick1@gmail.com
- 비밀번호: moodpick1!

이 계정은 데모/테스트용 샘플 데이터용입니다. 실제 사용자 정보나 민감한 데이터는 저장하지 마십시오.

---

더 자세한 설정과 엔드포인트는 각 하위 `README.md`를 참고하세요.
- 의존성이나 Dockerfile을 바꿨다면 `docker compose up --build -d`로 다시 올리세요.