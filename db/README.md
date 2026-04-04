# MoodPick 데이터베이스 (Supabase)

## 개요
PostgreSQL 기반의 Supabase를 사용하여 사용자, 감정 기록, 상담 이력 데이터를 관리합니다.

## 폴더 구조
```
db/
├── migrations/              # 데이터베이스 마이그레이션 파일
│   └── 001_initial_schema.sql      # 세션/문진/콘텐츠 관련 초기 테이블 + RLS
└── (추후 추가)
	├── 002_*.sql                    # 신규 기능 스키마
	├── 003_*.sql                    # 인덱스/정책 보강
	└── ...
```

## 마이그레이션 번호 규칙
- 아직 Supabase에 적용 전이면 번호/파일명을 정리한 후 적용합니다.
- 이미 적용된 마이그레이션 파일은 번호를 바꾸지 않고 다음 번호를 이어서 추가합니다.

## 주요 테이블
- `users` - 사용자 정보
- `emotion_records` - 감정 기록
- `counseling_histories` - 상담 이력

## 개발 환경 설정
자세한 내용은 [PLAN.md](../PLAN.md)의 **DB 폴더** 섹션을 참고하세요.
