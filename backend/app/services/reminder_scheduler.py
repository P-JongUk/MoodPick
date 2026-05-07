import asyncio
import logging

from app.config import get_settings
from app.routers.reminder import dispatch_due_reminders
from app.services.supabase_service import get_supabase_client


logger = logging.getLogger(__name__)


async def reminder_scheduler_loop(stop_event: asyncio.Event) -> None:
    settings = get_settings()
    interval = settings.reminder_scheduler_interval_seconds

    logger.info("Reminder scheduler started (interval=%ss)", interval)

    # Startup delay to avoid noisy logs during boot sequence.
    await asyncio.sleep(3)

    while not stop_event.is_set():
        try:
            supabase = get_supabase_client()
            result = dispatch_due_reminders(supabase, source="auto-scheduler")
            if result.get("due_count", 0) > 0:
                logger.info(
                    "Reminder dispatch checked=%s due=%s sent=%s failed=%s",
                    result.get("checked_at"),
                    result.get("due_count"),
                    result.get("sent_count"),
                    result.get("failed_count"),
                )
        except Exception as exc:
            logger.exception("Reminder scheduler iteration failed: %s", exc)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue

    logger.info("Reminder scheduler stopped")
