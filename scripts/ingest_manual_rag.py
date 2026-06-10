#!/usr/bin/env python3
"""
scripts/ingest_manual_rag.py

비대면 심리지원(상담) 매뉴얼 PDF를 파싱하고,
청킹·임베딩 후 Supabase RAG DB에 업로드하는 스크립트.

사용법:
    cd <project_root>
    python scripts/ingest_manual_rag.py

사전 설치 (프로젝트 venv 안에서):
    pip install pypdf openai supabase python-dotenv

환경 변수:
    backend/.env.local 에 아래 항목이 설정되어 있어야 합니다.
    - OPENAI_API_KEY
    - SUPABASE_URL
    - SUPABASE_SERVICE_ROLE_KEY
"""

import os
import re
import sys
import time
from pathlib import Path

# ── 경로 설정 ─────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent

# backend/.env.local 에서 환경 변수 로드
from dotenv import load_dotenv
load_dotenv(ROOT / "backend" / ".env.local")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ── 설정 ──────────────────────────────────────────────────────────────────────
PDF_PATH       = ROOT / "papers" / "비대면_심리지원(상담)_매뉴얼.pdf"
CHUNK_MAX_CHARS  = 1200   # 한국어 기준 약 400 토큰
CHUNK_OVERLAP_CHARS = 150
EMBEDDING_MODEL  = "text-embedding-3-small"
DOCUMENT_TITLE   = "비대면 심리지원(상담) 매뉴얼"
SOURCE_TYPE      = "manual"
RATE_LIMIT_PAUSE = 0.3    # 초 (OpenAI Embedding API rate limit 방지)


# ── PDF 파싱 ──────────────────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_path: Path) -> str:
    """pypdf로 각 페이지 텍스트를 추출해 하나의 문자열로 반환."""
    try:
        from pypdf import PdfReader
    except ImportError:
        print("❌ pypdf 패키지가 없습니다. 다음 명령으로 설치하세요:")
        print("   pip install pypdf")
        sys.exit(1)

    reader = PdfReader(str(pdf_path))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text and text.strip():
            pages.append(text.strip())

    return "\n\n".join(pages)


# ── 청킹 ──────────────────────────────────────────────────────────────────────

def chunk_text(text: str) -> list[str]:
    """
    섹션 헤더를 우선 기준으로 분할하고,
    너무 긴 섹션은 문단(빈 줄) 단위로 추가 분할.

    전략:
      1. 연속 개행 3개 이상 → 2개로 정규화
      2. 숫자/한자 섹션 헤더 앞에서 분할 (예: '1.' '제3장' '가.' 등)
      3. 분할된 섹션이 CHUNK_MAX_CHARS 초과 시 문단 단위로 재분할
      4. 재분할 시 CHUNK_OVERLAP_CHARS 길이만큼 앞 청크 끝을 다음 청크 앞에 붙임
      5. 50자 미만 청크 필터링
    """
    # 공백 정규화
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)

    # 섹션 헤더 기준 1차 분할
    # 패턴: 줄 시작에 숫자·마침표, 제N장, 제N절, 가나다 목록 등
    section_pattern = re.compile(
        r'\n(?=(?:\d{1,2}[\.\)]\s|\d{1,2}\.\d{1,2}\s|제\s*\d+\s*[장절]|[①-⑳]\s|[가-힣]\.\s))'
    )
    raw_sections = section_pattern.split(text)

    chunks: list[str] = []

    for section in raw_sections:
        section = section.strip()
        if not section:
            continue

        if len(section) <= CHUNK_MAX_CHARS:
            chunks.append(section)
        else:
            # 문단 단위 재분할
            paragraphs = [p.strip() for p in section.split('\n\n') if p.strip()]
            current = ""

            for para in paragraphs:
                if len(current) + len(para) + 2 <= CHUNK_MAX_CHARS:
                    current = (current + "\n\n" + para).strip() if current else para
                else:
                    if current:
                        chunks.append(current)
                    # 이전 청크 끝 overlap 붙이기
                    tail = current[-CHUNK_OVERLAP_CHARS:] if len(current) > CHUNK_OVERLAP_CHARS else current
                    current = (tail + "\n\n" + para).strip() if tail else para

            if current:
                chunks.append(current)

    # 너무 짧은 청크 제거
    return [c for c in chunks if len(c.strip()) >= 50]


# ── 임베딩 ────────────────────────────────────────────────────────────────────

def embed_text(text: str, openai_client) -> list[float]:
    response = openai_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text.strip(),
    )
    return response.data[0].embedding


# ── 중복 체크 ─────────────────────────────────────────────────────────────────

