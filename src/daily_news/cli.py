from __future__ import annotations

import argparse
import sys

from .models import Source
from .sources import SourceStore


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "run":
            from .runner import run_daily

            report_path = run_daily(args.config, args.sources, push=not args.no_push)
            print(f"日报已生成: {report_path}")
            return 0
        if args.command == "weekly":
            from .runner import run_weekly

            report_path = run_weekly(args.config, args.sources, push=not args.no_push)
            print(f"周末深度报告已生成: {report_path}")
            return 0
        if args.command == "notify-daily":
            from .runner import notify_latest_daily

            report_url = notify_latest_daily(args.config)
            print(f"日报通知已推送: {report_url}")
            return 0
        if args.command == "notify-weekly":
            from .runner import notify_latest_weekly

            report_url = notify_latest_weekly(args.config)
            print(f"周报通知已推送: {report_url}")
            return 0
        if args.command == "sources":
            return handle_sources(args)
        parser.print_help()
        return 1
    except Exception as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="daily-news", description="每日资讯推送")
    parser.add_argument("--sources", default="sources.yaml", help="订阅源配置文件路径")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="抓取资讯、生成日报并推送")
    run_parser.add_argument("--config", default="config.yaml", help="运行配置文件路径")
    run_parser.add_argument("--sources", default="sources.yaml", help="订阅源配置文件路径")
    run_parser.add_argument("--no-push", action="store_true", help="只生成日报，不推送飞书")

    weekly_parser = subparsers.add_parser("weekly", help="生成周末主题深度报告并推送")
    weekly_parser.add_argument("--config", default="config.yaml", help="运行配置文件路径")
    weekly_parser.add_argument("--sources", default="sources.yaml", help="订阅源配置文件路径")
    weekly_parser.add_argument("--no-push", action="store_true", help="只生成报告，不推送飞书")

    notify_daily_parser = subparsers.add_parser("notify-daily", help="推送最近一次日报 HTML 链接")
    notify_daily_parser.add_argument("--config", default="config.yaml", help="运行配置文件路径")

    notify_weekly_parser = subparsers.add_parser("notify-weekly", help="推送最近一次周报 HTML 链接")
    notify_weekly_parser.add_argument("--config", default="config.yaml", help="运行配置文件路径")

    sources_parser = subparsers.add_parser("sources", help="管理订阅源")
    sources_subparsers = sources_parser.add_subparsers(dest="sources_command", required=True)

    sources_subparsers.add_parser("list", help="列出所有订阅源")

    add_parser = sources_subparsers.add_parser("add", help="添加订阅源")
    add_parser.add_argument("--id", required=True)
    add_parser.add_argument("--name", required=True)
    add_parser.add_argument("--url", required=True)
    add_parser.add_argument("--category", required=True)
    add_parser.add_argument("--language", default="zh")
    add_parser.add_argument("--weight", type=int, default=0)
    add_parser.add_argument("--disabled", action="store_true")

    delete_parser = sources_subparsers.add_parser("delete", help="删除订阅源")
    delete_parser.add_argument("id")

    edit_parser = sources_subparsers.add_parser("edit", help="编辑订阅源")
    edit_parser.add_argument("id")
    edit_parser.add_argument("--name")
    edit_parser.add_argument("--url")
    edit_parser.add_argument("--category")
    edit_parser.add_argument("--language")
    edit_parser.add_argument("--weight", type=int)

    enable_parser = sources_subparsers.add_parser("enable", help="启用订阅源")
    enable_parser.add_argument("id")

    disable_parser = sources_subparsers.add_parser("disable", help="停用订阅源")
    disable_parser.add_argument("id")

    test_parser = sources_subparsers.add_parser("test", help="测试订阅源抓取")
    test_parser.add_argument("id")
    test_parser.add_argument("--limit", type=int, default=5)
    test_parser.add_argument("--timeout", type=int, default=20)
    test_parser.add_argument("--user-agent", default="DailyNewsPush/1.0")

    return parser


def handle_sources(args: argparse.Namespace) -> int:
    store = SourceStore(args.sources)
    command = args.sources_command
    if command == "list":
        print_sources(store.list())
    elif command == "add":
        store.add(
            Source(
                id=args.id,
                name=args.name,
                url=args.url,
                category=args.category,
                language=args.language,
                enabled=not args.disabled,
                weight=args.weight,
            )
        )
        print(f"已添加订阅源: {args.id}")
    elif command == "delete":
        store.delete(args.id)
        print(f"已删除订阅源: {args.id}")
    elif command == "edit":
        source = store.update(
            args.id,
            name=args.name,
            url=args.url,
            category=args.category,
            language=args.language,
            weight=args.weight,
        )
        print(f"已更新订阅源: {source.id}")
    elif command == "enable":
        store.set_enabled(args.id, True)
        print(f"已启用订阅源: {args.id}")
    elif command == "disable":
        store.set_enabled(args.id, False)
        print(f"已停用订阅源: {args.id}")
    elif command == "test":
        from .rss import fetch_source

        source = store.get(args.id)
        items = fetch_source(source, args.timeout, args.user_agent, args.limit)
        print(f"抓取成功，共返回 {len(items)} 条：")
        for item in items:
            print(f"- {item.title} | {item.link}")
    return 0


def print_sources(sources: list[Source]) -> None:
    if not sources:
        print("暂无订阅源")
        return
    for source in sources:
        status = "enabled" if source.enabled else "disabled"
        print(
            f"{source.id}\t{status}\t{source.weight}\t{source.category}\t"
            f"{source.language}\t{source.name}\t{source.url}\tlast={source.last_fetch_at or '-'}"
        )
