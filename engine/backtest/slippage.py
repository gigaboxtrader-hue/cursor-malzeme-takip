from __future__ import annotations


def compute_slippage_bps(mode: str, spread_bps: float, volatility_bps: float) -> float:
	"""Very simple slippage model: hybrid adds a fraction of volatility to spread."""
	mode = (mode or "hybrid").lower()
	if mode == "none":
		return 0.0
	if mode == "deterministic":
		return max(spread_bps, 0.0)
	if mode == "stochastic":
		return max(spread_bps * 0.5 + volatility_bps * 0.5, 0.0)
	# hybrid
	return max(spread_bps + 0.25 * volatility_bps, 0.0)
