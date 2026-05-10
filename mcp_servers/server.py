"""
mcp_servers/server.py

Unified FastMCP server for MoodPick external content APIs.
Each content platform is registered as a separate tool on the same server.

Currently supported:
  - search_youtube: YouTube Data API v3
  - recommend_podcast_episode: 큐레이션 RSS에서 에피소드 1개 선택 (ai.tools.podcast_catalog)

Future:
  - search_spotify: Spotify Web API
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import FastMCP

# Load .env.local from this directory
_env_path = Path(__file__).parent / ".env.local"
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path)

mcp = FastMCP("moodpick-content")


# ── YouTube ─────────────────────────────────────────────────────────────────

@mcp.tool()
async def search_youtube(
    query: str,
    watched_ids: list[str] | None = None,
    max_results: int = 5,
) -> list[dict]:
    """
    YouTube에서 영상을 검색하고 기술적 필터링만 수행한다.
    개인화 판단은 하지 않음 — 에이전트가 이미 쿼리에 반영했음.

    Args:
        query: 검색 쿼리 (에이전트가 생성한 영어 쿼리)
        watched_ids: 제외할 영상 ID 목록
        max_results: 반환할 최대 영상 수

    Returns:
        [{"video_id": ..., "title": ..., "url": ..., "thumbnail": ...}]
    """
    from googleapiclient.discovery import build

    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        return [{"error": "YOUTUBE_API_KEY is not set"}]

    exclude = set(watched_ids or [])

    # Request extra results to compensate for filtered-out videos
    fetch_count = max_results + len(exclude)

    youtube = build("youtube", "v3", developerKey=api_key)
    request = youtube.search().list(
        q=query,
        part="snippet",
        type="video",
        maxResults=min(fetch_count, 25),
        relevanceLanguage="ko",
        safeSearch="strict",
    )
    response = request.execute()

    results = []
    for item in response.get("items", []):
        video_id = item["id"]["videoId"]
        if video_id in exclude:
            continue

        results.append({
            "video_id": video_id,
            "title": item["snippet"]["title"],
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "thumbnail": item["snippet"]["thumbnails"].get("high", {}).get("url", ""),
        })

        if len(results) >= max_results:
            break

    return results


# ── Podcast (RSS 큐레이션) ─────────────────────────────────────────────────

def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


@mcp.tool()
async def recommend_podcast_episode(
    emotion: str,
    intensity: float = 0.5,
    watched_content_ids: list[str] | None = None,
) -> dict | None:
    """
    고정 RSS 피드에서 감정·시청 이력을 반영해 팟캐스트 에피소드 1개를 고른다.
    YouTube 검색과 동일하게 MCP 도구로만 외부 소스에 접근한다.

    Returns:
        {"content_id", "title", "audio_url", "thumbnail_url", "reason"} 또는 없으면 null
    """
    import sys

    root = _repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from ai.tools.podcast_catalog import recommend_podcast_episode as catalog_pick

    return catalog_pick(
        emotion=emotion,
        intensity=float(intensity),
        watched_content_ids=watched_content_ids,
    )


# ── Spotify (TODO) ──────────────────────────────────────────────────────────
# @mcp.tool()
# async def search_spotify(...) -> list[dict]:
#     ...


if __name__ == "__main__":
    mcp.run()
