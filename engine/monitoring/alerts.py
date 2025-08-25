from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class AlertConfig:
	telegram_token: Optional[str]
	telegram_chat_id: Optional[str]


class AlertService:
	def __init__(self, cfg: AlertConfig):
		self.cfg = cfg

	def info(self, msg: str) -> None:
		print(f"[INFO] {msg}")

	def warn(self, msg: str) -> None:
		print(f"[WARN] {msg}")

	def error(self, msg: str) -> None:
		print(f"[ERROR] {msg}")


class KillSwitch:
	def __init__(self, daily_dd_limit_pct: float = 0.02):
		self.daily_dd_limit_pct = daily_dd_limit_pct

	def check_and_trigger(self, daily_dd_pct: float) -> bool:
		if daily_dd_pct <= -abs(self.daily_dd_limit_pct):
			print("[KILL] Daily drawdown limit reached. Triggering killswitch.")
			return True
		return False
