from __future__ import annotations
from datetime import datetime, timezone
from dateutil import parser


def parse_utc(dt: str | datetime) -> datetime:
	if isinstance(dt, datetime):
		return dt.astimezone(timezone.utc)
	return parser.parse(dt).astimezone(timezone.utc)


def now_utc() -> datetime:
	return datetime.now(timezone.utc)
