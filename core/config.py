"""
Configuración persistente — guarda ajustes de UI en un JSON local.
"""

import json
import os

_CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".fileforge_config.json")
_cache: dict = {}


def _load() -> dict:
    global _cache
    if _cache:
        return _cache
    try:
        with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
            _cache = json.load(f)
    except Exception:
        _cache = {}
    return _cache


def _save(data: dict):
    try:
        with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def load_config(key: str, default=None):
    return _load().get(key, default)


def save_config(key: str, value):
    data = _load()
    data[key] = value
    _cache[key] = value
    _save(data)
