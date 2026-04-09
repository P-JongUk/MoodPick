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
    emotion_score: dict = Field(default_factory=dict)   # {"emotion": "불안", "intensity": 0.7}
    user_profile: Optional[dict] = None                 # cached after first fetch; reused by Recommender
    response: str = ""
    # Counselor may also override needs_recommendation based on session context

    # --- Content Recommender fills this ---
    recommended_content: Optional[dict] = None
    # Format: {"title": ..., "url": ..., "video_id": ..., "reason": ...}
