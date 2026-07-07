from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .cluster import dedupe_by_cluster
from .config import load_config
from .content import enrich_items_with_full_text
from .dedupe import dedupe_items, sort_items
from .feishu import push_to_feishu
from .html_report import (
    daily_html_filename,
    prune_html_reports,
    render_index,
    save_book_html,
    weekly_html_filename,
)
from .pipeline import Pipeline
from .quality import apply_quality_rules
from .report import load_published, render_markdown, save_report
from .rss import fetch_all_sources
from .sources import SourceStore
from .summarizer import generate_daily_summary
from .weekly import generate_deep_report, save_weekly_report, select_topic_items


def run_daily(config_path: str, sources_path: str, push: bool = True) -> str:
    config = load_config(config_path)
    pipeline = Pipeline(config, sources_path, report_type="daily", push=push)

    # Step 1: Fetch sources
    pipeline.fetch_sources(source_sections=["sources"])

    # Step 2: Dedupe and filter
    pipeline.dedupe_and_filter(exclude_published=True)

    # Step 3: Quality and clustering
    pipeline.apply_quality_and_clustering(
        max_per_direction=int(config["app"].get("max_items_per_direction_group", 4)),
        max_total=int(config["app"].get("max_items_total", 16)),
        cluster_threshold=int(config["app"].get("cluster_threshold", 80)),
    )

    # Step 4: Enrich with full text
    pipeline.enrich_full_text(max_length=int(config["app"].get("full_text_max_length", 1200)))

    # Step 5: Generate summary
    pipeline.generate_summary(
        generate_daily_summary,
        api_key_env=str(config["llm"]["api_key_env"]),
        base_url=config["llm"].get("base_url"),
        model=str(config["llm"]["model"]),
        temperature=float(config["llm"]["temperature"]),
    )

    # Step 6: Save markdown report
    timezone_name = config["app"]["timezone"]
    markdown = render_markdown(
        title=str(config["report"]["title"]),
        summary=pipeline.summary,
        items=pipeline.selected_items,
        timezone_name=timezone_name,
        errors=pipeline.errors,
    )
    report_path = pipeline.save_report(markdown, config["report"]["output_dir"])

    # Step 7: Save HTML report
    html_path = pipeline.save_html(
        markdown,
        title=str(config["report"]["title"]),
        topic="每日精选",
        output_dir=config["report"].get("html_output_dir", "docs"),
        filename_prefix=daily_html_filename(timezone_name),
        eyebrow="DAILY REPORT",
    )
    report_url = build_report_url(str(config["report"].get("site_base_url", "")), html_path)

    # Step 8: Push to Feishu
    pipeline.push_to_feishu(
        report_url=report_url,
        push_func=push_to_feishu,
        summary=pipeline.summary,
        items=pipeline.selected_items,
    )

    return str(report_path)


def run_weekly(config_path: str, sources_path: str, push: bool = True) -> str:
    config = load_config(config_path)
    weekly_config = config["weekly_report"]
    pipeline = Pipeline(config, sources_path, report_type="weekly", push=push)

    # Step 1: Fetch sources
    source_sections = list(weekly_config.get("source_sections", ["weekly_report_sources", "sources"]))
    pipeline.fetch_sources(source_sections=source_sections)

    # Step 2: Dedupe and quality filter (no exclude_published for weekly)
    pipeline.dedupe_and_filter(exclude_published=False)

    # Step 3: Apply quality rules and topic selection
    pipeline.apply_quality_and_clustering(
        max_per_direction=int(weekly_config.get("max_items_per_direction_group", 40)),
        max_total=int(weekly_config.get("candidate_items", 40)),
        cluster_threshold=int(config["app"].get("cluster_threshold", 80)),
    )
    pipeline.selected_items = select_topic_items(
        pipeline.selected_items,
        keywords=list(weekly_config.get("keywords", [])),
        max_items=int(weekly_config.get("max_source_items", 24)),
    )

    # Step 4: Enrich with full text
    pipeline.enrich_full_text(max_length=int(config["app"].get("full_text_max_length", 1200)))

    # Step 5: Generate deep report
    pipeline.generate_summary(
        generate_deep_report,
        topic=str(weekly_config["topic"]),
        api_key_env=str(config["llm"]["api_key_env"]),
        base_url=config["llm"].get("base_url"),
        model=str(config["llm"]["model"]),
        temperature=float(config["llm"]["temperature"]),
    )

    # Step 6: Save markdown report
    timezone_name = config["app"]["timezone"]
    report_path = save_weekly_report(
        pipeline.summary,
        weekly_config.get("output_dir", "weekly_reports"),
        timezone_name,
    )

    # Step 7: Save HTML report
    html_output_dir = weekly_config.get("html_output_dir", weekly_config.get("output_dir", "weekly_reports"))
    html_path = pipeline.save_html(
        pipeline.summary,
        title=str(weekly_config["title"]),
        topic=str(weekly_config["topic"]),
        output_dir=html_output_dir,
        filename_prefix=weekly_html_filename(timezone_name),
        eyebrow="WEEKLY DEEP REPORT",
    )
    report_url = build_report_url(str(weekly_config.get("site_base_url", "")), html_path)

    # Step 8: Push to Feishu
    if push and bool(config["feishu"].get("enabled", True)):
        from .feishu import push_deep_report_to_feishu

        push_deep_report_to_feishu(
            title=str(weekly_config["title"]),
            topic=str(weekly_config["topic"]),
            report_markdown=pipeline.summary,
            source_items=pipeline.selected_items,
            timezone_name=timezone_name,
            report_url=report_url,
            errors=pipeline.errors,
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
        action_url=github_run_url(),
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
        action_url=github_run_url(),
        timeout=int(config["app"]["fetch_timeout_seconds"]),
    )
    return report_url


def notify_workflow_status(config_path: str, title: str, status: str, details: str) -> None:
    config = load_config(config_path)
    from .feishu import push_workflow_status_notice

    push_workflow_status_notice(
        title=title,
        status=status,
        details=details,
        run_url=github_run_url(),
        timeout=int(config["app"]["fetch_timeout_seconds"]),
    )


def github_run_url() -> str | None:
    server_url = os.environ.get("GITHUB_SERVER_URL")
    repository = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    if not server_url or not repository or not run_id:
        return None
    return f"{server_url.rstrip('/')}/{repository}/actions/runs/{run_id}"


def latest_file(directory: str, pattern: str):
    from pathlib import Path

    path = Path(directory)
    if not path.exists():
        return None
    files = sorted(path.glob(pattern), key=lambda item: item.name, reverse=True)
    return files[0] if files else None


def exclude_published(
    items: list[NewsItem], config: dict, timezone_name: str
) -> list[NewsItem]:
    from .dedupe import normalize_url

    html_dir = config["report"].get("html_output_dir", "docs")
    published_links, published_titles = load_published(html_dir, timezone_name)
    if not published_links and not published_titles:
        return items

    result: list[NewsItem] = []
    for item in items:
        if normalize_url(item.link) in published_links:
            continue
        title_key = f"{item.title.strip()}||{item.source.strip()}"
        if title_key in published_titles:
            continue
        result.append(item)
    return result
