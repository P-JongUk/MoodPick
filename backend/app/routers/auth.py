from pydantic import BaseModel, EmailStr
from fastapi import APIRouter


router = APIRouter(prefix="/auth", tags=["auth"])


class AuthRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/register")
async def register_user(payload: AuthRequest):
    return {
        "message": "회원가입 엔드포인트가 준비되었습니다.",
        "email": payload.email,
        "status": "ok",
    }


@router.post("/login")
async def login_user(payload: AuthRequest):
    return {
        "message": "로그인 엔드포인트가 준비되었습니다.",
        "email": payload.email,
        "status": "ok",
    }


@router.get("/me")
async def get_current_user():
    return {
        "message": "현재 사용자 정보 엔드포인트가 준비되었습니다.",
        "status": "ok",
    }
