from pydantic import BaseModel
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from app.services.supabase_service import get_supabase_client
from supabase import Client
from datetime import datetime, timezone


router = APIRouter(prefix="/survey", tags=["survey"])

# 사전/사후 문진 동일 문항 세트
SURVEY_QUESTIONS = [
    {
        "key": "mood_general",
        "question": "현재 전체적인 기분은 어떤가요?",
        "type": "emoji",
        "emoji_options": ["great", "good", "neutral", "low", "bad"]
    },
    {
        "key": "energy_level",
        "question": "현재 에너지 수준은?",
        "type": "emoji",
        "emoji_options": ["great", "good", "neutral", "low", "bad"]
    },
    {
        "key": "stress_level",
        "question": "스트레스 정도는?",
        "type": "emoji",
        "emoji_options": ["bad", "low", "neutral", "good", "great"]
    }
]

MOOD_EMOJI_MAP = {
    "great": 5,
    "good": 4,
    "neutral": 3,
    "low": 2,
    "bad": 1,
}


class SurveyQuestion(BaseModel):
    key: str
    question: str
    type: str
    emoji_options: List[str]


class SurveyResponseRequest(BaseModel):
    session_id: str
    phase: str  # "pre" or "post"
    question_key: str
    emoji_value: str


class SurveyDeltaResponse(BaseModel):
    pre_scores: dict
    post_scores: dict
    delta: dict
    improved: bool


@router.get("/questions", response_model=List[SurveyQuestion])
async def get_survey_questions():
    """사전/사후 문진 질문 조회"""
    return SURVEY_QUESTIONS


@router.post("/submit")
async def submit_survey_response(
    payload: SurveyResponseRequest,
    supabase: Client = Depends(get_supabase_client)
):
    """문진 응답 저장"""
    try:
        # emoji_value -> score 매핑
        score = MOOD_EMOJI_MAP.get(payload.emoji_value, 3)
        
        result = supabase.table("survey_responses").insert({
            "session_id": payload.session_id,
            "phase": payload.phase,
            "question_key": payload.question_key,
            "emoji_value": payload.emoji_value,
            "score": score,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()

        if result.data and len(result.data) > 0:
            return {
                "status": "success",
                "response_id": result.data[0]["id"],
                "score": score
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save survey response"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/delta/{session_id}", response_model=Optional[SurveyDeltaResponse])
async def get_survey_delta(
    session_id: str,
    supabase: Client = Depends(get_supabase_client)
):
    """세션의 사전/사후 문진 감정 변화(Delta) 조회"""
    try:
        result = supabase.table("survey_responses").select("*").eq(
            "session_id", session_id
        ).execute()

        if not result.data:
            return None

        # phase별로 응답 분류
        pre_responses = [r for r in result.data if r["phase"] == "pre"]
        post_responses = [r for r in result.data if r["phase"] == "post"]

        # 점수 집계
        pre_scores = {}
        for response in pre_responses:
            pre_scores[response["question_key"]] = response["score"]

        post_scores = {}
        for response in post_responses:
            post_scores[response["question_key"]] = response["score"]

        # Delta 계산
        delta = {}
        for key in pre_scores.keys():
            if key in post_scores:
                delta[key] = post_scores[key] - pre_scores[key]

        # 전체적으로 개선되었는지 판단
        avg_delta = sum(delta.values()) / len(delta) if delta else 0
        improved = avg_delta > 0

        return SurveyDeltaResponse(
            pre_scores=pre_scores,
            post_scores=post_scores,
            delta=delta,
            improved=improved
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/history/{user_id}")
async def get_survey_history(
    user_id: str,
    limit: int = 10,
    supabase: Client = Depends(get_supabase_client)
):
    """사용자의 문진 기록 조회 (최근 10개)"""
    try:
        sessions_result = supabase.table("counseling_sessions").select(
            "id, started_at"
        ).eq("user_id", user_id).order("started_at", desc=True).execute()

        session_rows = sessions_result.data or []
        if not session_rows:
            return {
                "status": "success",
                "data": []
            }

        session_ids = [row["id"] for row in session_rows]
        started_at_by_session = {row["id"]: row.get("started_at") for row in session_rows}

        responses_result = supabase.table("survey_responses").select("*").in_(
            "session_id", session_ids
        ).order("created_at", desc=True).limit(limit).execute()

        response_rows = responses_result.data or []
        enriched_rows = [
            {
                **row,
                "session_started_at": started_at_by_session.get(row.get("session_id")),
            }
            for row in response_rows
        ]

        return {
            "status": "success",
            "data": enriched_rows
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


def _mood_general_pre_post(
    supabase: Client, session_ids: list[str]
) -> dict[str, tuple[Optional[str], Optional[str]]]:
    """session_id -> (pre_emoji, post_emoji) for mood_general only."""
    if not session_ids:
        return {}
    result = supabase.table("survey_responses").select(
        "session_id, phase, emoji_value, question_key"
    ).in_("session_id", session_ids).execute()
    rows = result.data or []
    out: dict[str, tuple[Optional[str], Optional[str]]] = {
        sid: (None, None) for sid in session_ids
    }
    for row in rows:
        if row.get("question_key") != "mood_general":
            continue
        sid = row["session_id"]
        if sid not in out:
            continue
        pre, post = out[sid]
        if row["phase"] == "pre":
            pre = row.get("emoji_value")
        elif row["phase"] == "post":
            post = row.get("emoji_value")
        out[sid] = (pre, post)
    return out
