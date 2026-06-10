# MoodPick 백엔드 (FastAPI)

## 개요
FastAPI 기반의 MoodPick 백엔드 서버입니다. 상담, 감정 기록, 콘텐츠 추천, RAG 조회를 위한 API를 제공합니다.

## 폴더 구조
```
backend/
├── app/
│   ├── main.py              # FastAPI 애플리케이션 진입점
│   ├── routers/             # API 라우트 (인증, 상담, 감정, 사용자)
│   ├── schemas/             # Pydantic 데이터 모델
│   ├── services/            # 비즈니스 로직
│   ├── config.py            # 설정
│   └── dependencies.py      # 의존성 주입
├── requirements.txt         # Python 패키지 의존성
├── .env.example            # 환경 변수 예시
└── README.md               # 이 파일
```

## 주요 API 엔드포인트
- `POST /counseling/message` - 상담 요청
- `POST /emotion/analyze` - 키워드 기반 감정 분석 보조
- `GET /emotion/records/{user_id}` - 감정 기록 조회
- `GET /emotion/summary/{user_id}` - 감정 요약 조회
- `POST /rag/search` - RAG 유사도 검색

## 개발 환경 설정
프로젝트 전체 개요와 실행 방법은 [루트 README](../README.md)를 참고하세요.
