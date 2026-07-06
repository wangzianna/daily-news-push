from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from .config import load_config
from .dedupe import dedupe_items, sort_items
from .feishu import push_to_feishu
from .html_report import (
    daily_html_filename,
    prune_html_reports,
    render_index,
    save_book_html,
    weekly_html_filename,
)
from .quality import apply_quality_rules
from .report import render_markdown, save_report
from .rss import fetch_all_sources
from .sources import SourceStore
from .summarizer import generate_daily_summary
from .weekly import generate_deep_report, save_weekly_report, select_topic_items


def run_daily(config_path: str, sources_path: str, push: bool = True) -> str:
    config = load_config(config_path)
    timezone_name = config["app"]["timezone"]
    store = SourceStore(sources_path)
    sources = store.list(enabled_only=True)

    items, errors = fetch_all_sources(
        sources=sources,
        timeout=int(config["app"]["fetch_timeout_seconds"]),
        user_agent=str(config["app"]["user_agent"]),
        limit_per_source=int(config["app"]["max_items_per_source"]),
    )
    now = datetime.now(ZoneInfo(timezone_name)).isoformat()
    fetched_source_ids = {item.source_id for item in items}
    for source_id in fetched_source_ids:
        store.set_last_fetch_at(source_id, now)

    sorted_items = sort_items(dedupe_items(items))
    selected_items = apply_quality_rules(
        sorted_items,
        max_per_direction=int(config["app"].get("max_items_per_direction_group", 3)),
        max_total=int(config["app"].get("max_items_total", 12)),
    )
    summary = generate_daily_summary(
        selected_items,
        api_key_env=str(config["llm"]["api_key_env"]),
        base_url=config["llm"].get("base_url"),
        model=str(config["llm"]["model"]),
        temperature=float(config["llm"]["temperature"]),
        timezone_name=timezone_name,
    )
    markdown = render_markdown(
        title=str(config["report"]["title"]),
        summary=summary,
        items=selected_items,
        timezone_name=timezone_name,
        errors=errors,
    )
    report_path = save_report(markdown, config["report"]["output_dir"], timezone_name)
    html_path = save_book_html(
        markdown,
        title=str(config["report"]["title"]),
        topic="每日精选",
        source_items=selected_items,
        output_dir=config["report"].get("html_output_dir", "docs"),
        timezone_name=timezone_name,
        filename_prefix=daily_html_filename(timezone_name),
        eyebrow="DAILY REPORT",
    )
    prune_html_reports(
        config["report"].get("html_output_dir", "docs"),
        "daily",
        int(config["report"].get("keep_html", 14)),
    )
    render_index(config["report"].get("html_output_dir", "docs"))
    report_url = build_report_url(str(config["report"].get("site_base_url", "")), html_path)

    if push and bool(config["feishu"].get("enabled", True)):
        push_to_feishu(
            title=str(config["report"]["title"]),
            summary=summary,
            items=selected_items,
            timezone_name=timezone_name,
            report_url=report_url,
            errors=errors,
            timeout=int(config["app"]["fetch_timeout_seconds"]),
        )

    return str(report_path)


