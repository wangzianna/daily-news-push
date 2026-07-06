from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .models import NewsItem


REPORT_SECTIONS = ["今日重点", "行业动态", "AI / 科技", "产品设计相关", "值得关注的信号"]


def group_by_category(items: list[NewsItem]) -> dict[str, list[NewsItem]]:
    grouped: dict[str, list[NewsItem]] = defaultdict(list)
    for item in items:
        grouped[item.category].append(item)
    return dict(grouped)


def items_as_context(items: list[NewsItem], timezone_name: str) -> str:
    lines = []
    for index, item in enumerate(items, start=1):
        published = format_datetime(item.published_at, timezone_name)
        lines.append(
            "\n".join(
                [
                    f"{index}. 标题：{item.title}",
                    f"   来源：{item.source}",
                    f"   分类：{item.category}",
                    f"   质量标签：{format_labels(item.quality_labels)}",
                    f"   降权原因：{format_labels(item.penalty_labels)}",
                    f"   健康证据类型：{item.evidence_type or '不适用'}",
                    f"   AI 内容类型：{item.ai_type or '不适用'}",
                    f"   发布时间：{published}",
                    f"   链接：{item.link}",
                    f"   摘要：{item.summary}",
                ]
            )
        )
    return "\n\n".join(lines)


def render_markdown(
    title: str,
    summary: str,
    items: list[NewsItem],
    timezone_name: str,
    errors: dict[str, str] | None = None,
) -> str:
    today = datetime.now(ZoneInfo(timezone_name)).strftime("%Y-%m-%d")
    body = [
        f"# {title}",
        "",
        f"**日期**：{today}",
        f"**精选**：{len(items)} 条，已按质量规则过滤",
        "",
        "---",
        "",
        "## 今日简报",
        "",
        summary.strip(),
        "",
        "---",
        "",
        "## 精选资讯",
    ]
    for category, category_items in group_by_category(items).items():
        body.extend(["", f"### {category}"])
        for index, item in enumerate(category_items, start=1):
            meta = build_meta_line(item, timezone_name)
            body.append(
                "\n".join(
                    [
                        f"**{index}. {item.title}**",
                        f"> {meta}",
                        f"> 摘要：{item.summary or '暂无摘要'}",
                        f"> 原文：{item.link}",
                    ]
                )
            )

    if errors:
        body.extend(["", "---", "", "## 抓取异常"])
        for source_id, error in errors.items():
            body.append(f"- {source_id}: {error}")

    return "\n".join(body).strip() + "\n"


def save_report(markdown: str, output_dir: str | Path, timezone_name: str) -> Path:
    report_dir = Path(output_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    filename = datetime.now(ZoneInfo(timezone_name)).strftime("%Y-%m-%d") + ".md"
    path = report_dir / filename
    path.write_text(markdown, encoding="utf-8")
    return path


def format_datetime(value: datetime | None, timezone_name: str) -> str:
    if value is None:
        return "未知"
    return value.astimezone(ZoneInfo(timezone_name)).strftime("%Y-%m-%d %H:%M")


def build_meta_line(item: NewsItem, timezone_name: str) -> str:
    parts = [
        f"来源：{item.source}",
        f"时间：{format_datetime(item.published_at, timezone_name)}",
        f"质量：{format_labels(item.quality_labels)}",
    ]
    if item.evidence_type:
        parts.append(f"证据：{item.evidence_type}")
    if item.ai_type:
        parts.append(f"AI 类型：{item.ai_type}")
    if item.penalty_labels:
        parts.append(f"降权：{format_labels(item.penalty_labels)}")
    return " ｜ ".join(parts)


def format_labels(labels: list[str] | None) -> str:
    if not labels:
        return "无"
    return "、".join(labels)
