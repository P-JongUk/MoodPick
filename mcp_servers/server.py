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
import html
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

# YouTube Shorts는 최대 3분(180초)까지 가능하지만, 1~3분의 정상 영상도 함께
# 걸리는 트레이드오프를 피하기 위해 임계값을 120초로 둔다.
_SHORTS_MAX_SECONDS = 120


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

_YOUTUBE_SEARCH_TIMEOUT_SEC = float(os.getenv("YOUTUBE_SEARCH_TIMEOUT_SEC", "60"))
_YOUTUBE_VIDEOS_TIMEOUT_SEC = float(os.getenv("YOUTUBE_VIDEOS_TIMEOUT_SEC", "60"))


def _is_playable(status: dict) -> bool:
    """Return whether a YouTube video is safe to embed and play in the app."""
    if status.get("uploadStatus") != "processed":
        return False
    if status.get("privacyStatus") not in ("public", "unlisted"):
        return False
    return status.get("embeddable") is True


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
        logger.warning("search_youtube unavailable: missing_api_key query_len=%s", len(query or ""))
        return [{"error": "youtube_search_unavailable"}]

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
        videoEmbeddable="true",
        videoSyndicated="true",
    )
    _t = time.perf_counter()
    try:
        search_response = await asyncio.wait_for(
            asyncio.to_thread(search_request.execute),
            timeout=_YOUTUBE_SEARCH_TIMEOUT_SEC,
        )
    except HttpError as e:
        status = getattr(getattr(e, "resp", None), "status", None)
        reason = getattr(getattr(e, "resp", None), "reason", None)
        logger.warning(
            "YouTube search.list failed query_len=%s status=%s reason=%s",
            len(query or ""),
            status,
            reason,
        )
        return [{"error": "youtube_search_failed"}]
    except Exception as e:
        logger.warning(
            "YouTube search.list failed query_len=%s error_type=%s",
            len(query or ""),
            type(e).__name__,
        )
        return [{"error": "youtube_search_failed"}]
    t_search_list = time.perf_counter() - _t

    candidates: list[dict] = []
    for item in search_response.get("items", []):
        video_id = item["id"]["videoId"]
        if video_id in exclude:
            continue
        candidates.append({
            "video_id": video_id,
            "title": html.unescape(item["snippet"]["title"]),
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "thumbnail": item["snippet"]["thumbnails"].get("high", {}).get("url", ""),
        })

    if not candidates:
        logger.warning("YouTube search returned no candidates query_len=%s", len(query or ""))
        return [{"_perf": {
            "search_list_s": round(t_search_list, 3),
            "videos_list_s": None,
            "post_s": 0.0,
            "filtered": 0,
            "kept": 0,
        }}]

    if allow_shorts:
        ids = [c["video_id"] for c in candidates]
        _t = time.perf_counter()
        try:
            status_req = youtube.videos().list(
                part="status",
                id=",".join(ids),
                fields="items(id,status/embeddable,status/uploadStatus,status/privacyStatus)",
                maxResults=50,
            )
            status_resp = await asyncio.wait_for(
                asyncio.to_thread(status_req.execute),
                timeout=_YOUTUBE_VIDEOS_TIMEOUT_SEC,
            )
            t_status = time.perf_counter() - _t
        except HttpError as e:
            http_status = getattr(getattr(e, "resp", None), "status", None)
            reason = getattr(getattr(e, "resp", None), "reason", None)
            logger.warning(
                "videos.list(status) failed for allow_shorts path: status=%s reason=%s",
                http_status,
                reason,
            )
            t_status = None
            status_resp = {}
        except Exception as e:
            logger.warning(
                "videos.list(status) failed for allow_shorts path: error_type=%s",
                type(e).__name__,
            )
            t_status = None
            status_resp = {}

        playable_ids: set[str] = set()
        for item in status_resp.get("items", []):
            vid = item.get("id")
            if vid and _is_playable(item.get("status") or {}):
                playable_ids.add(vid)

        results = [c for c in candidates if c["video_id"] in playable_ids][:max_results]
        filtered_shorts = len(candidates) - len(playable_ids)
        logger.info(
            "YouTube search complete query_len=%s candidates=%s kept=%s allow_shorts=%s",
            len(query or ""),
            len(candidates),
            len(results),
            allow_shorts,
        )
        return [
            *results,
            {"_perf": {
                "search_list_s": round(t_search_list, 3),
                "videos_list_s": round(t_status, 3) if t_status is not None else None,
                "post_s": 0.0,
                "filtered": filtered_shorts,
                "kept": len(results),
            }},
        ]

    # 2단계: videos.list로 duration + status를 한 번에 조회해 필터링
    ids = [c["video_id"] for c in candidates]
    t_videos_list: float | None = None
    try:
        videos_request = youtube.videos().list(
            part="contentDetails,status",
            id=",".join(ids),
            fields="items(id,contentDetails/duration,status/embeddable,status/uploadStatus,status/privacyStatus)",
            maxResults=50,
        )
        _t = time.perf_counter()
        videos_response = await asyncio.wait_for(
            asyncio.to_thread(videos_request.execute),
            timeout=_YOUTUBE_VIDEOS_TIMEOUT_SEC,
        )
        t_videos_list = time.perf_counter() - _t
    except HttpError as e:
        http_status = getattr(getattr(e, "resp", None), "status", None)
        reason = getattr(getattr(e, "resp", None), "reason", None)
        logger.warning("videos.list failed, falling back to unfiltered results: status=%s reason=%s", http_status, reason)
        return [
            *candidates[:max_results],
            {"_perf": {
                "search_list_s": round(t_search_list, 3),
                "videos_list_s": f"failed status={http_status}",
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
    candidates_by_id = {c["video_id"]: c for c in candidates}
    results: list[dict] = []
    filtered_out = 0

    for item in videos_response.get("items", []):
        vid = item.get("id")
        if not vid:
            continue

        if not _is_playable(item.get("status") or {}):
            filtered_out += 1
            continue

        dur = _parse_iso8601_duration(item.get("contentDetails", {}).get("duration", ""))
        # 0(파싱 실패·라이브 등)이나 _SHORTS_MAX_SECONDS 이하는 보수적으로 제외
        if dur <= _SHORTS_MAX_SECONDS:
            filtered_out += 1
            continue

        candidate = candidates_by_id.get(vid)
        if candidate:
            candidate["duration_seconds"] = dur
            results.append(candidate)

    t_post = time.perf_counter() - _t
    final_results = results[:max_results]

    logger.info(
        "YouTube search complete query_len=%s candidates=%s filtered=%s kept=%s allow_shorts=%s",
        len(query or ""),
        len(candidates),
        filtered_out,
        len(final_results),
        allow_shorts,
    )

    return [
        *final_results,
        {"_perf": {
            "search_list_s": round(t_search_list, 3),
            "videos_list_s": round(t_videos_list, 3) if t_videos_list is not None else None,
            "post_s": round(t_post, 3),
            "filtered": filtered_out,
            "kept": len(final_results),
        }},
    ]


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
