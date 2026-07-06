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
    "weekly_report": {
        "title": "周末深度报告",
        "topic": "女性与个人成长",
        "keywords": ["女性", "个人成长", "职场", "健康", "心理", "教育", "家庭", "消费"],
        "source_sections": ["weekly_report_sources", "sources"],
        "candidate_items": 40,
        "max_items_per_source": 25,
        "max_items_per_direction_group": 40,
        "max_source_items": 24,
        "output_dir": "weekly_reports",
        "html_output_dir": "weekly_reports",
        "site_base_url": "https://wangzianna.github.io/daily-news-push/",
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
