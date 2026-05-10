"""명상·오디오·팟캐스트 관련 사용자 문장 휴리스틱 (추천 분기 공용)."""

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


def likely_music_search_request(message: str | None) -> bool:
    """
    특정 곡·플레이리스트·일반 음악 검색으로 보이면 True → 팟캐스트(RSS) 스킵, YouTube 검색.
    웰니스(명상·수면 등) 맥락이 있으면 False.
    """
    if not message or not message.strip():
        return False
    raw = message.strip()
    m = raw.lower()

    # 영상 말고 오디오/팟캐스트 — 곡 검색이 아님
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

    # 「백아 첫사랑 오디오」처럼 곡+오디오 — 웰니스 가이드 오디오는 explicit_wants_guided로 구분
    if ("오디오" in raw or " audio" in m) and not wellness and not explicit_wants_guided(message):
        return True

    play_verbs = ("틀어", "들려", "재생", "불러", "찾아", "검색")
    if any(v in raw for v in play_verbs) and not wellness and len(raw) >= 5:
        # 짧은 「가이드 오디오 틀어줘」는 웰니스 — 긴 문장은 곡 제목+가이드 트랙 등
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
    positive = [
        "팟캐스트",
        "podcast",
        # 오디오/audio 단독은 곡 요청과 충돌 → 제거. 명상·수면·가이드 등과 함께 쓰이면 다른 키워드로 잡힘
        "수면",
        "명상",
        "호흡",
        "잠",
        "asrm",
        "asmr",
    ]
    if any(p.lower() in m for p in positive):
        return True
    negative_video = ["유튜브", "youtube", "영상", "video"]
    if any(n in m for n in negative_video) and ("말고" in m or "싫" in m or "빼" in m):
        return True
    # 「가이드로 틀어줘」만 있어도 오디오 가이드 경로 — 「가이드 말고」등은 wants_music_only가 우선
    if explicit_wants_guided(message) and not wants_music_only_bgm(message):
        return True
    return False
