from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .cluster import dedupe_by_cluster
from .content import enrich_items_with_full_text
from .dedupe import dedupe_items, sort_items
from .html_report import prune_html_reports, render_index, save_book_html
from .models import NewsItem
from .quality import apply_quality_rules
from .report import load_published, render_markdown, save_report
from .rss import fetch_all_sources
from .sources import SourceStore
from .weekly import save_weekly_report, select_topic_items


class Pipeline:
    def __init__(
        self,
        config: dict,
        sources_path: str,
        report_type: str = "daily",
        push: bool = True,
    ):
        self.config = config
        self.timezone_name = config["app"]["timezone"]
        self.report_type = report_type
        self.push = push
        self.store = SourceStore(sources_path)
        self.errors: dict[str, str] = {}
        self.items: list[NewsItem] = []
        self.selected_items: list[NewsItem] = []
        self.summary: str = ""
        self.token_usage: dict[str, int] | None = None

    def fetch_sources(self, source_sections: list[str] | None = None) -> None:
        sections = source_sections or ["sources"]
        sources = self.store.list_many(sections, enabled_only=True)

        self.items, self.errors = fetch_all_sources(
            sources=sources,
            timeout=int(self.config["app"]["fetch_timeout_seconds"]),
            user_agent=str(self.config["app"]["user_agent"]),
            limit_per_source=int(self.config["app"]["max_items_per_source"]),
        )

        now = datetime.now(ZoneInfo(self.timezone_name)).isoformat()
        fetched_source_ids = {item.source_id for item in self.items}
        for source_id in fetched_source_ids:
            self.store.set_last_fetch_at(source_id, now)

        # Track consecutive failures
        for source_id in self.errors:
            failure_count = self.store.increment_consecutive_failures(source_id)
            if failure_count >= 3:
                self.errors[source_id] = f"{self.errors[source_id]} (连续失败 {failure_count} 次，建议检查或手动停用)"

        # Check error thresholds and send alerts
        self._check_and_alert_errors(sources)

    def _check_and_alert_errors(self, sources: list) -> None:
        total_sources = len(sources)
        error_count = len(self.errors)
        error_rate = error_count / total_sources if total_sources > 0 else 0

        critical_sources = [s for s in sources if s.weight >= 9]
        critical_errors = [s for s in critical_sources if s.id in self.errors]
        all_critical_failed = len(critical_sources) > 0 and len(critical_errors) == len(critical_sources)

        should_alert = error_rate > 0.3 or all_critical_failed

        if should_alert and self.push and bool(self.config["feishu"].get("enabled", True)):
            from .feishu import push_workflow_status_notice
            from .runner import github_run_url

            status = "error" if all_critical_failed else "warning"
            details = f"错误率: {error_rate:.0%} ({error_count}/{total_sources})"
            if all_critical_failed:
                details += f"\n关键源全部失败: {', '.join(s.name for s in critical_errors)}"
            if self.errors:
                details += "\n\n错误详情:\n" + "\n".join(f"- {k}: {v}" for k, v in list(self.errors.items())[:5])

            try:
                push_workflow_status_notice(
                    title=self._get_report_title(),
                    status=status,
                    details=details,
                    run_url=github_run_url(),
                    timeout=int(self.config["app"]["fetch_timeout_seconds"]),
                )
            except Exception as exc:
                print(f"告警推送失败: {exc}")

    def dedupe_and_filter(self, exclude_published: bool = True) -> None:
        sorted_items = sort_items(dedupe_items(self.items))

        if exclude_published and self.report_type == "daily":
            html_dir = self.config["report"].get("html_output_dir", "docs")
            published_links, published_titles = load_published(html_dir, self.timezone_name)
            if published_links or published_titles:
                from .dedupe import normalize_url

                result: list[NewsItem] = []
                for item in sorted_items:
                    if normalize_url(item.link) in published_links:
                        continue
                    title_key = f"{item.title.strip()}||{item.source.strip()}"
                    if title_key in published_titles:
                        continue
                    result.append(item)
                sorted_items = result

        self.selected_items = sorted_items

    def apply_quality_and_clustering(
        self,
        max_per_direction: int = 4,
        max_total: int = 16,
        cluster_threshold: int = 80,
    ) -> None:
        self.selected_items = apply_quality_rules(
            self.selected_items,
            max_per_direction=max_per_direction,
            max_total=max_total,
        )
        self.selected_items = dedupe_by_cluster(
            self.selected_items,
            threshold=cluster_threshold,
        )

    def enrich_full_text(self, max_length: int = 1200) -> None:
        enrich_items_with_full_text(
            self.selected_items,
            timeout=int(self.config["app"]["fetch_timeout_seconds"]),
            user_agent=str(self.config["app"]["user_agent"]),
            max_length=max_length,
        )

    def generate_summary(self, summary_func, **kwargs) -> None:
        self.summary, self.token_usage = summary_func(
            self.selected_items,
            timezone_name=self.timezone_name,
            **kwargs,
        )
        if self.token_usage:
            self.summary += f"\n\n---\n\n**LLM Token 消耗**：输入 {self.token_usage['prompt_tokens']}，输出 {self.token_usage['completion_tokens']}，总计 {self.token_usage['total_tokens']}\n"

    def save_report(self, markdown: str, output_dir: str) -> Path:
        return save_report(markdown, output_dir, self.timezone_name)

    def save_html(
        self,
        markdown: str,
        title: str,
        topic: str,
        output_dir: str,
        filename_prefix: str,
        eyebrow: str,
    ) -> Path:
        html_path = save_book_html(
            markdown,
            title=title,
            topic=topic,
            source_items=self.selected_items,
            output_dir=output_dir,
            timezone_name=self.timezone_name,
            filename_prefix=filename_prefix,
            eyebrow=eyebrow,
        )
        subfolder = "daily" if "daily" in filename_prefix else "weekly"
        keep_config = self.config["weekly_report"] if self.report_type == "weekly" else self.config["report"]
        prune_html_reports(output_dir, subfolder, int(keep_config.get("keep_html", 14)))
        render_index(output_dir)
        return html_path

    def push_to_feishu(self, report_url: str | None, push_func, **kwargs) -> None:
        if self.push and bool(self.config["feishu"].get("enabled", True)):
            push_func(
                title=self._get_report_title(),
                timezone_name=self.timezone_name,
                report_url=report_url,
                errors=self.errors,
                timeout=int(self.config["app"]["fetch_timeout_seconds"]),
                **kwargs,
            )

    def _get_report_title(self) -> str:
        if self.report_type == "weekly":
            return str(self.config["weekly_report"]["title"])
        return str(self.config["report"]["title"])
