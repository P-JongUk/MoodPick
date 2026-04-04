from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.auth import router as auth_router
from app.routers.session import router as session_router
from app.routers.counseling import router as counseling_router
from app.routers.emotion import router as emotion_router
from app.routers.survey import router as survey_router
from app.routers.content import router as content_router
from app.routers.user import router as user_router


app = FastAPI(title="MoodPick Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(session_router)
app.include_router(counseling_router)
app.include_router(emotion_router)
app.include_router(survey_router)
app.include_router(content_router)
app.include_router(user_router)


@app.get("/")
async def root():
    return {
        "message": "MoodPick 백엔드가 실행 중입니다.",
        "status": "ok",
    }


@app.get("/health")
async def health_check():
    return {
        "message": "healthy",
        "status": "ok",
    }