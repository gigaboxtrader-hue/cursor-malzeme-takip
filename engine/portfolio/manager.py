from __future__ import annotations
from dataclasses import dataclass


@dataclass
class OpenPosition:
	symbol: str
	risk_pct: float


class PortfolioRisk:
	def __init__(self, total_risk_cap_pct: float):
		self.total_risk_cap_pct = total_risk_cap_pct

	def can_open(self, open_positions: list[OpenPosition], new_risk_pct: float) -> bool:
		total = sum(p.risk_pct for p in open_positions) + new_risk_pct
		return total <= self.total_risk_cap_pct
