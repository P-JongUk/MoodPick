from fastapi import APIRouter


router = APIRouter(prefix="/user", tags=["user"])


@router.get("/profile")
async def get_user_profile():
    return {
        "message": "사용자 프로필 엔드포인트가 준비되었습니다.",
        "status": "ok",
    }
