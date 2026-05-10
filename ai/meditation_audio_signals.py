"""오디오·음악 세부 신호 휴리스틱.

라우팅(audio/video/music 분류)은 Orchestrator의 `content_format`이 담당한다.
이 모듈은 LLM이 잡기 어려운 미세 신호만 다룬다:
- `wants_music_only_bgm`: "말 없이/인스트루멘탈/BGM" 등 보컬·내레이션 없는 음악만
  원하는지. 검색 쿼리에 인스트루멘탈 강조 키워드 추가용 + 클라리피 답변 파싱용.
- `explicit_wants_guided`: "가이드/안내" 등 가이드형 명시. 클라리피 답변 파싱용.
- `is_video_content` / `is_audio_content` / `is_music_content`: content_format
  비교 헬퍼.
"""

_WELLNESS_CONTEXT_HINTS = (
    "명상",
    "수면",
    "호흡",
    "마음챙김",
    "mindfulness",
    "mindful",
    "meditation",
    "sleep",
    "asmr",
    "팟캐스트",
    "podcast",
    "잠 안",
    "불면",
    "바디스캔",
    "body scan",
    "이완",
    "긴장 풀",
    "스트레스 풀",
)


def _has_wellness_context(message: str) -> bool:
    m = message.lower()
    return any(w in m for w in _WELLNESS_CONTEXT_HINTS)


def has_wellness_context(message: str | None) -> bool:
    """추천 분기 등에서 웰니스(명상·수면 등) 맥락 여부."""
    if not message or not message.strip():
        return False
    return _has_wellness_context(message.strip())


def wants_music_only_bgm(message: str | None) -> bool:
    if not message:
        return False
    m = message.lower()
    phrases = (
        "말 없이",
        "말없이",
        "말 없는",
        "말없는",
        "말 안 나오",
        "말 나오는 거 싫",
        "말 나오는게 싫",
        "말하는 거 싫",
        "음악만",
        "순수 음악",
        "노래만",
        "bgm",
        "배경음",
        "인스트루멘탈",
        "instrumental",
        "가이드 말고",
        "가이드 빼",
        "가이드 없",
        "가이드형 싫",
        "가이드 싫",
        "내레이션 없",
        "나레이션 없",
        "no talking",
        "music only",
        "just music",
        "ambient only",
        "instrumentals only",
        "피아노만",
        "piano only",
    )
    return any(p in m for p in phrases)


def explicit_wants_guided(message: str | None) -> bool:
    if not message:
        return False
    m = message.lower()
    needles = (
        "가이드",
        "guided",
        "안내 따라",
        "따라할게",
        "따라 할",
        "명상 가이드",
        "안내해",
    )
    return any(n in m for n in needles)


def is_video_content(content_format: str | None) -> bool:
    return (content_format or "").lower() == "video"


def is_audio_content(content_format: str | None) -> bool:
    return (content_format or "").lower() == "audio"


def is_music_content(content_format: str | None) -> bool:
    return (content_format or "").lower() == "music"


def likely_music_search_request(message: str | None) -> bool:
    """
    특정 곡·플레이리스트·일반 음악 검색으로 보이면 True를 반환한다.
    이 경우 팟캐스트 RSS 추천을 건너뛰고 YouTube 검색으로 보낸다.
    """
    if not message or not message.strip():
        return False
    raw = message.strip()
    m = raw.lower()

    if any(n in m for n in ("유튜브", "youtube", "영상", "video")) and (
        "말고" in m or "싫" in m or "빼" in m
    ):
        return False

    if wants_music_only_bgm(message):
        return True

    wellness = _has_wellness_context(raw)

    music_markers = (
        "노래",
        "곡이",
        "좋아하는 곡",
        "플레이리스트",
        "playlist",
        "뮤비",
        "뮤직비디오",
        "music video",
        " ost",
        "ost ",
        "soundtrack",
        "커버",
        "remix",
        "리믹스",
        "가요",
        "발라드",
        "힙합",
        "rap",
        "팝송",
        "타이틀곡",
        "title track",
    )
    if any(x in m for x in music_markers) and not wellness:
        return True

    if "음악" in m and not wellness:
        return True

    if ("오디오" in raw or " audio" in m) and not wellness and not explicit_wants_guided(message):
        return True

    play_verbs = ("틀어", "들려", "재생", "불러", "찾아", "검색")
    if any(v in raw for v in play_verbs) and not wellness and len(raw) >= 5:
        if explicit_wants_guided(message) and "오디오" in raw and len(raw) <= 18:
            return False
        return True

    return False


def wants_podcast(message: str | None) -> bool:
    if not message:
        return False
    if likely_music_search_request(message):
        return False
    m = message.lower()
    positive = (
        "팟캐스트",
        "podcast",
        "수면",
        "명상",
        "호흡",
        "잠",
        "asrm",
        "asmr",
    )
    if any(p in m for p in positive):
        return True
    negative_video = ("유튜브", "youtube", "영상", "video")
    if any(n in m for n in negative_video) and ("말고" in m or "싫" in m or "빼" in m):
        return True
    if explicit_wants_guided(message) and not wants_music_only_bgm(message):
        return True
    return False
