from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .indicators import atr, ema
from .filters import extreme_move_filter


@dataclass
class EntrySignal:
	index: int
	direction: str  # "long" or "short"
	trigger_price: float
	entry_type: str  # "limit" or "market"
	pullback_to: Optional[float]
	atr: float


@dataclass
class StrategyParams:
	atr_period: int = 14
	ema_period: int = 20
	atr_max_pct: float = 0.03
	body_k_atr: float = 3.0
	confirm_pct: float = 0.003  # 0.3%
	pullback_pct: float = 0.002  # 0.2%
	allow_market_on_slippage: bool = False
	max_slippage_pct: float = 0.001


class StrategyEngine:
	def generate_signals(self, bars: List[Dict[str, Any]], params: StrategyParams) -> List[EntrySignal]:
		if not bars:
			return []
		closes = [float(b["close"]) for b in bars]
		emas = ema(closes, params.ema_period)
		atrs = atr(bars, params.atr_period)
		out: List[EntrySignal] = []
		for i in range(2, len(bars)):
			bar = bars[i]
			atr_val = atrs[i]
			if atr_val <= 0:
				continue
			atr_pct = atr_val / max(1e-8, float(bar["close"]))
			if atr_pct > params.atr_max_pct:
				continue
			if not extreme_move_filter(bar, atr_val, k=params.body_k_atr):
				continue
			# Breakout: close > previous high and above EMA
			prev_high = float(bars[i - 1]["high"]) 
			prev_low = float(bars[i - 1]["low"]) 
			price = float(bar["close"]) 
			ema_val = emas[i]
			if price > prev_high and price > ema_val:
				confirm_level = prev_high * (1 + params.confirm_pct)
				if price >= confirm_level:
					pullback_to = ema_val * (1 + params.pullback_pct)
					out.append(EntrySignal(index=i, direction="long", trigger_price=price, entry_type="limit", pullback_to=pullback_to, atr=atr_val))
			elif price < prev_low and price < ema_val:
				confirm_level = prev_low * (1 - params.confirm_pct)
				if price <= confirm_level:
					pullback_to = ema_val * (1 - params.pullback_pct)
					out.append(EntrySignal(index=i, direction="short", trigger_price=price, entry_type="limit", pullback_to=pullback_to, atr=atr_val))
		return out