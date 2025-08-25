from __future__ import annotations

from typing import List, Dict, Any


def ema(values: List[float], period: int) -> List[float]:
	if period <= 0:
		raise ValueError("period must be > 0")
	out: List[float] = []
	k = 2.0 / (period + 1)
	prev = None
	for v in values:
		if prev is None:
			prev = v
		else:
			prev = v * k + prev * (1 - k)
		out.append(prev)
	return out


def rsi(closes: List[float], period: int = 14) -> List[float]:
	if period <= 0:
		raise ValueError("period must be > 0")
	gains: List[float] = [0.0]
	losses: List[float] = [0.0]
	for i in range(1, len(closes)):
		change = closes[i] - closes[i - 1]
		gains.append(max(change, 0.0))
		losses.append(max(-change, 0.0))
	avg_gain = sum(gains[:period]) / max(period, 1)
	avg_loss = sum(losses[:period]) / max(period, 1)
	result: List[float] = [50.0] * len(closes)
	for i in range(period, len(closes)):
		avg_gain = (avg_gain * (period - 1) + gains[i]) / period
		avg_loss = (avg_loss * (period - 1) + losses[i]) / period
		rs = (avg_gain / avg_loss) if avg_loss != 0 else float('inf')
		result[i] = 100 - (100 / (1 + rs))
	return result


def atr(bars: List[Dict[str, Any]], period: int = 14) -> List[float]:
	trs: List[float] = []
	for i, b in enumerate(bars):
		high = float(b["high"])
		low = float(b["low"])
		close_prev = float(bars[i - 1]["close"]) if i > 0 else float(b["close"]) 
		tr = max(
			high - low,
			abs(high - close_prev),
			abs(low - close_prev),
		)
		trs.append(tr)
	out: List[float] = []
	alpha = 1.0 / period
	prev = None
	for tr in trs:
		if prev is None:
			prev = tr
		else:
			prev = alpha * tr + (1 - alpha) * prev
		out.append(prev)
	return out