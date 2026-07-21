# MoodPick

AI 상담과 개인화된 콘텐츠 추천을 결합한 상담 흐름, 감정 기록, 그리고 RAG 기반 추천이 연결된 개인 심리 케어 서비스.

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

## 문서

- [백엔드 안내](backend/README.md)
- [AI 모듈 안내](ai/README.md)
- [DB / 마이그레이션 안내](db/README.md)
- [아키텍처 개요](docs/ARCHITECTURE.md)
- [이론적 계산 및 RAG 설명](docs/REPORT_SECTION3.md)

## 테스트 계정

- 아이디: moodpick1@gmail.com
- 비밀번호: moodpick1!

이 계정은 데모/테스트용 샘플 데이터용입니다.

## 관리자 계정

- 아이디: test1@gmail.com
- 비밀번호: test1!

---
