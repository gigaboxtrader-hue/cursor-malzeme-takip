from __future__ import annotations

import datetime as _dt
from typing import Optional


def parse_date_yyyy_mm_dd(value: str) -> Optional[_dt.date]:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return _dt.datetime.strptime(value, "%Y-%m-%d").date()
    except Exception:
        return None

