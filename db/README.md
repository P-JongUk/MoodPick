# MoodPick 데이터베이스 (Supabase)

## 개요
PostgreSQL 기반의 Supabase를 사용하여 사용자, 감정 기록, 상담 이력 데이터를 관리합니다.

## 폴더 구조
```
db/
├── migrations/              # 데이터베이스 마이그레이션 파일
│   ├── 001_initial_schema.sql      # 세션/문진/콘텐츠 관련 초기 테이블 + RLS
│   └── 002_vector_tables.sql       # RAG/임베딩 벡터 테이블(pgvector)
└── (추후 추가)
	├── 002_*.sql                    # 신규 기능 스키마
	├── 003_*.sql                    # 인덱스/정책 보강
	└── ...
```

## 마이그레이션 번호 규칙
- 아직 Supabase에 적용 전이면 번호/파일명을 정리한 후 적용합니다.
- 이미 적용된 마이그레이션 파일은 번호를 바꾸지 않고 다음 번호를 이어서 추가합니다.

## 주요 테이블
- `counseling_sessions` - 상담 세션
- `survey_responses` - 사전/사후 문진 응답
- `content_feedback` - 콘텐츠 피드백(좋아요/아쉬워요)
- `watched_content_records` - 시청 콘텐츠 기록
- `emotion_embeddings` - 감정/문맥 임베딩 벡터(예정)
- `rag_documents` - RAG 문서 메타데이터(예정)
- `rag_chunks` - RAG 청크 및 임베딩(예정)

## RAG/벡터 저장소 계획
- `002_vector_tables.sql`에서 `pgvector` 확장을 활성화합니다.
- 기본 검색 단위는 `rag_chunks`이며, 코사인 유사도 인덱스를 사용합니다.
- 서비스 연결 전까지는 마이그레이션 적용 + 샘플 데이터 삽입 + 검색 쿼리 검증까지 수행합니다.

## 개발 환경 설정
자세한 내용은 [PLAN.md](../PLAN.md)의 **DB 폴더** 섹션을 참고하세요.

## 운영 문서
- RAG 적용 순서: `db/RAG_MIGRATION_RUNBOOK.md`
- RAG 샘플 데이터: `db/seed_data/001_rag_sample_data.sql`
