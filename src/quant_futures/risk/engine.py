from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..data.metadata import MetaService, SymbolMeta


@dataclass
class RiskConfig:
	equity_usdt: float
	risk_per_trade_pct: float = 0.01
	liq_buffer_pct_min: float = 0.02
	atr_buffer_mult_entry: float = 3.0
	atr_buffer_mult_sl: float = 1.5
	max_portfolio_risk_pct: float = 0.03
	vol_class_leverage_caps: Dict[str, float] | None = None  # e.g., {"A": 15, "B": 6, "C": 3}


@dataclass
class PlannedTrade:
	symbol: str
	direction: str
	entry: float
	sl: float
	atr: float
	vol_class: str = "A"  # A/B/C per policy


@dataclass
class SizingResult:
	notional: float
	quantity: float
	effective_leverage: float
	applied_leverage_param: int
	passes_liq_buffer: bool
	reasons: List[str]


class RiskEngine:
	def __init__(self, meta_service: MetaService, config: RiskConfig) -> None:
		self.meta = meta_service
		self.cfg = config

	def _compute_exchange_liq_price(self, meta: SymbolMeta, direction: str, entry: float, leverage_param: int) -> Optional[float]:
		# Approximate: use maintenance margin ratio from first tier
		try:
			mmr = float(meta.maint_margin_tiers[0]["maintMarginRatio"]) if meta.maint_margin_tiers else 0.004
		except Exception:
			mmr = 0.004
		if direction == "long":
			return entry * (1 - 1.0 / leverage_param) * (1 - mmr)
		else:
			return entry * (1 + 1.0 / leverage_param) * (1 + mmr)

	def size_position(self, trade: PlannedTrade) -> SizingResult:
		meta = self.meta.symbol_meta(trade.symbol)
		R = self.cfg.equity_usdt * self.cfg.risk_per_trade_pct
		sl_dist = abs(trade.entry - trade.sl)
		if sl_dist <= 0:
			return SizingResult(0.0, 0.0, 0.0, 1, False, ["invalid_sl_distance"])
		notional = R / (sl_dist / trade.entry)  # R = notional * (sl_dist/entry)
		effective_lev = notional / max(self.cfg.equity_usdt, 1e-9)

		# cap leverage by vol class policy
		lev_cap = 100.0
		if self.cfg.vol_class_leverage_caps and trade.vol_class in self.cfg.vol_class_leverage_caps:
			lev_cap = float(self.cfg.vol_class_leverage_caps[trade.vol_class])
		if effective_lev > lev_cap:
			notional = lev_cap * self.cfg.equity_usdt
			effective_lev = lev_cap

		# bourse parameter: cannot exceed symbol max leverage
		applied_lev_param = min(int(effective_lev) if effective_lev >= 1 else 1, meta.max_leverage)

		# liquidation buffer checks
		liq_price = self._compute_exchange_liq_price(meta, trade.direction, trade.entry, applied_lev_param)
		passes, reasons = self._check_liq_buffer(trade, liq_price)

		# adjust by reducing leverage if fails
		while not passes and applied_lev_param > 1:
			applied_lev_param = max(1, applied_lev_param // 2)
			liq_price = self._compute_exchange_liq_price(meta, trade.direction, trade.entry, applied_lev_param)
			passes, reasons = self._check_liq_buffer(trade, liq_price)
		if not passes:
			# reduce notional
			notional *= 0.5
			effective_lev = notional / max(self.cfg.equity_usdt, 1e-9)
			if effective_lev < 1:
				applied_lev_param = 1
			passes, reasons = self._check_liq_buffer(trade, liq_price)

		qty = notional / trade.entry
		# round by step size
		step = meta.step_size or 0.001
		if step > 0:
			qty = (qty // step) * step

		return SizingResult(
			notional=notional,
			quantity=qty,
			effective_leverage=effective_lev,
			applied_leverage_param=applied_lev_param,
			passes_liq_buffer=passes,
			reasons=reasons,
		)

	def _check_liq_buffer(self, trade: PlannedTrade, liq_price: Optional[float]) -> tuple[bool, List[str]]:
		reasons: List[str] = []
		if liq_price is None:
			return False, ["no_liq_price"]
		entry = trade.entry
		atr = trade.atr
		Z = self.cfg.atr_buffer_mult_entry
		Y = self.cfg.atr_buffer_mult_sl
		min_pct = self.cfg.liq_buffer_pct_min
		if trade.direction == "long":
			dist_entry = (entry - liq_price) / entry
			dist_sl = (trade.sl - liq_price) / trade.sl if trade.sl > 0 else 0
		else:
			dist_entry = (liq_price - entry) / entry
			dist_sl = (liq_price - trade.sl) / trade.sl if trade.sl > 0 else 0
		cond1 = dist_entry >= max(Z * atr / entry, min_pct)
		cond2 = dist_sl >= Y * atr / max(trade.sl, 1e-9)
		if not cond1:
			reasons.append("entry_liq_buffer_fail")
		if not cond2:
			reasons.append("sl_liq_buffer_fail")
		return cond1 and cond2, reasons or ["ok"]