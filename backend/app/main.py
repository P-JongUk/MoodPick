import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_cors_origins, get_settings

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

from app.routers.session import router as session_router
from app.routers.counseling import router as counseling_router
from app.routers.emotion import router as emotion_router
from app.routers.survey import router as survey_router
from app.routers.content import router as content_router
from app.routers.user import router as user_router
from app.routers.rag import router as rag_router
from app.routers.admin import router as admin_router
from ai.clients import close_clients


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ = app
    settings = get_settings()
    reminder_stop_event: asyncio.Event | None = None
    reminder_task: asyncio.Task | None = None

    if settings.reminder_feature_enabled and settings.reminder_scheduler_enabled:
        from app.services.reminder_scheduler import reminder_scheduler_loop

        reminder_stop_event = asyncio.Event()
        reminder_task = asyncio.create_task(reminder_scheduler_loop(reminder_stop_event))

    try:
        yield
    finally:
        if reminder_stop_event is not None and reminder_task is not None:
            reminder_stop_event.set()
            await reminder_task
        await close_clients()


app = FastAPI(title="MoodPick Backend", version="0.1.0", lifespan=lifespan)

allowed_origins = get_cors_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(session_router)
app.include_router(counseling_router)
app.include_router(emotion_router)
app.include_router(survey_router)
app.include_router(content_router)
app.include_router(user_router)
app.include_router(rag_router)
app.include_router(admin_router)

if settings.reminder_feature_enabled:
    from app.routers.reminder import router as reminder_router

    app.include_router(reminder_router)


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
