"""The current date in the configured business time zone (Asia/Kolkata by default).

Routes depend on ``get_today`` rather than calling ``date.today()`` so that date
rules use the firm's calendar, not the server's, and tests can fix the date.
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import Depends

from lexflow.config import Settings, get_settings


def get_today(settings: Settings = Depends(get_settings)) -> date:
    return datetime.now(settings.tz).date()
