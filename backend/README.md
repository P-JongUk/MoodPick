# MoodPick 백엔드 (FastAPI)

## 개요
FastAPI 기반의 MoodPick 백엔드 서버입니다. GPT-4o-mini와 YouTube API를 활용한 AI 상담 및 감정 분석 기능을 제공합니다.

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
- `POST /emotion/analyze` - 감정 분석
- `GET /emotion/records` - 감정 기록 조회

## 개발 환경 설정
프로젝트 전체 개요와 실행 방법은 [루트 README](../README.md)를 참고하세요.
