from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

BINANCE_FAPI_BASE = os.environ.get("BINANCE_FAPI_BASE", "https://fapi.binance.com")


class BinanceAPIError(Exception):
	pass


class BinanceRestrictedLocationError(BinanceAPIError):
	pass


class BinancePublicClient:
	def __init__(self, base_url: str = BINANCE_FAPI_BASE, timeout_sec: int = 10) -> None:
		self.base_url = base_url.rstrip("/")
		self.session = requests.Session()
		self.timeout_sec = timeout_sec

	@retry(reraise=True,
		   stop=stop_after_attempt(5),
		   wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
		   retry=retry_if_exception_type((requests.RequestException, BinanceAPIError)))
	def get(self, path: str, params: Optional[Dict[str, Any]] = None, weight: int = 1) -> Any:
		url = f"{self.base_url}{path}"
		resp = self.session.get(url, params=params or {}, timeout=self.timeout_sec)
		if resp.status_code == 451:
			raise BinanceRestrictedLocationError(f"HTTP 451: {resp.text}")
		if resp.status_code != 200:
			raise BinanceAPIError(f"HTTP {resp.status_code}: {resp.text}")
		try:
			return resp.json()
		except ValueError as e:
			raise BinanceAPIError(f"Invalid JSON: {e}")

	def server_time(self) -> int:
		data = self.get("/fapi/v1/time")
		return int(data.get("serverTime"))