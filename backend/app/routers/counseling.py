from pydantic import BaseModel
from fastapi import APIRouter


router = APIRouter(prefix="/counseling", tags=["counseling"])


class CounselingMessageRequest(BaseModel):
    user_id: str
    message: str


@router.post("/message")
async def send_counseling_message(payload: CounselingMessageRequest):
    return {
        "message": "상담 응답 엔드포인트가 준비되었습니다.",
        "user_id": payload.user_id,
        "echo": payload.message,
        "status": "ok",
    }
