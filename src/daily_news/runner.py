from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from .config import load_config
from .dedupe import dedupe_items, sort_items
from .feishu import push_to_feishu
from .quality import apply_quality_rules
from .report import render_markdown, save_report
from .rss import fetch_all_sources
from .sources import SourceStore
from .summarizer import generate_daily_summary


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

    if push and bool(config["feishu"].get("enabled", True)):
        push_to_feishu(markdown, str(config["report"]["title"]), int(config["app"]["fetch_timeout_seconds"]))

    return str(report_path)
