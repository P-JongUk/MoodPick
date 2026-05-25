"""
ai/utils.py

Shared utility functions for the ai/ module.
"""

import re
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt(filename: str) -> str:
    """
    Load a prompt file from the ai/prompts/ directory.

    Args:
        filename: e.g. "system_prompt.md"

    Returns:
        The file content as a string.

    Raises:
        FileNotFoundError: if the prompt file does not exist.
    """
    path = PROMPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(
            f"Prompt file not found: {path}. "
            f"Make sure ai/prompts/{filename} exists."
        )
    return path.read_text(encoding="utf-8")


def load_crisis_response() -> str:
    """Return the pre-written crisis response text."""
    return load_prompt("crisis_response.md")


def strip_unverified_markdown_links(text: str) -> str:
    """상담 AI가 지어낸 마크다운/평문 URL을 제거한다 (API 추천 링크는 파이프라인에서만 붙임)."""
    if not text:
        return text
    cleaned = re.sub(r"\[([^\]]*)\]\(https?://[^)]+\)", r"\1", text)
    cleaned = re.sub(r"https?://\S+", "", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def format_verified_alternative_links(alternatives: list[dict]) -> str:
    """YouTube 검색 후보(2~3등)를 검증된 마크다운 링크 목록으로 만든다."""
    lines: list[str] = []
    for alt in alternatives:
        title = (alt.get("title") or "").strip()
        url = (alt.get("url") or "").strip()
        if not title or not url:
            continue
        safe_title = title.replace("[", "").replace("]", "")
        lines.append(f"- [{safe_title}]({url})")
    if not lines:
        return ""
    return "**다른 추천도 들어보세요**\n\n" + "\n".join(lines)


def append_verified_recommendation_block(
    response: str,
    *,
    title: str,
    reason: str,
    alternative_links: list[dict] | None,
    has_primary_video: bool,
) -> str:
    """상담 본문 뒤에 API 검증 링크·메인 추천 안내를 붙인다."""
    body = strip_unverified_markdown_links(response)
    parts: list[str] = []

    alt_block = format_verified_alternative_links(alternative_links or [])
    if alt_block:
        parts.append(alt_block)

    if title:
        if has_primary_video:
            parts.append(f"**이번 추천**은 아래 카드에서 '{title}'을(를) 들어보세요. {reason}")
        else:
            parts.append(f"'{title}'을(를) 추천해드릴게요. {reason}")

    if not parts:
        return body
    return f"{body}\n\n" + "\n\n".join(parts)
