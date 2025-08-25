from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Tuple

_INTERVAL_MAP = {
	"1m": timedelta(minutes=1),
	"3m": timedelta(minutes=3),
	"5m": timedelta(minutes=5),
	"15m": timedelta(minutes=15),
	"30m": timedelta(minutes=30),
	"1h": timedelta(hours=1),
	"2h": timedelta(hours=2),
	"4h": timedelta(hours=4),
	"6h": timedelta(hours=6),
	"8h": timedelta(hours=8),
	"12h": timedelta(hours=12),
	"1d": timedelta(days=1),
	"3d": timedelta(days=3),
}


def interval_to_timedelta(interval: str) -> timedelta:
	if interval not in _INTERVAL_MAP:
		raise ValueError(f"Unsupported interval: {interval}")
	return _INTERVAL_MAP[interval]


def now_utc() -> datetime:
	return datetime.now(timezone.utc)


def time_range_utc(days: int | None = None, hours: int | None = None) -> Tuple[datetime, datetime]:
	end_ts = now_utc()
	delta = timedelta(days=days or 0, hours=hours or 0)
	start_ts = end_ts - delta
	return start_ts, end_ts