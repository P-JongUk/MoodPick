from pydantic import BaseModel
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from app.services.supabase_service import get_supabase_client
from supabase import Client
from datetime import datetime, timedelta


router = APIRouter(prefix="/emotion", tags=["emotion"])


class EmotionAnalysisRequest(BaseModel):
    user_input: str
    context: Optional[str] = None


class EmotionAnalysisResponse(BaseModel):
    emotion: str
    recommendations: List[str] = []


class EmotionRecordResponse(BaseModel):
    emotion: str
    recorded_at: str


@router.post("/analyze", response_model=EmotionAnalysisResponse)
async def analyze_emotion(
    payload: EmotionAnalysisRequest,
    supabase: Client = Depends(get_supabase_client)
):
    """사용자 입력 텍스트에서 감정 분석 (AI 제외 - 임시 분석)"""
    try:
        # 간단한 키워드 기반 감정 분석 (임시)
        keywords = {
            "스트레스": ("stress", 0.7),
            "우울": ("sadness", 0.8),
            "불안": ("anxiety", 0.7),
            "행복": ("happiness", 0.8),
            "분노": ("anger", 0.7),
            "피로": ("fatigue", 0.6),
            "외로움": ("loneliness", 0.7),
        }

        emotion = "neutral"
        intensity = 0.5
        
        for keyword, (emotion_type, intensity_val) in keywords.items():
            if keyword.lower() in payload.user_input.lower():
                emotion = emotion_type
                intensity = intensity_val
                break

        # 추천 활동 (감정별)
        recommendations_map = {
            "stress": ["명상", "산책", "운동"],
            "sadness": ["음악 감상", "친구와 통화", "취미 활동"],
            "anxiety": ["심호흡", "요가", "산책"],
            "happiness": ["즐겨찾기 영상", "친구들과 나누기"],
            "anger": ["심호흡", "운동", "명상"],
            "fatigue": ["충분한 수면", "휴식", "명상"],
            "loneliness": ["친구 연락", "커뮤니티 활동"],
            "neutral": ["일상 활동"],
        }

        recommendations = recommendations_map.get(emotion, ["활동"])

        return EmotionAnalysisResponse(
            emotion=emotion,
            recommendations=recommendations
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/records/{user_id}", response_model=List[dict])
async def get_emotion_records(
    user_id: str,
    days: int = 7,
    supabase: Client = Depends(get_supabase_client)
):
    """사용자의 감정 기록 조회 (최근 N일)"""
    try:
        days_ago = datetime.utcnow() - timedelta(days=days)

        sessions_result = supabase.table("counseling_sessions").select("id").eq(
            "user_id", user_id
        ).execute()

        session_rows = sessions_result.data or []
        if not session_rows:
            return []

        session_ids = [row["id"] for row in session_rows]

        responses_result = supabase.table("survey_responses").select("*").in_(
            "session_id", session_ids
        ).filter("created_at", "gte", days_ago.isoformat()).order(
            "created_at", desc=True
        ).execute()

        if responses_result.data:
            emotions = []
            for record in responses_result.data:
                emotions.append({
                    "question": record["question_key"],
                    "emoji": record["emoji_value"],
                    "score": record["score"],
                    "phase": record.get("phase"),
                    "recorded_at": record["created_at"],
                    "session_id": record["session_id"],
                })
            return emotions
        return []
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/summary/{user_id}")
async def get_emotion_summary(
    user_id: str,
    days: int = 7,
    supabase: Client = Depends(get_supabase_client)
):
    """사용자의 감정 요약 (최근 N일 평균)"""
    try:
        days_ago = datetime.utcnow() - timedelta(days=days)

        sessions_result = supabase.table("counseling_sessions").select("id").eq(
            "user_id", user_id
        ).execute()

        session_rows = sessions_result.data or []
        if not session_rows:
            return {
                "user_id": user_id,
                "average_score": 3.0,
                "trend": "stable",
                "total_sessions": 0
            }

        session_ids = [row["id"] for row in session_rows]

        responses_result = supabase.table("survey_responses").select("score").in_(
            "session_id", session_ids
        ).filter("created_at", "gte", days_ago.isoformat()).order(
            "created_at", desc=True
        ).execute()

        if not responses_result.data:
            return {
                "user_id": user_id,
                "average_score": 3.0,
                "trend": "stable",
                "total_sessions": len(session_ids),
                "total_responses": 0,
                "days_range": days
            }

        scores = [r["score"] for r in responses_result.data]
        avg_score = sum(scores) / len(scores) if scores else 3.0

        # 추이 판단 (최근 3개 vs 그 이전 3개)
        recent = scores[:3]
        earlier = scores[3:6]
        
        trend = "stable"
        if recent and earlier:
            recent_avg = sum(recent) / len(recent)
            earlier_avg = sum(earlier) / len(earlier)
            if recent_avg > earlier_avg + 0.5:
                trend = "improving"
            elif recent_avg < earlier_avg - 0.5:
                trend = "declining"

        return {
            "user_id": user_id,
            "average_score": round(avg_score, 2),
            "trend": trend,
            "total_sessions": len(session_ids),
            "total_responses": len(scores),
            "days_range": days
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/records")
async def get_emotion_records():
    return {
        "message": "감정 기록 조회 엔드포인트가 준비되었습니다.",
        "records": [],
        "status": "ok",
    }
