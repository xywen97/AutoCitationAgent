from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Optional


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _cache_path(cache_dir: str, key: str) -> str:
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"{_hash_key(key)}.json")


def cache_get(cache_dir: str, key: str) -> Optional[Any]:
    path = _cache_path(cache_dir, key)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def cache_set(cache_dir: str, key: str, value: Any) -> None:
    path = _cache_path(cache_dir, key)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=True, indent=2)
    except OSError:
        return
