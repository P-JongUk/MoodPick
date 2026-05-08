"""
ai/tools/podcast_catalog.py

Search-less (A.k.a. "큐레이션") 팟캐스트 추천을 위한 RSS 파서/선택 로직.

요구사항:
  - 외부 "검색 API" 없이 (RSS 피드 URL만 가지고) 에피소드 1개를 고름
  - emotion(불안/수면/우울/분노/스트레스/무기력 등)과 intensity를 사용해
    키워드/길이(가능하면 duration) 중심으로 점수화
  - watched_content_ids(이전에 추천/재생된 content_id)로 중복 제거
"""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Iterable, Optional
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


_RSS_TIMEOUT_SEC = 15
_FEED_CACHE_TTL_SEC = 60 * 10  # 10분 캐시
_FEED_CACHE: dict[str, tuple[float, list["PodcastEpisode"]]] = {}


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
    # "{namespace}tag" or "tag"
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
    # RSS: <enclosure url="..."> (enclosure may not have namespace)
    for el in item.iter():
        if _local_name(el.tag) == "enclosure" and "url" in el.attrib:
            url = el.attrib.get("url", "").strip()
            if url:
                return url

    # Atom fallback (rare): <link href="..."> but podcasts usually use enclosure
    return ""


def _find_thumbnail_url(item: ET.Element) -> str:
    # Common: <itunes:image href="..."/>
    thumb = _first_attr_by_localname(item, "image", "href")
    if thumb:
        return thumb
    # Sometimes <itunes:image href="..."/> where localname is "image" already handled.
    thumb = _first_attr_by_localname(item, "itunes:image", "href")
    if thumb:
        return thumb

    # Some feeds: <image><url>...</url></image>
    # Look for any element named "url" under an "image" container.
    for el in item.iter():
        if _local_name(el.tag) == "url" and el.text and el.text.strip():
            # Avoid grabbing random urls from description if possible.
            return el.text.strip()
    return ""


_DURATION_PATTERNS = [
    # "12:34" => 12m34s
    re.compile(r"(?P<m>\d{1,3}):(?P<s>\d{1,2})"),
    # "5 min" / "5 minutes"
    re.compile(r"(?P<n>\d{1,3})\s*(?:min|mins|minute|minutes)\b", re.IGNORECASE),
    # "5분"
    re.compile(r"(?P<n>\d{1,3})\s*분"),
]


def _parse_duration_seconds(text: str) -> Optional[int]:
    if not text:
        return None
    t = text.strip()

    # Try explicit HH:MM:SS
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
    # 짧고 안정적인 content_id 생성: podcast:episode:<sha1(enclosure_url)>
    h = hashlib.sha1(audio_url.encode("utf-8")).hexdigest()
    return f"podcast:episode:{h}"


def _parse_duration_seconds_from_item(item: ET.Element) -> Optional[int]:
    # itunes:duration is common; local name tends to be "duration"
    dur_raw = _first_text_by_localnames(item, ["duration"])
    if dur_raw:
        return _parse_duration_seconds(dur_raw)

    # fallback: title/description에 "5분" 같은 패턴이 있으면 파싱
    title = _first_text_by_localnames(item, ["title"])
    desc = _first_text_by_localnames(item, ["description", "summary"])
    return _parse_duration_seconds(title) or _parse_duration_seconds(desc)


def _parse_rss_feed(feed_url: str, max_items: int = 60) -> list[PodcastEpisode]:
    req = Request(
        feed_url,
        headers={
            "User-Agent": "MoodPick/1.0 (podcast_catalog RSS parser)",
            "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
        },
        method="GET",
    )
    with urlopen(req, timeout=_RSS_TIMEOUT_SEC) as resp:
        xml_bytes = resp.read()

    root = ET.fromstring(xml_bytes)

    channel = root
    # RSS: <rss><channel>...; Atom: <feed>... but item still exists.
    for el in root.iter():
        if _local_name(el.tag) == "channel":
            channel = el
            break

    items = []
    for item in root.iter():
        if _local_name(item.tag) == "item":
            items.append(item)
    # If Atom, the items may be under <entry>
    if not items:
        for el in root.iter():
            if _local_name(el.tag) == "entry":
                items.append(el)

    episodes: list[PodcastEpisode] = []
    now = time.time()
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

    # Some feeds may put newest at top; still safe to keep ordering.
    return episodes


