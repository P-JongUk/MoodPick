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
from googleapiclient.errors import HttpError

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
        logger.warning("search_youtube called without YOUTUBE_API_KEY query=%r", query)
        return [{"error": "YOUTUBE_API_KEY is not set"}]

    exclude = set(watched_ids or [])

    # duration/embeddable 필터 후에도 max_results를 채울 여지를 둔다.
    fetch_count = min(50, max(25, max_results * 2 + len(exclude), max_results + len(exclude) + 20))

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
    try:
        search_response = await asyncio.to_thread(search_request.execute)
    except HttpError as e:
        status = getattr(getattr(e, "resp", None), "status", None)
        reason = getattr(getattr(e, "resp", None), "reason", None)
        logger.warning(
            "YouTube search.list failed query=%r status=%s reason=%s",
            query,
            status,
            reason,
        )
        return [{"error": f"youtube_search_failed status={status} reason={reason}"}]
    except Exception as e:
        logger.warning(
            "YouTube search.list failed query=%r error_type=%s",
            query,
            type(e).__name__,
        )
        return [{"error": f"youtube_search_failed error_type={type(e).__name__}"}]
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
        logger.warning("YouTube search returned no candidates query=%r", query)
        return [{"_perf": {
            "search_list_s": round(t_search_list, 3),
            "videos_list_s": None,
            "post_s": 0.0,
            "filtered": 0,
            "kept": 0,
        }}]

    if allow_shorts:
        embed_ok = await _youtube_embeddable_ids(youtube, [c["video_id"] for c in candidates])
        results = [c for c in candidates if c["video_id"] in embed_ok][:max_results]
        logger.info(
            "YouTube search complete query=%r candidates=%s kept=%s allow_shorts=%s",
            query,
            len(candidates),
            len(results),
            allow_shorts,
        )
        return [
            *results,
            {"_perf": {
                "search_list_s": round(t_search_list, 3),
                "videos_list_s": None,  # duration check skipped
                "post_s": 0.0,
                "filtered": 0,
                "kept": len(results),
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
    except HttpError as e:
        status = getattr(getattr(e, "resp", None), "status", None)
        reason = getattr(getattr(e, "resp", None), "reason", None)
        logger.warning("videos.list failed, falling back to unfiltered results: status=%s reason=%s", status, reason)
        return [
            *candidates[:max_results],
            {"_perf": {
                "search_list_s": round(t_search_list, 3),
                "videos_list_s": f"failed status={status}",
                "post_s": 0.0,
                "filtered": 0,
                "kept": len(candidates[:max_results]),
            }},
        ]
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
    t_post = time.perf_counter() - _t

    embed_ok = await _youtube_embeddable_ids(youtube, [r["video_id"] for r in results])
    embeddable_results = [r for r in results if r["video_id"] in embed_ok][:max_results]
    logger.info(
        "YouTube search complete query=%r candidates=%s duration_ok=%s embeddable_kept=%s allow_shorts=%s",
        query,
        len(candidates),
        len(results),
        len(embeddable_results),
        allow_shorts,
    )

    results.append({"_perf": {
        "search_list_s": round(t_search_list, 3),
        "videos_list_s": round(t_videos_list, 3) if t_videos_list is not None else None,
        "post_s": round(t_post, 3),
        "filtered": filtered_out + (len(results) - len(embeddable_results)),
        "kept": len(embeddable_results),
    }})

    return [*embeddable_results, results[-1]]


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
