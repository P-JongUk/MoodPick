# MoodPick 데이터베이스 (Supabase)

## 개요
PostgreSQL 기반의 Supabase를 사용하여 사용자, 감정 기록, 상담 이력 데이터를 관리합니다.

## 폴더 구조
```
db/
├── migrations/
│   ├── 001_initial_schema.sql                    # 세션/문진/콘텐츠 초기 테이블 + RLS
│   ├── 002_vector_tables.sql                     # RAG/임베딩 벡터 테이블 (pgvector)
│   ├── 003_reminder_preferences.sql              # 리마인더 설정 (※ /*미반영 — 보류 중)
│   ├── 004_reminder_dispatch_logs.sql            # 리마인더 전송 로그 (※ /*미반영 — 보류 중)
│   ├── 005_user_profiles.sql                     # 사용자 프로필
│   ├── 006_ai_tables.sql                         # 3-agent 상담 파이프라인 (emotion_records, counseling_history, onboarding_profile)
│   ├── 007_emotion_scoring_upgrade.sql           # VA 모델 컬럼 추가 (valence/arousal/va_radius)
│   ├── 008_fix_match_rag_chunks_global_docs.sql  # match_rag_chunks: 전역 문서(user_id IS NULL) 포함 fix
│   ├── 009_remove_legacy_intensity.sql           # emotion_records.intensity 제거 (VA 도입에 따른 정리)
│   ├── 010_watched_content_media.sql             # watched_content_records: media_provider/media_url 컬럼 추가
│   ├── 011_content_embeddings.sql                # 콘텐츠 임베딩 (추천 v2)
│   ├── 012_user_taste_vectors.sql                # 사용자 취향 벡터 (추천 v2)
│   ├── 013_recommendation_log.sql                # 추천 로그 (추천 v2)
│   └── 014_content_feedback_unique.sql           # content_feedback (user_id, content_id) UNIQUE — 토글 UX 지원
├── seed_data/
│   ├── 001_rag_sample_data.sql
│   └── 002_frontend_dev_sample_seed.sql
├── README.md
└── RAG_MIGRATION_RUNBOOK.md
```

## 마이그레이션 번호 규칙
- 아직 Supabase에 적용 전이면 번호/파일명을 정리한 후 적용합니다.
- 이미 적용된 마이그레이션 파일은 번호를 바꾸지 않고 다음 번호를 이어서 추가합니다.
- `/*미반영` 으로 시작하는 파일은 작성됐지만 아직 Supabase에 적용하지 않은 상태입니다. 적용 시점이 결정되면 주석 블록을 제거하고 그대로 실행합니다.

### 충돌 정리 이력
- **2026-05-08** — 5월 추가분 4개 파일이 기존 번호와 충돌하여 빈 슬롯으로 이동:
  - `006_watched_content_media.sql` → `010_watched_content_media.sql`
  - `001_content_embeddings.sql` → `011_content_embeddings.sql`
  - `002_user_taste_vectors.sql` → `012_user_taste_vectors.sql`
  - `003_recommendation_log.sql` → `013_recommendation_log.sql`
  - 모두 raw SQL로 이미 Supabase에 적용된 상태이므로 SQL 내용은 변경하지 않고 파일명/정렬만 정리.

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
