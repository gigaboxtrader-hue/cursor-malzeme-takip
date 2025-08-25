from __future__ import annotations
from ..config import Config


class LiveExecutor:
	def __init__(self, cfg: Config):
		self.cfg = cfg

	def run(self) -> None:
		# Stub: live/shadow pipeline to be implemented in Kart H
		print("[LiveExecutor] Starting live/shadow mode (stub)")
