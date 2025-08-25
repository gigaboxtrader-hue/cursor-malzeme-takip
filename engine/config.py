from __future__ import annotations
import yaml
from pydantic import BaseModel
from typing import Any, Dict


class AppConfig(BaseModel):
	mode: str
	log_level: str
	data_dir: str


class ExchangeConfig(BaseModel):
	name: str
	base_url: str
	ws_url: str
	maker_fee_bps: float
	taker_fee_bps: float


class RiskConfig(BaseModel):
	per_trade_risk_pct: float
	portfolio_risk_cap_pct: float
	liquidation_buffer_atr_mult: float
	liquidation_buffer_pct: float
	sl_atr_mult: float
	rr_min: float
	trailing_atr_mult: float
	use_isolated_margin: bool


class LeveragePolicy(BaseModel):
	class_caps: Dict[str, int]
	regime_adjustments: Dict[str, float]


class UniverseConfig(BaseModel):
	whitelist: list[str]
	min_notional_30d_usdt: int
	min_notional_90d_usdt: int
	max_spread_bps: float
	min_top_of_book_usdt: int


class BacktestConfig(BaseModel):
	timeframe: str
	initial_equity_usdt: float
	lat_ms_mean: int
	lat_ms_jitter: int
	slippage_mode: str
	trigger_price: str
	funding_enabled: bool
	fees_enabled: bool
	partial_fills: bool


class OptimizerConfig(BaseModel):
	sharpe_mdd_penalty: Dict[str, float]
	random_trials: int
	walkforward: Dict[str, int]


class AlertsConfig(BaseModel):
	telegram_token: str | None
	telegram_chat_id: str | None


class Config(BaseModel):
	app: AppConfig
	exchange: ExchangeConfig
	risk: RiskConfig
	leverage_policy: LeveragePolicy
	universe: UniverseConfig
	backtest: BacktestConfig
	optimizer: OptimizerConfig
	alerts: AlertsConfig


def load_config(path: str) -> Config:
	with open(path, "r", encoding="utf-8") as f:
		data: Dict[str, Any] = yaml.safe_load(f)
	return Config(**data)
