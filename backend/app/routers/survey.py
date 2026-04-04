from pydantic import BaseModel
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from app.services.supabase_service import get_supabase_client
from supabase import Client
from datetime import datetime


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
            "created_at": datetime.utcnow().isoformat(),
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
        result = supabase.table("survey_responses").select(
            "*, counseling_sessions(id, started_at)"
        ).eq("counseling_sessions.user_id", user_id).order(
            "created_at", desc=True
        ).limit(limit).execute()

        return {
            "status": "success",
            "data": result.data or []
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
