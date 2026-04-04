from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter(prefix="/emotion", tags=["emotion"])


class EmotionAnalyzeRequest(BaseModel):
    text: str


@router.post("/analyze")
async def analyze_emotion(payload: EmotionAnalyzeRequest):
    return {
        "message": "감정 분석 엔드포인트가 준비되었습니다.",
        "text": payload.text,
        "emotion": "neutral",
        "score": 0.5,
        "status": "ok",
    }


@router.get("/records")
async def get_emotion_records():
    return {
        "message": "감정 기록 조회 엔드포인트가 준비되었습니다.",
        "records": [],
        "status": "ok",
    }
