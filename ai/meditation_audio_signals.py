"""오디오·음악 세부 신호 휴리스틱.

라우팅(audio/video/music 분류)은 Orchestrator의 `content_format`이 담당한다.
이 모듈은 LLM이 잡기 어려운 미세 신호만 다룬다:
- `wants_music_only_bgm`: "말 없이/인스트루멘탈/BGM" 등 보컬·내레이션 없는 음악만
  원하는지. 검색 쿼리에 인스트루멘탈 강조 키워드 추가용 + 클라리피 답변 파싱용.
- `explicit_wants_guided`: "가이드/안내" 등 가이드형 명시. 클라리피 답변 파싱용.
- `is_video_content` / `is_audio_content` / `is_music_content`: content_format
  비교 헬퍼.
"""


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
