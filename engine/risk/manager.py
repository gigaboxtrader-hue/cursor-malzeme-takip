from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import math


@dataclass
class SizingResult:
	notional: float
	qty: float
	leverage_effective: float
	entry_price: float
	sl_price: float
	valid: bool
	reason: Optional[str] = None


class RiskManager:
	def __init__(self, cfg):
		self.cfg = cfg

	def compute_position(self, equity_usdt: float, entry_price: float, side: str, atr_value: float, tick_size: float, step_size: float) -> SizingResult:
		# SL distance = ATR cushion
		sl_buffer = max(self.cfg.risk.sl_atr_mult * atr_value, entry_price * 0.001)
		if side == 'LONG':
			sl_price = entry_price - sl_buffer
		else:
			sl_price = entry_price + sl_buffer

		risk_usdt = equity_usdt * self.cfg.risk.per_trade_risk_pct
		sl_distance = abs(entry_price - sl_price)
		if sl_distance <= 0:
			return SizingResult(0,0,0,entry_price,sl_price,False,"invalid sl distance")

		notional = risk_usdt / (sl_distance / entry_price)
		leverage_effective = notional / equity_usdt

		# Round quantity by step size
		qty = notional / entry_price
		if step_size > 0:
			qty = math.floor(qty / step_size) * step_size
		if qty <= 0:
			return SizingResult(0,0,0,entry_price,sl_price,False,"qty round to zero")

		return SizingResult(notional=qty*entry_price, qty=qty, leverage_effective=leverage_effective, entry_price=entry_price, sl_price=sl_price, valid=True)

	def validate_liquidation_buffer(self, entry_price: float, sl_price: float, liquidation_price: float, atr_value: float) -> tuple[bool, str | None]:
		# distance(entry, liq) ≥ max(Z×ATR, LiqBuffer%) and distance(SL, liq) ≥ Y×ATR
		Z = self.cfg.risk.liquidation_buffer_atr_mult
		pct = self.cfg.risk.liquidation_buffer_pct
		Y = max(1.5, self.cfg.risk.sl_atr_mult)

		dist_entry_liq = abs(entry_price - liquidation_price)
		dist_sl_liq = abs(sl_price - liquidation_price)
		req1 = dist_entry_liq >= max(Z * atr_value, pct * entry_price)
		req2 = dist_sl_liq >= Y * atr_value
		if not req1:
			return False, "entry-liq buffer fail"
		if not req2:
			return False, "sl-liq buffer fail"
		return True, None
