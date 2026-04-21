"""Файл настроек UI (~/.config/linear-notifier/config.json)."""

import json
import os
from typing import Any, Dict

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "linear-notifier")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")


def _defaults() -> Dict[str, Any]:
    return {"language": "ru"}


def load_config() -> Dict[str, Any]:
    cfg = _defaults()
    if not os.path.isfile(CONFIG_PATH):
        return cfg
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "language" in data:
            cfg["language"] = str(data["language"])
        return cfg
    except Exception:
        return _defaults()


def save_config(partial: Dict[str, Any]) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    cfg = load_config()
    cfg.update(partial)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
