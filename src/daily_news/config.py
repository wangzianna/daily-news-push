from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG: dict[str, Any] = {
    "app": {
        "timezone": "Asia/Shanghai",
        "max_items_per_source": 15,
        "max_items_per_direction_group": 3,
        "max_items_total": 12,
        "fetch_timeout_seconds": 20,
        "user_agent": "DailyNewsPush/1.0",
    },
    "llm": {
        "provider": "deepseek",
        "base_url": "https://api.deepseek.com",
        "api_key_env": "DEEPSEEK_API_KEY",
        "model": "deepseek-v4-flash",
        "temperature": 0.2,
    },
    "report": {
        "title": "每日资讯日报",
        "output_dir": "reports",
    },
    "feishu": {
        "enabled": True,
    },
}


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        return DEFAULT_CONFIG
    with config_path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    return deep_merge(DEFAULT_CONFIG, data)
