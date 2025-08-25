from __future__ import annotations
from dataclasses import dataclass
from typing import List

from ..config import Config


@dataclass
class UniverseItem:
	symbol: str
	reason: str


class UniverseSelector:
	def __init__(self, cfg: Config):
		self.cfg = cfg

	def build_universe(self) -> List[UniverseItem]:
		# Placeholder: returns whitelist with reason
		return [UniverseItem(symbol=s, reason="whitelist") for s in self.cfg.universe.whitelist]
