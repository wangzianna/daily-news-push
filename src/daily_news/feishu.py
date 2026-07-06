from __future__ import annotations

import os

import requests

from .models import NewsItem
from .report import build_meta_line, format_datetime, group_by_category


def push_to_feishu(
    title: str,
    summary: str,
    items: list[NewsItem],
    timezone_name: str,
    errors: dict[str, str] | None = None,
    timeout: int = 20,
) -> None:
    webhook = os.environ.get("FEISHU_WEBHOOK_URL")
    if not webhook:
        raise RuntimeError("缺少 FEISHU_WEBHOOK_URL 环境变量")

    card_title = f"{title} · {len(items)} 条精选"
    payload = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True, "enable_forward": True},
            "header": {
                "title": {"tag": "plain_text", "content": card_title},
                "template": "blue",
            },
            "elements": build_card_elements(summary, items, timezone_name, errors),
        },
    }
    response = requests.post(webhook, json=payload, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    if data.get("code", 0) != 0:
        raise RuntimeError(f"飞书推送失败: {data}")


def push_deep_report_to_feishu(
    title: str,
    topic: str,
    report_markdown: str,
    source_items: list[NewsItem],
    timezone_name: str,
    errors: dict[str, str] | None = None,
    timeout: int = 20,
) -> None:
    webhook = os.environ.get("FEISHU_WEBHOOK_URL")
    if not webhook:
        raise RuntimeError("缺少 FEISHU_WEBHOOK_URL 环境变量")

    payload = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True, "enable_forward": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"{title} · {topic}"},
                "template": "purple",
            },
            "elements": build_deep_report_elements(
                report_markdown,
                source_items,
                timezone_name,
                errors,
            ),
        },
    }
    response = requests.post(webhook, json=payload, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    if data.get("code", 0) != 0:
        raise RuntimeError(f"飞书推送失败: {data}")


def build_card_elements(
    summary: str,
    items: list[NewsItem],
    timezone_name: str,
    errors: dict[str, str] | None = None,
) -> list[dict]:
    elements: list[dict] = [
        markdown_div("**今日简报**\n" + trim(summary.strip(), 5000)),
        {"tag": "hr"},
    ]

    if not items:
        elements.append(markdown_div("暂无可推送资讯。"))
        return elements

    for category, category_items in group_by_category(items).items():
        elements.append(markdown_div(f"**{category}**"))
        for item in category_items:
            elements.extend(build_item_elements(item, timezone_name))
        elements.append({"tag": "hr"})

    if errors:
        error_lines = [f"- `{source_id}`：{trim(error, 120)}" for source_id, error in errors.items()]
        elements.append(markdown_div("**抓取异常**\n" + "\n".join(error_lines)))

    return elements[:80]


def build_deep_report_elements(
    report_markdown: str,
    source_items: list[NewsItem],
    timezone_name: str,
    errors: dict[str, str] | None = None,
) -> list[dict]:
    elements: list[dict] = []
    sections = split_markdown_sections(report_markdown)
    if not sections:
        elements.append(markdown_div(trim(report_markdown, 6000)))
    else:
        for heading, content in sections:
            elements.append(markdown_div(f"**{escape_markdown(heading)}**\n{trim(content.strip(), 4500)}"))
            elements.append({"tag": "hr"})

    if source_items:
        elements.append(markdown_div("**关键原文**"))
        for item in source_items[:8]:
            elements.append(
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": trim(item.title, 30),
                            },
                            "url": item.link,
                            "type": "default",
                            "value": {
                                "source": item.source,
                                "published_at": format_datetime(item.published_at, timezone_name),
                            },
                        }
                    ],
                }
            )

    if errors:
        error_lines = [f"- `{source_id}`：{trim(error, 120)}" for source_id, error in errors.items()]
        elements.append(markdown_div("**抓取异常**\n" + "\n".join(error_lines)))

    return elements[:80]


def build_item_elements(item: NewsItem, timezone_name: str) -> list[dict]:
    type_tags = []
    if item.ai_type:
        type_tags.append(f"AI：{item.ai_type}")
    if item.evidence_type:
        type_tags.append(f"证据：{item.evidence_type}")
    if item.penalty_labels:
        type_tags.append("已降权")

    tag_line = " ｜ ".join(type_tags)
    meta = build_meta_line(item, timezone_name)
    content_lines = [
        f"**{escape_markdown(item.title)}**",
        f"{escape_markdown(meta)}",
    ]
    if tag_line:
        content_lines.append(f"`{escape_markdown(tag_line)}`")
    content_lines.append(f"摘要：{escape_markdown(trim(item.summary or '暂无摘要', 220))}")

    return [
        markdown_div("\n".join(content_lines)),
        {
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "查看原文"},
                    "url": item.link,
                    "type": "primary",
                    "value": {
                        "source": item.source,
                        "published_at": format_datetime(item.published_at, timezone_name),
                    },
                }
            ],
        },
    ]


def markdown_div(content: str) -> dict:
    return {
        "tag": "div",
        "text": {
            "tag": "lark_md",
            "content": content,
        },
    }


def split_markdown_sections(markdown: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, list[str]]] = []
    current_heading: str | None = None
    current_lines: list[str] = []
    for line in markdown.splitlines():
        if line.startswith("## "):
            if current_heading is not None:
                sections.append((current_heading, current_lines))
            current_heading = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_heading is not None:
        sections.append((current_heading, current_lines))
    return [(heading, "\n".join(lines)) for heading, lines in sections]


def trim(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return value[: max_length - 1].rstrip() + "…"


def escape_markdown(value: str) -> str:
    return value.replace("\n", " ").strip()
