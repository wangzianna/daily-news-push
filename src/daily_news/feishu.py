from __future__ import annotations

import os

import requests


def push_to_feishu(markdown: str, title: str, timeout: int = 20) -> None:
    webhook = os.environ.get("FEISHU_WEBHOOK_URL")
    if not webhook:
        raise RuntimeError("缺少 FEISHU_WEBHOOK_URL 环境变量")

    payload = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True, "enable_forward": True},
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": "blue",
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": markdown[:30000],
                }
            ],
        },
    }
    response = requests.post(webhook, json=payload, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    if data.get("code", 0) != 0:
        raise RuntimeError(f"飞书推送失败: {data}")
