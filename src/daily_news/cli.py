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
        if args.command == "notify-status":
            from .runner import notify_workflow_status

            notify_workflow_status(args.config, args.title, args.status, args.details)
            print("运行状态通知已推送")
            return 0
        if args.command == "debug":
            return handle_debug(args)
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

    notify_status_parser = subparsers.add_parser("notify-status", help="推送 GitHub Actions 运行状态")
    notify_status_parser.add_argument("--config", default="config.yaml", help="运行配置文件路径")
    notify_status_parser.add_argument("--title", required=True, help="通知标题")
    notify_status_parser.add_argument("--status", required=True, help="运行状态")
    notify_status_parser.add_argument("--details", required=True, help="状态说明")

    debug_parser = subparsers.add_parser("debug", help="调试模式：查看评分或测试单源")
    debug_parser.add_argument("--config", default="config.yaml", help="运行配置文件路径")
    debug_parser.add_argument("--sources", default="sources.yaml", help="订阅源配置文件路径")
    debug_parser.add_argument("--show-scores", metavar="REPORT", help="显示指定 Markdown 报告的评分详情")
    debug_parser.add_argument("--source", metavar="SOURCE_ID", help="测试单个订阅源并显示详细抓取结果")
    debug_parser.add_argument("--limit", type=int, default=3, help="测试源时抓取的条目数")
    debug_parser.add_argument("--timeout", type=int, default=20, help="请求超时时间（秒）")

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


def handle_debug(args: argparse.Namespace) -> int:
    if args.show_scores:
        return handle_debug_scores(args)
    if args.source:
        return handle_debug_source(args)
    print("请指定 --show-scores 或 --source", file=sys.stderr)
    return 1


def handle_debug_scores(args: argparse.Namespace) -> int:
    from pathlib import Path

    report_path = Path(args.show_scores)
    if not report_path.exists():
        print(f"报告不存在: {report_path}", file=sys.stderr)
        return 1

    print(f"报告: {report_path}")
    print("=" * 80)

    # This would need to parse the markdown and show scores
    # For now, just indicate it's not fully implemented
    print("评分详情功能待实现（需要解析 Markdown 报告并重新计算评分）")
    return 0


def handle_debug_source(args: argparse.Namespace) -> int:
    from .rss import fetch_source
    from .quality import score_item
    from .content import fetch_full_text

    store = SourceStore(args.sources)
    try:
        source = store.get(args.source)
    except ValueError as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1

    print(f"测试订阅源: {source.id} ({source.name})")
    print(f"URL: {source.url}")
    print(f"类别: {source.category}, 语言: {source.language}, 权重: {source.weight}")
    print(f"可信度: {source.credibility}")
    print("=" * 80)

    items = fetch_source(source, args.timeout, "DailyNewsPush/1.0", args.limit)
    print(f"抓取成功，共返回 {len(items)} 条\n")

    for i, item in enumerate(items, 1):
        print(f"[{i}] {item.title}")
        print(f"    链接: {item.link}")
        print(f"    摘要: {item.summary[:100]}...")

        # Fetch full text
        full_text = fetch_full_text(item.link, timeout=args.timeout)
        if full_text:
            print(f"    全文: {full_text[:150]}...")
        else:
            print(f"    全文: (无法抓取)")

        # Score the item
        scored = score_item(item)
        print(f"    评分: {scored.quality_score}")
        print(f"    标签: {', '.join(scored.quality_labels or [])}")
        if scored.penalty_labels:
            print(f"    惩罚: {', '.join(scored.penalty_labels)}")
        print()

    return 0
