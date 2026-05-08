from pydantic import BaseModel, Field
from typing import Optional


class CounselingState(BaseModel):
    """
    3-agent pipeline shared state.
    Each agent reads from and writes to this object.
    """

    # --- Input (always populated before pipeline starts) ---
    user_id: str
    session_id: str
    message: str                                        # current user message

    # Multi-turn conversation history (injected by the API endpoint)
    # Format: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    messages: list[dict] = Field(default_factory=list)

    # --- Orchestrator fills these ---
    is_crisis: bool = False
    intent: str = "상담"                                # "상담" | "추천" | "잡담"
    needs_recommendation: bool = False

    # --- Counselor fills these ---
    rag_context: list = Field(default_factory=list)
    emotion_score: dict = Field(default_factory=dict)
    # 형식:
    # {
    #   "emotion": "불안",                    # 24개 기준 감정 중 하나 (get_nearest_emotion 결과)
    #   "valence": -0.5,                      # -1.0~1.0
    #   "arousal":  0.5,                      # -1.0~1.0
    #   "intensity": 0.50,                    # 0.0~1.0, "감정 케어 시급도"
    #                                         #   = min(1, max(0, -V) * 0.6 + |A| * 0.4)
    #                                         #   counselor._build_emotion_score()에서 즉석 계산
    #                                         #   ※ va_radius (EMOTION_VA_MAP confidence_radius)와 다른 개념
    #   "emotion_description": "직장 스트레스와 자책감으로...",  # 임베딩 쿼리용 서술문
    # }
    user_profile: Optional[dict] = None                 # cached after first fetch; reused by Recommender
    response: str = ""
    # Counselor may also override needs_recommendation based on session context

    # --- Content Recommender fills this ---
    recommended_content: Optional[dict] = None
    # Format: {"title": ..., "url": ..., "video_id": ..., "reason": ...}
