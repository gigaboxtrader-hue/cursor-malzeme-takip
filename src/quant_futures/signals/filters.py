from __future__ import annotations

from typing import Dict, Any


def extreme_move_filter(bar: Dict[str, Any], atr_value: float, k: float = 3.0) -> bool:
	body = abs(float(bar["close"]) - float(bar["open"]))
	return body <= k * atr_value


def volatility_ok(atr_pct: float, max_pct: float) -> bool:
	return atr_pct <= max_pct