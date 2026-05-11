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

import asyncio
import logging
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import FastMCP

logger = logging.getLogger(__name__)

_ISO_DURATION_RE = re.compile(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$")


def _parse_iso8601_duration(value: str) -> int:
    """Return total seconds for an ISO 8601 duration like 'PT1M30S'.

    Returns 0 for parse failures or non-standard values (live streams, etc.).
    Callers should treat 0 as 'unknown' and apply conservative filtering.
    """
    if not value:
        return 0
    match = _ISO_DURATION_RE.match(value)
    if not match:
        return 0
    hours, minutes, seconds = (int(g) if g else 0 for g in match.groups())
    return hours * 3600 + minutes * 60 + seconds

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
    allow_shorts: bool = False,
) -> list[dict]:
    """
    YouTube에서 영상을 검색하고 기술적 필터링만 수행한다.
    개인화 판단은 하지 않음 — 에이전트가 이미 쿼리에 반영했음.

    Args:
        query: 검색 쿼리 (에이전트가 생성한 영어 쿼리)
        watched_ids: 제외할 영상 ID 목록
        max_results: 반환할 최대 영상 수
        allow_shorts: True면 60초 미만 쇼츠도 포함 (사용자가 명시적으로 쇼츠 요청 시).
                      False(기본)이면 videos.list로 duration을 확인해 60초 미만을 제외.

    Returns:
        [{"video_id": ..., "title": ..., "url": ..., "thumbnail": ..., "duration_seconds": ...}]
    """
    from googleapiclient.discovery import build

    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        return [{"error": "YOUTUBE_API_KEY is not set"}]

    exclude = set(watched_ids or [])

    # 쇼츠 필터 후 부족분을 흡수하려고 여유분 확보. 쇼츠 비율은 보통 20% 미만이므로 2배면 충분.
    fetch_count = min(max_results * 2 + len(exclude), 50)

    youtube = build("youtube", "v3", developerKey=api_key)
    search_request = youtube.search().list(
        q=query,
        part="snippet",
        type="video",
        maxResults=fetch_count,
        relevanceLanguage="ko",
        safeSearch="strict",
    )
    _t = time.perf_counter()
    search_response = await asyncio.to_thread(search_request.execute)
    t_search_list = time.perf_counter() - _t

    candidates: list[dict] = []
    for item in search_response.get("items", []):
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
        return [{"_perf": {
            "search_list_s": round(t_search_list, 3),
            "videos_list_s": None,
            "post_s": 0.0,
            "filtered": 0,
            "kept": 0,
        }}]

    if allow_shorts:
        return [
            *candidates[:max_results],
            {"_perf": {
                "search_list_s": round(t_search_list, 3),
                "videos_list_s": None,  # skipped
                "post_s": 0.0,
                "filtered": 0,
                "kept": len(candidates[:max_results]),
            }},
        ]

    # 2단계: videos.list로 duration 조회해 60초 미만 제외
    ids = [c["video_id"] for c in candidates]
    t_videos_list: float | None = None
    try:
        videos_request = youtube.videos().list(
            part="contentDetails",
            id=",".join(ids),
            fields="items(id,contentDetails/duration)",
            maxResults=50,
        )
        _t = time.perf_counter()
        videos_response = await asyncio.to_thread(videos_request.execute)
        t_videos_list = time.perf_counter() - _t
    except Exception as e:
        logger.warning("videos.list failed, falling back to unfiltered results: %s", type(e).__name__)
        return [
            *candidates[:max_results],
            {"_perf": {
                "search_list_s": round(t_search_list, 3),
                "videos_list_s": "failed",
                "post_s": 0.0,
                "filtered": 0,
                "kept": len(candidates[:max_results]),
            }},
        ]

    _t = time.perf_counter()
    durations: dict[str, int] = {
        item["id"]: _parse_iso8601_duration(item.get("contentDetails", {}).get("duration", ""))
        for item in videos_response.get("items", [])
    }

    results: list[dict] = []
    filtered_out = 0
    for c in candidates:
        dur = durations.get(c["video_id"], 0)
        # 0(파싱 실패·라이브 등)이나 60초 미만은 보수적으로 제외
        if dur < 60:
            filtered_out += 1
            continue
        c["duration_seconds"] = dur
        results.append(c)
        if len(results) >= max_results:
            break
    t_post = time.perf_counter() - _t

    results.append({"_perf": {
        "search_list_s": round(t_search_list, 3),
        "videos_list_s": round(t_videos_list, 3) if t_videos_list is not None else None,
        "post_s": round(t_post, 3),
        "filtered": filtered_out,
        "kept": len([r for r in results if "video_id" in r]),
    }})

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
