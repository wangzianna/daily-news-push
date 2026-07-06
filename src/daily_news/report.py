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
    body = [f"# {title} - {today}", "", summary.strip(), "", "## 原始资讯"]
    for category, category_items in group_by_category(items).items():
        body.extend(["", f"### {category}"])
        for item in category_items:
            body.append(
                f"- [{item.title}]({item.link}) | {item.source} | "
                f"{format_datetime(item.published_at, timezone_name)} | 权重 {item.weight}"
            )
            if item.summary:
                body.append(f"  - {item.summary}")

    if errors:
        body.extend(["", "## 抓取异常"])
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
