from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Optional

_DEFAULT_CACHE_DIR = Path(os.environ.get("QF_CACHE_DIR", ".cache"))
_DEFAULT_CACHE_DIR.mkdir(parents=True, exist_ok=True)


class FileCache:
	def __init__(self, base_dir: Path | str = _DEFAULT_CACHE_DIR, default_ttl_sec: int = 300) -> None:
		self.base_dir = Path(base_dir)
		self.base_dir.mkdir(parents=True, exist_ok=True)
		self.default_ttl_sec = default_ttl_sec

	def _key_to_path(self, key: str) -> Path:
		hash_key = hashlib.sha256(key.encode("utf-8")).hexdigest()
		return self.base_dir / f"{hash_key}.json"

	def get(self, key: str) -> Optional[Any]:
		path = self._key_to_path(key)
		if not path.exists():
			return None
		try:
			with path.open("r", encoding="utf-8") as f:
				payload = json.load(f)
			exp = payload.get("_exp", 0)
			if exp and time.time() > exp:
				return None
			return payload.get("data")
		except Exception:
			return None

	def set(self, key: str, data: Any, ttl_sec: Optional[int] = None) -> None:
		path = self._key_to_path(key)
		payload = {"_exp": time.time() + (ttl_sec or self.default_ttl_sec), "data": data}
		with path.open("w", encoding="utf-8") as f:
			json.dump(payload, f)