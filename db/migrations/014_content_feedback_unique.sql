-- 014_content_feedback_unique.sql
-- content_feedback에 (user_id, content_id) UNIQUE 제약 추가.
-- 토글 UX: 사용자당 영상당 row 1개. like/dislike는 update, 취소는 row 삭제.
--
-- 변경 이유:
--   기존 스키마는 unique 제약이 없어 동일 영상에 like가 여러 번 쌓이는 케이스 발생
--   (테스트 환경에서 단일 영상 5번 좋아요 → user_taste_vectors가 단일 임베딩에 편향).
--   토글을 지원하면서 데이터 품질을 보존하려면 DB 레벨에서 (user_id, content_id) 1행을
--   강제하고, 애플리케이션은 upsert + delete 패턴으로 동작해야 한다.

-- 1) 기존 중복 정리: (user_id, content_id) 그룹에서 가장 최근 row 1개만 보존
WITH ranked AS (
  SELECT
    id,
    ROW_NUMBER() OVER (
      PARTITION BY user_id, content_id
      ORDER BY created_at DESC, id DESC
    ) AS rn
  FROM public.content_feedback
)
DELETE FROM public.content_feedback
WHERE id IN (SELECT id FROM ranked WHERE rn > 1);

-- 2) UNIQUE 제약 추가
ALTER TABLE public.content_feedback
ADD CONSTRAINT content_feedback_unique_user_content
UNIQUE (user_id, content_id);
