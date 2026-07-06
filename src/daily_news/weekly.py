from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from openai import OpenAI

from .models import NewsItem
from .report import format_datetime, items_as_context


WEEKLY_SECTIONS = [
    "本周关键变化",
    "重要数据/事件/报告",
    "判断趋势",
    "对个体、职场、健康、经济的影响概览",
    "值得继续关注的问题",
    "原文链接",
]


def select_topic_items(items: list[NewsItem], keywords: list[str], max_items: int) -> list[NewsItem]:
    normalized = [keyword.lower() for keyword in keywords if keyword.strip()]
    matched = []
    for item in items:
        text = f"{item.title} {item.summary} {item.category}".lower()
        if any(keyword in text for keyword in normalized):
            matched.append(item)
    source = matched or items
    return sorted(
        source,
        key=lambda item: (
            -item.quality_score,
            -item.weight,
            -(item.published_at.timestamp() if item.published_at else 0),
        ),
    )[:max_items]


def generate_deep_report(
    items: list[NewsItem],
    topic: str,
    api_key_env: str,
    base_url: str | None,
    model: str,
    temperature: float,
    timezone_name: str,
) -> str:
    if not items:
        return fallback_deep_report([], topic, timezone_name, api_key_env)

    api_key = os.environ.get(api_key_env)
    if not api_key:
        return fallback_deep_report(items, topic, timezone_name, api_key_env)

    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {
                "role": "system",
                "content": "你是严谨的研究型编辑，擅长把一周资讯整理成结构化中文深度报告。",
            },
            {"role": "user", "content": build_deep_report_prompt(items, topic, timezone_name)},
        ],
    )
    return response.choices[0].message.content or fallback_deep_report(
        items, topic, timezone_name, api_key_env
    )


def build_deep_report_prompt(items: list[NewsItem], topic: str, timezone_name: str) -> str:
    sections = "\n".join(f"## {section}" for section in WEEKLY_SECTIONS)
    return f"""请基于本周资讯，围绕主题「{topic}」写一篇中文结构化深度报告。

这不是每日新闻推送，不要做碎片化新闻列表。请把材料综合成一篇有判断、有脉络、有引用来源的周末深度报告。

必须使用以下结构和二级标题：
{sections}

写作要求：
1. 每个部分写成段落 + 少量要点，重点是解释变化、背景、影响和趋势。
2. 「重要数据/事件/报告」必须尽量标注来源名称。
3. 「判断趋势」要给出 3-5 条明确判断，不要空泛。
4. 「对个体、职场、健康、经济的影响概览」要分别覆盖个体、职场、健康、经济四个角度。
5. 「值得继续关注的问题」输出 5-8 个后续观察问题。
6. 「原文链接」必须列出引用过的关键原文链接，格式为：- 标题｜来源｜链接。
7. 不要编造材料中没有的信息；不确定时明确写“仍需观察”。

材料：
{items_as_context(items, timezone_name)}
"""


def fallback_deep_report(
    items: list[NewsItem],
    topic: str,
    timezone_name: str,
    api_key_env: str = "DEEPSEEK_API_KEY",
) -> str:
    lines = [
        f"# 周末深度报告：{topic}",
        "",
        "## 本周关键变化",
        f"- 未配置 {api_key_env}，已生成基础版深度报告框架。",
        "",
        "## 重要数据/事件/报告",
    ]
    lines.extend([f"- {item.title}（{item.source}，{format_datetime(item.published_at, timezone_name)}）" for item in items[:6]])
    lines.extend(
        [
            "",
            "## 判断趋势",
            "- 需要配置大模型 API 后生成完整趋势判断。",
            "",
            "## 对个体、职场、健康、经济的影响概览",
            "- 个体：仍需结合更多材料判断。",
            "- 职场：仍需结合更多材料判断。",
            "- 健康：仍需结合更多材料判断。",
            "- 经济：仍需结合更多材料判断。",
            "",
            "## 值得继续关注的问题",
            "- 下周是否出现更多一手来源或研究来源？",
            "",
            "## 原文链接",
        ]
    )
    lines.extend([f"- {item.title}｜{item.source}｜{item.link}" for item in items])
    return "\n".join(lines).strip() + "\n"


def save_weekly_report(markdown: str, output_dir: str | Path, timezone_name: str) -> Path:
    report_dir = Path(output_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    filename = datetime.now(ZoneInfo(timezone_name)).strftime("%Y-W%U") + ".md"
    path = report_dir / filename
    path.write_text(markdown, encoding="utf-8")
    return path