def _get_feed_episodes(feed_url: str) -> list[PodcastEpisode]:
    now = time.time()
    cached = _FEED_CACHE.get(feed_url)
    if cached and (now - cached[0]) < _FEED_CACHE_TTL_SEC:
        return cached[1]

    episodes = _parse_rss_feed(feed_url)
    _FEED_CACHE[feed_url] = (now, episodes)
    return episodes


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

    if duration_range and ep.duration_seconds:
        lo, hi = duration_range
        if lo <= ep.duration_seconds <= hi:
            score += 4.0
        else:
            # 가깝게라도 맞으면 약간 가점
            target = (lo + hi) / 2
            diff = abs(ep.duration_seconds - target)
            score += max(0.0, 2.0 - diff / max(1.0, target))

    # recency 가중치 (pub_date_ts가 있으면)
    if ep.pub_date_ts:
        age_days = max(0.0, (time.time() - ep.pub_date_ts) / (3600 * 24))
        score += max(0.0, 2.0 - age_days / 15)

    return score


def _category_for_emotion(emotion: str) -> tuple[list[str], tuple[int, int] | None]:
    e = (emotion or "").strip()

    # 한국어/영어 키워드를 같이 넣어서 feed 언어 차이를 흡수
    if e in {"불안", "스트레스", "외로움", "공황", "긴장"}:
        return (
            ["호흡", "불안", "진정", "calm", "breathing", "anxiety", "grounding", "panic", "relax", "mindfulness"],
            (180, 480),  # 3~8분
        )
    if e in {"수면", "무기력", "피로"}:
        return (
            ["수면", "잠", "바디스캔", "sleep", "body scan", "relax", "bed", "night", "slow"],
            (600, 1200),  # 10~20분
        )
    if e in {"우울", "슬픔", "자책"}:
        return (
            ["자기연민", "자애", "self-compassion", "kindness", "우울", "슬픔", "sad", "depression", "healing"],
            (420, 900),  # 7~15분
        )
    if e in {"분노", "짜증"}:
        return (
            ["분노", "짜증", "anger", "irritation", "calm", "breath", "reset", "tension", "release"],
            (240, 720),  # 4~12분
        )

    # fallback
    return (
        ["호흡", "relax", "mindfulness", "calm", "이완", "grounding"],
        (300, 900),
    )


# 큐레이션 RSS: MVP에서는 "검색 없음"이므로 피드 URL만 고정
_CURATED_FEEDS: list[str] = [
    # NPR Life Kit: 불안/스트레스 대처 및 마음챙김/호흡 관련 에피소드가 많음
    "https://feeds.npr.org/510338/podcast.xml",
    # Mindfulness For Beginners: mindfulness/meditation 기반
    "https://anchor.fm/s/123de8e0/podcast/rss",
]


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

    # intensity가 높으면 더 짧게 유도
    if duration_range and intensity is not None:
        lo, hi = duration_range
        try:
            i = float(intensity)
        except Exception:
            i = 0.5
        if i >= 0.7:
            duration_range = (lo, max(lo + 60, int((lo + hi) * 0.7)))

    best: PodcastEpisode | None = None
    best_score = float("-inf")

    for feed_url in _CURATED_FEEDS:
        try:
            episodes = _get_feed_episodes(feed_url)
        except Exception:
            continue

        for ep in episodes[:60]:
            s = _score_episode(ep, watched_ids, keywords, duration_range)
            if s > best_score:
                best_score = s
                best = ep

    if not best:
        return None

    # Reason은 앱에 맞게 짧고 구체적으로
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