def find_existing_document(supabase, title: str) -> str | None:
    """동일 제목의 전역 문서가 있으면 document_id를 반환."""
    result = (
        supabase.table("rag_documents")
        .select("id")
        .eq("title", title)
        .is_("user_id", "null")
        .execute()
    )
    return result.data[0]["id"] if result.data else None


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main() -> None:
    # 1. 환경 변수 검증
    missing = [
        name for name, val in {
            "OPENAI_API_KEY": OPENAI_API_KEY,
            "SUPABASE_URL": SUPABASE_URL,
            "SUPABASE_SERVICE_ROLE_KEY": SUPABASE_SERVICE_ROLE_KEY,
        }.items()
        if not val
    ]
    if missing:
        print(f"❌ 환경 변수 누락: {', '.join(missing)}")
        print("   backend/.env.local 파일을 확인하세요.")
        sys.exit(1)

    # 2. PDF 존재 확인
    if not PDF_PATH.exists():
        print(f"❌ PDF 파일을 찾을 수 없습니다: {PDF_PATH}")
        sys.exit(1)

    # 3. 클라이언트 초기화
    from openai import OpenAI
    from supabase import create_client

    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    # 4. 중복 업로드 방지
    existing_id = find_existing_document(supabase, DOCUMENT_TITLE)
    if existing_id:
        print(f"⚠️  이미 업로드된 문서가 있습니다.")
        print(f"   document_id : {existing_id}")
        print("   재업로드하려면 Supabase SQL Editor에서 아래 쿼리 실행 후 다시 시도하세요:")
        print(f"   DELETE FROM rag_documents WHERE id = '{existing_id}';")
        sys.exit(0)

    # 5. PDF 파싱
    print(f"📄 PDF 파싱 중: {PDF_PATH.name}")
    full_text = extract_text_from_pdf(PDF_PATH)
    print(f"   추출 텍스트 길이: {len(full_text):,} 자")

    # 6. 청킹
    chunks = chunk_text(full_text)
    print(f"   생성된 청크 수: {len(chunks)}개")
    if not chunks:
        print("❌ 청크가 생성되지 않았습니다. PDF 파싱 결과를 확인하세요.")
        sys.exit(1)

    # 7. rag_documents 등록 (user_id=None → 전역 공유)
    print("\n📋 rag_documents 등록 중...")
    doc_result = (
        supabase.table("rag_documents")
        .insert({
            "user_id": None,
            "source_type": SOURCE_TYPE,
            "source_ref": PDF_PATH.name,
            "title": DOCUMENT_TITLE,
            "metadata": {
                "language": "ko",
                "category": "psychological_support",
                "publisher": "국립정신건강센터·국가트라우마센터",
                "chunk_max_chars": CHUNK_MAX_CHARS,
                "total_chunks": len(chunks),
            },
        })
        .execute()
    )
    document_id = doc_result.data[0]["id"]
    print(f"   document_id: {document_id}")

    # 8. 청크 임베딩 및 업로드
    print(f"\n🔢 {len(chunks)}개 청크 임베딩 및 업로드 중...\n")
    success, failed = 0, 0

    for i, chunk_content in enumerate(chunks):
        try:
            embedding = embed_text(chunk_content, openai_client)

            supabase.table("rag_chunks").insert({
                "document_id": document_id,
                "user_id": None,               # 전역 공유 → 모든 사용자 검색 가능
                "chunk_index": i,
                "content": chunk_content,
                "token_count": len(chunk_content) // 3,  # 한국어 rough estimate
                "embedding": embedding,
            }).execute()

            success += 1
            # 진행 상황 표시
            bar_len = 30
            filled = int(bar_len * (i + 1) / len(chunks))
            bar = "█" * filled + "░" * (bar_len - filled)
            print(f"  [{bar}] {i+1}/{len(chunks)}  ✓", end="\r")

            # Rate limit 방지
            time.sleep(RATE_LIMIT_PAUSE)

        except Exception as e:
            failed += 1
            print(f"\n  ⚠️  청크 {i} 실패: {e}")

    # 9. 결과 요약
    print(f"\n\n{'='*50}")
    print(f"✅ 완료!")
    print(f"   성공: {success}개 / 실패: {failed}개")
    print(f"   document_id: {document_id}")
    print(f"   문서 제목: {DOCUMENT_TITLE}")
    if failed > 0:
        print(f"\n⚠️  {failed}개 청크가 실패했습니다. 로그를 확인 후 스크립트를 재실행하세요.")
        print(f"   재실행 전 아래 쿼리로 기존 데이터 삭제 필요:")
        print(f"   DELETE FROM rag_documents WHERE id = '{document_id}';")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
