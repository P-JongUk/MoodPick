"""
mcp_servers/server.py

Unified FastMCP server for MoodPick external content APIs.
Each content platform is registered as a separate tool on the same server.

Currently supported:
  - search_youtube: YouTube Data API v3
  - recommend_podcast_episode: 큐레이션 RSS에서 에피소드 1개 선택 (ai.tools.podcast_catalog)
"""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import FastMCP

# Load .env.local from this directory
_env_path = Path(__file__).parent / ".env.local"
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path)

mcp = FastMCP("moodpick-content")

_YT_VIDEOS_LIST_CHUNK = 50


async def _youtube_embeddable_ids(youtube, video_ids: list[str]) -> set[str]:
    """videos.list(status)로 타 사이트 임베드가 허용된 영상 ID만 반환한다."""
    allowed: set[str] = set()
    for i in range(0, len(video_ids), _YT_VIDEOS_LIST_CHUNK):
        chunk = video_ids[i : i + _YT_VIDEOS_LIST_CHUNK]
        req = youtube.videos().list(part="status", id=",".join(chunk))
        resp = await asyncio.to_thread(req.execute)
        for item in resp.get("items", []):
            vid = item.get("id")
            if not vid:
                continue
            status = item.get("status") or {}
            if status.get("embeddable") is False:
                continue
            allowed.add(vid)
    return allowed


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
    임베드 비허용(status.embeddable=false) 영상은 제외하여 앱 내 재생과 맞춘다.

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

    # 검색은 최대 50건까지 받아 임베드 필터 후에도 max_results를 채울 여지를 둔다.
    search_max = min(50, max(25, max_results + len(exclude) + 20))

    youtube = build("youtube", "v3", developerKey=api_key)
    request = youtube.search().list(
        q=query,
        part="snippet",
        type="video",
        maxResults=search_max,
        relevanceLanguage="ko",
        safeSearch="strict",
    )
    response = await asyncio.to_thread(request.execute)

    candidates: list[dict] = []
    for item in response.get("items", []):
        video_id = item["id"]["videoId"]
        if video_id in exclude:
            continue
        candidates.append({
            "video_id": video_id,
            "title": item["snippet"]["title"],
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "thumbnail": item["snippet"]["thumbnails"].get("high", {}).get("url", ""),
        })

    if not candidates:
        return []

    embed_ok = await _youtube_embeddable_ids(youtube, [c["video_id"] for c in candidates])

    results = [c for c in candidates if c["video_id"] in embed_ok]
    return results[:max_results]


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


if __name__ == "__main__":
    mcp.run()
