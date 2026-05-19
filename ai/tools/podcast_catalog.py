"""
ai/tools/podcast_catalog.py

Search-less (A.k.a. "큐레이션") 팟캐스트 추천을 위한 RSS 파서/선택 로직.

요구사항:
  - 기본: 고정 RSS 피드 URL만으로 에피소드 1개를 고름
  - 한국어 명상 쇼: Apple Podcast **컬렉션 ID**로 `itunes.apple.com/lookup` → 공식 `feedUrl`을 받아 후보에 넣음
  - 추가로 iTunes Search API(country=kr)로 feedUrl을 가져올 수 있음 (결과는 캐시)
  - emotion(불안/수면/우울/분노/스트레스/무기력 등)과 intensity를 사용해
    키워드/길이(가능하면 duration) 중심으로 점수화
  - watched_content_ids(이전에 추천/재생된 content_id)로 중복 제거

환경 변수 (선택):
  - MOODPICK_PODCAST_ITUNES_KR: "0" 이면 iTunes 한국 후보 비활성 (오프라인 등)
  - MOODPICK_PODCAST_ITUNES_KR_QUERY: iTunes 검색어 (기본: 마음챙김 명상 불안 수면)
  - MOODPICK_PODCAST_RSS_FEEDS: 추가 RSS URL, 쉼표로 구분
  - MOODPICK_PODCAST_PREFER_KOREAN: 기본 "1". 한글 메타 에피소드가 전체 최고점과 비슷하면 한국어를 택하고,
    한국 후보가 없거나 점수가 너무 낮으면 영어로 폴백. "0" 이면 전체 풀에서 점수 최대 1개만 선택.
  - MOODPICK_PODCAST_KO_GAP: 한국어 후보 허용 점수 갭(기본 10). 전체 최고점 - 이 값 이상이면 한국어 후보 채택 후보.
  - MOODPICK_PODCAST_KO_MIN_SCORE: 한국어 후보 최소 점수(기본 2). 이보다 낮으면 전체 최고(영어) 유지.
  - MOODPICK_PODCAST_FEED_USE_SYSTEM_PROXY: 기본 "0". RSS/iTunes 요청 시 시스템 HTTP(S) 프록시를 쓰지 않음.
  - MOODPICK_PODCAST_ITUNES_COLLECTION_IDS: Apple Podcast 컬렉션 ID를 쉼표로 구분 (기본: 혜안스님·보디야나선원).
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Iterable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse, urlunparse
from urllib.request import ProxyHandler, Request, build_opener, urlopen
import xml.etree.ElementTree as ET


_RSS_TIMEOUT_SEC = 15
_ITUNES_KR_TTL_SEC = 86400
_ITUNES_KR_FAIL_TTL_SEC = 3600
_ITUNES_KR_CACHE_AT: float = 0.0
_ITUNES_KR_CACHE_URLS: list[str] = []
_ITUNES_COLLECTION_LOOKUP_CACHE_AT: float = 0.0
_ITUNES_COLLECTION_LOOKUP_CACHE_URLS: list[str] = []
_ITUNES_COLLECTION_LOOKUP_KEY: tuple[int, ...] | None = None
_FEED_CACHE_TTL_SEC = 60 * 10  # 10분 캐시
_FEED_CACHE: dict[str, tuple[float, list["PodcastEpisode"]]] = {}


def _use_system_proxy_for_feeds() -> bool:
    v = os.getenv("MOODPICK_PODCAST_FEED_USE_SYSTEM_PROXY", "0").strip().lower()
    return v in ("1", "true", "yes", "on")


def _request_body(url: str, headers: dict[str, str], timeout: int = _RSS_TIMEOUT_SEC) -> bytes:
    """RSS/iTunes용 GET. 기본은 프록시 비사용(Docker 등에서 깨진 프록시 회피)."""
    req = Request(url, headers=headers, method="GET")
    if _use_system_proxy_for_feeds():
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    else:
        opener = build_opener(ProxyHandler({}))
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read()
    if len(raw) >= 2 and raw[0] == 0x1F and raw[1] == 0x8B:
        try:
            raw = gzip.decompress(raw)
        except Exception:
            pass
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    return raw


def _fetch_rss_raw(feed_url: str) -> bytes:
    """
    팟빵/쎈호스팅 계열 RSS는 http만 두고 https를 막거나 404를 내거나,
    Referer 없으면 거절하는 경우가 있어 순차 시도한다.
    """
    u0 = feed_url.strip()
    parsed = urlparse(u0)
    host = (parsed.hostname or "").lower()

    urls: list[str] = []
    seen: set[str] = set()

    def add(u: str) -> None:
        u = u.strip()
        if u and u not in seen:
            seen.add(u)
            urls.append(u)

    add(u0)
    if parsed.scheme == "http":
        add(urlunparse(parsed._replace(scheme="https")))
    if host.endswith("ssenhosting.com") and parsed.scheme == "https":
        add(urlunparse(parsed._replace(scheme="http")))

    last_exc: Exception | None = None
    for u in urls:
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
            }
            if "ssenhosting.com" in u:
                headers["Referer"] = "https://www.podbbang.com/"
            return _request_body(u, headers=headers, timeout=_RSS_TIMEOUT_SEC)
        except (HTTPError, URLError, TimeoutError, OSError) as e:
            last_exc = e
            continue
        except Exception as e:
            last_exc = e
            continue
    if last_exc is not None:
        raise last_exc
    raise OSError("RSS fetch produced no response")


@dataclass(frozen=True)
class PodcastEpisode:
    episode_id: str  # 안정적 키(저장용)
    title: str
    description: str
    audio_url: str
    thumbnail_url: str
    pub_date_ts: float | None
    duration_seconds: int | None


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _first_text_by_localnames(root: ET.Element, localnames: Iterable[str]) -> str:
    wanted = set(localnames)
    for el in root.iter():
        if _local_name(el.tag) in wanted and el.text and el.text.strip():
            return el.text.strip()
    return ""


def _first_attr_by_localname(root: ET.Element, localname: str, attr: str) -> str:
    for el in root.iter():
        if _local_name(el.tag) == localname and attr in el.attrib and el.attrib[attr].strip():
            return el.attrib[attr].strip()
    return ""


def _find_audio_url(item: ET.Element) -> str:
    for el in item.iter():
        if _local_name(el.tag) == "enclosure" and "url" in el.attrib:
            url = el.attrib.get("url", "").strip()
            if url:
                return url
    return ""


def _find_thumbnail_url(item: ET.Element) -> str:
    thumb = _first_attr_by_localname(item, "image", "href")
    if thumb:
        return thumb
    thumb = _first_attr_by_localname(item, "itunes:image", "href")
    if thumb:
        return thumb
    for el in item.iter():
        if _local_name(el.tag) == "url" and el.text and el.text.strip():
            return el.text.strip()
    return ""


_DURATION_PATTERNS = [
    re.compile(r"(?P<m>\d{1,3}):(?P<s>\d{1,2})"),
    re.compile(r"(?P<n>\d{1,3})\s*(?:min|mins|minute|minutes)\b", re.IGNORECASE),
    re.compile(r"(?P<n>\d{1,3})\s*분"),
]


def _parse_duration_seconds(text: str) -> Optional[int]:
    if not text:
        return None
    t = text.strip()
    m = re.search(r"(?P<h>\d{1,2}):(?P<m>\d{1,2}):(?P<s>\d{1,2})", t)
    if m:
        h = int(m.group("h"))
        mi = int(m.group("m"))
        s = int(m.group("s"))
        return h * 3600 + mi * 60 + s
    for pat in _DURATION_PATTERNS:
        m = pat.search(t)
        if not m:
            continue
        if "h" in m.groupdict():
            return None
        if "m" in m.groupdict() and "s" in m.groupdict():
            return int(m.group("m")) * 60 + int(m.group("s"))
        n = m.groupdict().get("n")
        if n:
            return int(n) * 60
    return None


def _parse_pub_date_ts(item: ET.Element) -> float | None:
    raw = _first_text_by_localnames(item, ["pubDate", "published", "updated"])
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
        return dt.timestamp() if dt else None
    except Exception:
        return None


def _episode_key(audio_url: str) -> str:
    h = hashlib.sha1(audio_url.encode("utf-8")).hexdigest()
    return f"podcast:episode:{h}"


def _parse_duration_seconds_from_item(item: ET.Element) -> Optional[int]:
    dur_raw = _first_text_by_localnames(item, ["duration"])
    if dur_raw:
        return _parse_duration_seconds(dur_raw)
    title = _first_text_by_localnames(item, ["title"])
    desc = _first_text_by_localnames(item, ["description", "summary"])
    return _parse_duration_seconds(title) or _parse_duration_seconds(desc)


def _parse_rss_feed_bytes(xml_bytes: bytes, max_items: int = 60) -> list[PodcastEpisode]:
    root = ET.fromstring(xml_bytes)

    channel = root
    for el in root.iter():
        if _local_name(el.tag) == "channel":
            channel = el
            break

    items = []
    for item in root.iter():
        if _local_name(item.tag) == "item":
            items.append(item)
    if not items:
        for el in root.iter():
            if _local_name(el.tag) == "entry":
                items.append(el)

    episodes: list[PodcastEpisode] = []
    for item in items[:max_items]:
        title = _first_text_by_localnames(item, ["title"])
        desc = _first_text_by_localnames(item, ["description", "summary"])
        audio_url = _find_audio_url(item)
        if not audio_url:
            continue
        thumb = _find_thumbnail_url(item)
        pub_ts = _parse_pub_date_ts(item)
        dur = _parse_duration_seconds_from_item(item)
        episode_id = _episode_key(audio_url)
        episodes.append(
            PodcastEpisode(
                episode_id=episode_id,
                title=title.strip() or "명상 가이드",
                description=desc.strip(),
                audio_url=audio_url,
                thumbnail_url=thumb,
                pub_date_ts=pub_ts,
                duration_seconds=dur,
            )
        )
    return episodes


def _parse_rss_feed(feed_url: str, max_items: int = 60) -> list[PodcastEpisode]:
    raw = _fetch_rss_raw(feed_url)
    return _parse_rss_feed_bytes(raw, max_items=max_items)


def _get_feed_episodes(feed_url: str) -> list[PodcastEpisode]:
    now = time.time()
    cached = _FEED_CACHE.get(feed_url)
    if cached and (now - cached[0]) < _FEED_CACHE_TTL_SEC:
        return cached[1]
    episodes = _parse_rss_feed(feed_url)
    _FEED_CACHE[feed_url] = (now, episodes)
    return episodes


_HANGUL_RE = re.compile(r"[\uAC00-\uD7A3]")


def _itunes_kr_enabled() -> bool:
    v = os.getenv("MOODPICK_PODCAST_ITUNES_KR", "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def _prefer_korean_podcasts() -> bool:
    """한국 서비스 기본: 한글 에피소드 우선, 없으면 영어 폴백."""
    v = os.getenv("MOODPICK_PODCAST_PREFER_KOREAN", "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def _discover_kr_podcast_feed_urls() -> list[str]:
    """iTunes 한국 스토어에서 웰니스 성격 팟캐스트 RSS(feedUrl) 목록을 가져온다."""
    global _ITUNES_KR_CACHE_AT, _ITUNES_KR_CACHE_URLS
    now = time.time()
    if _ITUNES_KR_CACHE_AT:
        age = now - _ITUNES_KR_CACHE_AT
        ttl = _ITUNES_KR_TTL_SEC if _ITUNES_KR_CACHE_URLS else _ITUNES_KR_FAIL_TTL_SEC
        if age < ttl:
            return list(_ITUNES_KR_CACHE_URLS)

    found: list[str] = []
    try:
        q = os.getenv("MOODPICK_PODCAST_ITUNES_KR_QUERY", "마음챙김 명상 불안 수면").strip() or "마음챙김"
        url = f"https://itunes.apple.com/search?term={quote(q)}&media=podcast&country=kr&limit=12"
        raw = _request_body(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json",
                "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
            },
            timeout=12,
        )
        payload = json.loads(raw.decode("utf-8"))
        seen_local: set[str] = set()
        for r in payload.get("results", []):
            fu = (r.get("feedUrl") or "").strip()
            if not fu.startswith("http"):
                continue
            if fu in seen_local:
                continue
            seen_local.add(fu)
            found.append(fu)
    except Exception:
        found = []

    _ITUNES_KR_CACHE_AT = now
    _ITUNES_KR_CACHE_URLS = found
    return list(_ITUNES_KR_CACHE_URLS)


_DEFAULT_ITUNES_KR_COLLECTION_IDS: tuple[int, ...] = (
    953410161,  # 혜안스님의 불교명상 가이드
    1484477547,  # 보디야나선원 명상실(유도명상)
)


def _configured_itunes_kr_collection_ids() -> tuple[int, ...]:
    raw = os.getenv("MOODPICK_PODCAST_ITUNES_COLLECTION_IDS", "").strip()
    if not raw:
        return _DEFAULT_ITUNES_KR_COLLECTION_IDS
    ids: list[int] = []
    for part in raw.split(","):
        p = part.strip()
        if p.isdigit():
            ids.append(int(p))
    return tuple(ids) if ids else _DEFAULT_ITUNES_KR_COLLECTION_IDS


def _feed_urls_from_itunes_collection_ids(collection_ids: tuple[int, ...]) -> list[str]:
    """Apple lookup으로 각 컬렉션의 공식 RSS(feedUrl)을 얻는다."""
    global _ITUNES_COLLECTION_LOOKUP_CACHE_AT, _ITUNES_COLLECTION_LOOKUP_CACHE_URLS, _ITUNES_COLLECTION_LOOKUP_KEY
    if not collection_ids:
        return []
    now = time.time()
    key = tuple(int(x) for x in collection_ids)
    if _ITUNES_COLLECTION_LOOKUP_CACHE_AT and _ITUNES_COLLECTION_LOOKUP_KEY == key:
        age = now - _ITUNES_COLLECTION_LOOKUP_CACHE_AT
        ttl = _ITUNES_KR_TTL_SEC if _ITUNES_COLLECTION_LOOKUP_CACHE_URLS else _ITUNES_KR_FAIL_TTL_SEC
        if age < ttl:
            return list(_ITUNES_COLLECTION_LOOKUP_CACHE_URLS)

    want = {int(x) for x in collection_ids}
    urls: list[str] = []
    try:
        q = ",".join(str(int(i)) for i in collection_ids)
        api_url = f"https://itunes.apple.com/lookup?id={q}&entity=podcast"
        raw = _request_body(
            api_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json",
                "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
            },
            timeout=15,
        )
        payload = json.loads(raw.decode("utf-8"))
        by_cid: dict[int, str] = {}
        for r in payload.get("results", []):
            cid = r.get("collectionId")
            fu = (r.get("feedUrl") or "").strip()
            if cid is None or not fu.startswith("http"):
                continue
            icid = int(cid)
            if icid not in want:
                continue
            kind = r.get("kind")
            if kind not in (None, "podcast"):
                continue
            by_cid[icid] = fu
        for cid in collection_ids:
            icid = int(cid)
            if icid in by_cid:
                urls.append(by_cid[icid])
    except Exception:
        urls = []

    _ITUNES_COLLECTION_LOOKUP_CACHE_AT = now
    _ITUNES_COLLECTION_LOOKUP_CACHE_URLS = urls
    _ITUNES_COLLECTION_LOOKUP_KEY = key
    return list(_ITUNES_COLLECTION_LOOKUP_CACHE_URLS)


def _all_feed_urls() -> list[str]:
    """영어 고정 + (선택) 수동 한국 RSS + Apple 컬렉션 lookup RSS + env 추가 + iTunes 검색 KR."""
    out: list[str] = []
    seen: set[str] = set()

    def add(u: str) -> None:
        u = u.strip()
        if not u.startswith("http") or u in seen:
            return
        seen.add(u)
        out.append(u)

    for u in _CURATED_FEEDS:
        add(u)
    for u in _CURATED_FEEDS_KR:
        add(u)
    for u in _feed_urls_from_itunes_collection_ids(_configured_itunes_kr_collection_ids()):
        add(u)
    extra = os.getenv("MOODPICK_PODCAST_RSS_FEEDS", "").strip()
    if extra:
        for part in extra.split(","):
            add(part)
    if _itunes_kr_enabled():
        for u in _discover_kr_podcast_feed_urls():
            add(u)
    return out


def _score_episode(
    ep: PodcastEpisode,
    watched_ids: set[str],
    keywords: list[str],
    duration_range: tuple[int, int] | None,
) -> float:
    if ep.episode_id in watched_ids:
        return float("-inf")
    if not ep.audio_url:
        return float("-inf")

    title_desc = f"{ep.title}\n{ep.description}".lower()
    score = 0.0

    for kw in keywords:
        if not kw:
            continue
        if kw.lower() in title_desc:
            score += 3.0

    if _HANGUL_RE.search(f"{ep.title}\n{ep.description}"):
        score += 1.25

    if duration_range and ep.duration_seconds:
        lo, hi = duration_range
        if lo <= ep.duration_seconds <= hi:
            score += 4.0
        else:
            target = (lo + hi) / 2
            diff = abs(ep.duration_seconds - target)
            score += max(0.0, 2.0 - diff / max(1.0, target))

    if ep.pub_date_ts:
        age_days = max(0.0, (time.time() - ep.pub_date_ts) / (3600 * 24))
        score += max(0.0, 2.0 - age_days / 15)

    return score


def _episode_has_hangul(ep: PodcastEpisode) -> bool:
    return bool(_HANGUL_RE.search(f"{ep.title}\n{ep.description}"))


def _category_for_emotion(emotion: str) -> tuple[list[str], tuple[int, int] | None]:
    e = (emotion or "").strip()

    if e in {"불안", "스트레스", "외로움", "공황", "긴장"}:
        return (
            ["호흡", "불안", "진정", "calm", "breathing", "anxiety", "grounding", "panic", "relax", "mindfulness"],
            (180, 480),
        )
    if e in {"수면", "무기력", "피로"}:
        return (
            ["수면", "잠", "바디스캔", "sleep", "body scan", "relax", "bed", "night", "slow"],
            (600, 1200),
        )
    if e in {"우울", "슬픔", "자책"}:
        return (
            ["자기연민", "자애", "self-compassion", "kindness", "우울", "슬픔", "sad", "depression", "healing"],
            (420, 900),
        )
    if e in {"분노", "짜증"}:
        return (
            ["분노", "짜증", "anger", "irritation", "calm", "breath", "reset", "tension", "release"],
            (240, 720),
        )

    return (
        ["호흡", "relax", "mindfulness", "calm", "이완", "grounding"],
        (300, 900),
    )


_CURATED_FEEDS: list[str] = [
    "https://feeds.npr.org/510338/podcast.xml",
    "https://anchor.fm/s/123de8e0/podcast/rss",
]

# 수동 한국 RSS (선택). 필요 시 MOODPICK_PODCAST_RSS_FEEDS 또는 여기에 추가.
_CURATED_FEEDS_KR: list[str] = [
    "https://anchor.fm/s/10f3ef05c/podcast/rss",  # 생활과 명상
    "https://anchor.fm/s/1059eea20/podcast/rss",  # 라온 몸마음
]


def _ko_gap_tolerance() -> float:
    try:
        return float(os.getenv("MOODPICK_PODCAST_KO_GAP", "10"))
    except ValueError:
        return 10.0


def _ko_min_score_for_korean_pick() -> float:
    try:
        return float(os.getenv("MOODPICK_PODCAST_KO_MIN_SCORE", "2"))
    except ValueError:
        return 2.0


def recommend_podcast_episode(
    emotion: str,
    intensity: float,
    watched_content_ids: list[str] | None = None,
) -> Optional[dict]:
    """
    Returns:
      {
        "content_id": "podcast:episode:<sha1>",
        "title": "...",
        "audio_url": "...",
        "thumbnail_url": "...",
        "reason": "..."
      }
    """
    watched_ids = set(watched_content_ids or [])

    keywords, duration_range = _category_for_emotion(emotion)

    if duration_range and intensity is not None:
        lo, hi = duration_range
        try:
            i = float(intensity)
        except Exception:
            i = 0.5
        if i >= 0.7:
            duration_range = (lo, max(lo + 60, int((lo + hi) * 0.7)))

    scored: list[tuple[float, PodcastEpisode]] = []

    for feed_url in _all_feed_urls():
        try:
            episodes = _get_feed_episodes(feed_url)
        except Exception:
            continue

        for ep in episodes[:60]:
            s = _score_episode(ep, watched_ids, keywords, duration_range)
            if s > float("-inf"):
                scored.append((s, ep))

    if not scored:
        return None

    best_any_score, best_any_ep = max(scored, key=lambda x: x[0])

    if not _prefer_korean_podcasts():
        best = best_any_ep
    else:
        ko_scored = [(s, ep) for s, ep in scored if _episode_has_hangul(ep)]
        if not ko_scored:
            best = best_any_ep
        else:
            best_ko_score, best_ko_ep = max(ko_scored, key=lambda x: x[0])
            gap = _ko_gap_tolerance()
            rel_min = _ko_min_score_for_korean_pick()
            if best_ko_score >= rel_min and best_ko_score >= best_any_score - gap:
                best = best_ko_ep
            else:
                best = best_any_ep

    reason_map = {
        "불안": "지금 불안이 올라올 때 바로 도움이 되는 호흡/진정 가이드를 추천드릴게요.",
        "스트레스": "스트레스가 올라올 때 마음을 천천히 가라앉히는 짧은 안내를 추천드릴게요.",
        "수면": "잠들기 전 긴장을 풀어주는 수면 가이드를 추천드릴게요.",
        "우울": "자책이 커질 때 마음을 부드럽게 다독이는 가이드를 추천드릴게요.",
        "분노": "분노가 올라올 때 긴장을 풀고 반응을 늦추는 가이드를 추천드릴게요.",
    }
    reason = reason_map.get(emotion, "지금의 감정에 맞춰 마음을 정리하는 오디오 가이드를 추천드릴게요.")

    return {
        "content_id": best.episode_id,
        "title": best.title,
        "audio_url": best.audio_url,
        "thumbnail_url": best.thumbnail_url,
        "reason": reason,
    }
