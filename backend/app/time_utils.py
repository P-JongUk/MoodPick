"""로컬 날짜·타임존 경계 (UTC) 계산."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


def local_date_in_timezone(timezone_name: str) -> date:
    return datetime.now(ZoneInfo(timezone_name)).date()


def parse_iso_date(date_str: str) -> date:
    y, m, d = date_str.split("-")
    return date(int(y), int(m), int(d))


def local_day_to_utc_range(timezone_name: str, d: date) -> tuple[datetime, datetime]:
    """해당 로컬 날짜의 [start, end) in UTC (end exclusive)."""
    tz = ZoneInfo(timezone_name)
    start_local = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    utc = ZoneInfo("UTC")
    return start_local.astimezone(utc), end_local.astimezone(utc)
