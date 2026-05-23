"""
ai/tools/preference_map.py

onboarding_profile의 id 값을 한국어 라벨/지침으로 변환하는 단일 매핑 모듈.
counselor·content_recommender·user_taste가 공유.

분리 배경:
- counseling_tone(listen/advice): 상담 에이전트의 톤 가이드
- content_preference(music/video): 추천 에이전트의 콘텐츠 타입 선호
"""

CONTENT_PREFERENCE_LABELS: dict[str, str] = {
    "music": "음악",
    "video": "영상",
}

COUNSELING_TONE_LABELS: dict[str, str] = {
    "listen": "조용히 들어주기",
    "advice": "현실적인 조언",
}


def content_preference_to_korean(ids: list[str]) -> str:
    """['music', 'video'] → '음악, 영상'. 비어있거나 알 수 없는 id는 제외."""
    return ", ".join(
        CONTENT_PREFERENCE_LABELS[i] for i in ids if i in CONTENT_PREFERENCE_LABELS
    )


def counseling_tone_guidance(ids: list[str]) -> str:
    """상담 에이전트 system message에 주입할 톤 가이드 블록.

    빈 배열이면 빈 문자열 반환(블록 미주입 → 기본 톤 유지).
    """
    has_listen = "listen" in ids
    has_advice = "advice" in ids
    if not has_listen and not has_advice:
        return ""

    header = "\n\n### [Module 1.5: Tone Preference]\n"
    if has_listen and has_advice:
        body = (
            "- 사용자는 **공감·경청**과 **현실적 조언** 모두를 어느 정도 원합니다. "
            "기본은 반영적 경청·감정 수용이며, 사용자가 조언을 원하는 신호가 보일 때만 "
            "구체적·현실적 제안을 1가지 덧붙입니다."
        )
    elif has_listen:
        body = (
            "- 사용자가 **조용히 들어주는 방식**을 선호합니다. "
            "해결책·조언보다 반영적 경청과 감정 수용을 우선하세요. "
            "질문은 답을 유도하기보다 사용자가 더 말하고 싶도록 여는 형태로 합니다."
        )
    else:  # advice only
        body = (
            "- 사용자가 **현실적인 조언**을 선호합니다. "
            "충분히 공감한 뒤, 다음 한 걸음에 해당하는 구체적·현실적 제안을 1가지 "
            "포함하세요(강요 X, 선택지 제시 형태)."
        )
    return header + body
