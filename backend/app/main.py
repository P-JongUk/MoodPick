import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.auth import router as auth_router
from app.routers.session import router as session_router
from app.routers.counseling import router as counseling_router
from app.routers.emotion import router as emotion_router
from app.routers.survey import router as survey_router
from app.routers.content import router as content_router
from app.routers.user import router as user_router
from app.routers.rag import router as rag_router
from app.routers.reminder import router as reminder_router
from app.config import get_settings
from app.services.reminder_scheduler import reminder_scheduler_loop


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
app.include_router(rag_router)
app.include_router(reminder_router)


_reminder_stop_event: asyncio.Event | None = None
_reminder_task: asyncio.Task | None = None


@app.on_event("startup")
async def startup_event() -> None:
    global _reminder_stop_event, _reminder_task

    settings = get_settings()
    if not settings.reminder_scheduler_enabled:
        return

    _reminder_stop_event = asyncio.Event()
    _reminder_task = asyncio.create_task(reminder_scheduler_loop(_reminder_stop_event))


@app.on_event("shutdown")
async def shutdown_event() -> None:
    global _reminder_stop_event, _reminder_task

    if _reminder_stop_event is None or _reminder_task is None:
        return

    _reminder_stop_event.set()
    await _reminder_task
    _reminder_stop_event = None
    _reminder_task = None


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