def run_weekly(config_path: str, sources_path: str, push: bool = True) -> str:
    config = load_config(config_path)
    timezone_name = config["app"]["timezone"]
    weekly_config = config["weekly_report"]
    store = SourceStore(sources_path)
    source_sections = list(weekly_config.get("source_sections", ["weekly_report_sources", "sources"]))
    sources = store.list_many(source_sections, enabled_only=True)

    items, errors = fetch_all_sources(
        sources=sources,
        timeout=int(config["app"]["fetch_timeout_seconds"]),
        user_agent=str(config["app"]["user_agent"]),
        limit_per_source=int(weekly_config.get("max_items_per_source", config["app"]["max_items_per_source"])),
    )
    now = datetime.now(ZoneInfo(timezone_name)).isoformat()
    fetched_source_ids = {item.source_id for item in items}
    for source_id in fetched_source_ids:
        store.set_last_fetch_at(source_id, now, sections=source_sections)

    scored_items = apply_quality_rules(
        sort_items(dedupe_items(items)),
        max_per_direction=int(weekly_config.get("max_items_per_direction_group", 40)),
        max_total=int(weekly_config.get("candidate_items", 40)),
    )
    selected_items = select_topic_items(
        scored_items,
        keywords=list(weekly_config.get("keywords", [])),
        max_items=int(weekly_config.get("max_source_items", 24)),
    )
    report = generate_deep_report(
        selected_items,
        topic=str(weekly_config["topic"]),
        api_key_env=str(config["llm"]["api_key_env"]),
        base_url=config["llm"].get("base_url"),
        model=str(config["llm"]["model"]),
        temperature=float(config["llm"]["temperature"]),
        timezone_name=timezone_name,
    )
    report_path = save_weekly_report(
        report,
        weekly_config.get("output_dir", "weekly_reports"),
        timezone_name,
    )
    html_path = save_book_html(
        report,
        title=str(weekly_config["title"]),
        topic=str(weekly_config["topic"]),
        source_items=selected_items,
        output_dir=weekly_config.get("html_output_dir", weekly_config.get("output_dir", "weekly_reports")),
        timezone_name=timezone_name,
        filename_prefix=weekly_html_filename(timezone_name),
        eyebrow="WEEKLY DEEP REPORT",
    )
    prune_html_reports(
        weekly_config.get("html_output_dir", "docs"),
        "weekly",
        int(weekly_config.get("keep_html", 8)),
    )
    render_index(weekly_config.get("html_output_dir", "docs"))
    report_url = build_report_url(str(weekly_config.get("site_base_url", "")), html_path)

    if push and bool(config["feishu"].get("enabled", True)):
        from .feishu import push_deep_report_to_feishu

        push_deep_report_to_feishu(
            title=str(weekly_config["title"]),
            topic=str(weekly_config["topic"]),
            report_markdown=report,
            source_items=selected_items,
            timezone_name=timezone_name,
            report_url=report_url,
            errors=errors,
            timeout=int(config["app"]["fetch_timeout_seconds"]),
        )

    return str(report_path)


def build_report_url(site_base_url: str, html_path) -> str | None:
    if not site_base_url:
        return None
    base = site_base_url.rstrip("/") + "/"
    return base + "/".join(html_path.parts[-2:])


def notify_latest_daily(config_path: str) -> str:
    config = load_config(config_path)
    from .feishu import push_html_report_notice

    report_dir = config["report"].get("output_dir", "reports")
    html_dir = config["report"].get("html_output_dir", "docs")
    markdown_path = latest_file(report_dir, "*.md")
    html_path = latest_file(f"{html_dir}/daily", "*.html")
    if markdown_path is None or html_path is None:
        raise RuntimeError("未找到已生成的日报 Markdown 或 HTML")

    report_url = build_report_url(str(config["report"].get("site_base_url", "")), html_path)
    if not report_url:
        raise RuntimeError("未配置 report.site_base_url")

    push_html_report_notice(
        title=str(config["report"]["title"]),
        subtitle="今日简报",
        markdown=markdown_path.read_text(encoding="utf-8"),
        report_url=report_url,
        timeout=int(config["app"]["fetch_timeout_seconds"]),
    )
    return report_url


def notify_latest_weekly(config_path: str) -> str:
    config = load_config(config_path)
    weekly_config = config["weekly_report"]
    from .feishu import push_html_report_notice

    report_dir = weekly_config.get("output_dir", "weekly_reports")
    html_dir = weekly_config.get("html_output_dir", "docs")
    markdown_path = latest_file(report_dir, "*.md")
    html_path = latest_file(f"{html_dir}/weekly", "*.html")
    if markdown_path is None or html_path is None:
        raise RuntimeError("未找到已生成的周报 Markdown 或 HTML")

    report_url = build_report_url(str(weekly_config.get("site_base_url", "")), html_path)
    if not report_url:
        raise RuntimeError("未配置 weekly_report.site_base_url")

    push_html_report_notice(
        title=str(weekly_config["title"]),
        subtitle=str(weekly_config["topic"]),
        markdown=markdown_path.read_text(encoding="utf-8"),
        report_url=report_url,
        timeout=int(config["app"]["fetch_timeout_seconds"]),
    )
    return report_url


def latest_file(directory: str, pattern: str):
    from pathlib import Path

    path = Path(directory)
    if not path.exists():
        return None
    files = sorted(path.glob(pattern), key=lambda item: item.name, reverse=True)
    return files[0] if files else None
