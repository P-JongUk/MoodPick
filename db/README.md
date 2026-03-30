# MoodPick 데이터베이스 (Supabase)

## 개요
PostgreSQL 기반의 Supabase를 사용하여 사용자, 감정 기록, 상담 이력 데이터를 관리합니다.

## 폴더 구조
```
db/
├── migrations/              # 데이터베이스 마이그레이션 파일
│   ├── 001_initial_schema.sql      # 초기 테이블 생성
│   ├── 002_vector_tables.sql       # pgvector 테이블
│   └── 003_indexes.sql             # 인덱스 생성
├── seed_data/               # 초기 데이터
│   └── seed.sql             # 테스트 데이터
├── functions/               # Supabase Edge Functions (선택)
└── schema.md                # 데이터베이스 스키마 문서
```

## 주요 테이블
- `users` - 사용자 정보
- `emotion_records` - 감정 기록
- `counseling_histories` - 상담 이력

## 개발 환경 설정
자세한 내용은 [PLAN.md](../PLAN.md)의 **DB 폴더** 섹션을 참고하세요.
