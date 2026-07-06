from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from .models import NewsItem
from .report import format_datetime


URL_RE = re.compile(r"(https?://[^\s)）]+)")


def render_book_html(
    markdown: str,
    title: str,
    topic: str,
    source_items: list[NewsItem],
    timezone_name: str,
) -> str:
    date_label = datetime.now(ZoneInfo(timezone_name)).strftime("%Y.%m.%d")
    body = markdown_to_book_html(markdown)
    sources = render_source_items(source_items, timezone_name)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}｜{escape(topic)}</title>
  <style>
    :root {{
      --paper: #fbfaf7;
      --ink: #1f2328;
      --muted: #71757d;
      --rule: #ded8cc;
      --accent: #7c4d3a;
      --soft: #f2eee7;
    }}

    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      background:
        linear-gradient(90deg, rgba(124, 77, 58, 0.05), transparent 18%, transparent 82%, rgba(124, 77, 58, 0.05)),
        var(--paper);
      color: var(--ink);
      font-family: "Songti SC", "STSong", "Noto Serif CJK SC", "Source Han Serif SC", Georgia, serif;
      text-rendering: optimizeLegibility;
      -webkit-font-smoothing: antialiased;
    }}

    .page {{
      width: min(100%, 820px);
      margin: 0 auto;
      padding: 88px 34px 112px;
    }}

    header {{
      margin-bottom: 64px;
      border-bottom: 1px solid var(--rule);
      padding-bottom: 34px;
    }}

    .eyebrow {{
      color: var(--accent);
      font-size: 15px;
      letter-spacing: 0.16em;
      margin-bottom: 22px;
    }}

    h1 {{
      margin: 0;
      font-size: clamp(42px, 8vw, 72px);
      line-height: 1.16;
      font-weight: 700;
      letter-spacing: 0;
    }}

    .subtitle {{
      margin-top: 22px;
      color: var(--muted);
      font-size: clamp(22px, 4vw, 34px);
      line-height: 1.55;
    }}

    .meta {{
      margin-top: 28px;
      color: var(--muted);
      font-size: 15px;
    }}

    main {{
      font-size: clamp(23px, 4.6vw, 36px);
      line-height: 2.05;
      letter-spacing: 0;
    }}

    h2 {{
      margin: 78px 0 26px;
      font-size: clamp(30px, 5.6vw, 46px);
      line-height: 1.35;
      font-weight: 700;
    }}

    p {{
      margin: 0 0 1.15em;
      text-align: justify;
    }}

    ol, ul {{
      margin: 0 0 1.25em;
      padding-left: 1.25em;
    }}

    li {{
      margin: 0.5em 0;
      padding-left: 0.1em;
    }}

    a {{
      color: var(--accent);
      text-decoration-thickness: 1px;
      text-underline-offset: 0.16em;
      word-break: break-word;
    }}

    strong {{
      font-weight: 700;
    }}

    .sources {{
      margin-top: 88px;
      padding: 34px 28px;
      background: var(--soft);
      border: 1px solid var(--rule);
    }}

    .sources h2 {{
      margin-top: 0;
    }}

    .source-list {{
      font-size: clamp(17px, 3vw, 22px);
      line-height: 1.75;
      padding-left: 1.2em;
    }}

    .source-list li {{
      margin-bottom: 0.9em;
    }}

    .source-meta {{
      display: block;
      color: var(--muted);
      font-size: 0.82em;
      margin-top: 0.1em;
    }}

    @media (min-width: 860px) {{
      .page {{
        padding-left: 0;
        padding-right: 0;
      }}
    }}

    @media print {{
      body {{ background: #fff; }}
      .page {{ width: 100%; padding: 40px 56px; }}
      a {{ color: inherit; }}
    }}
  </style>
</head>
<body>
  <article class="page">
    <header>
      <div class="eyebrow">DEEP REPORT</div>
      <h1>{escape(title)}</h1>
      <div class="subtitle">{escape(topic)}</div>
      <div class="meta">{date_label} · 传统书籍阅读版</div>
    </header>
    <main>
{body}
{sources}
    </main>
  </article>
</body>
</html>
"""


def save_book_html(
    markdown: str,
    title: str,
    topic: str,
    source_items: list[NewsItem],
    output_dir: str | Path,
    timezone_name: str,
) -> Path:
    report_dir = Path(output_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    filename = datetime.now(ZoneInfo(timezone_name)).strftime("%Y-W%U") + ".html"
    path = report_dir / filename
    html = render_book_html(markdown, title, topic, source_items, timezone_name)
    path.write_text(html, encoding="utf-8")
    return path


def markdown_to_book_html(markdown: str) -> str:
    blocks: list[str] = []
    list_lines: list[str] = []
    list_type: str | None = None
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            blocks.append(f"      <p>{inline_markup(' '.join(paragraph))}</p>")
            paragraph = []

    def flush_list() -> None:
        nonlocal list_lines, list_type
        if list_lines and list_type:
            items = "\n".join(f"        <li>{inline_markup(line)}</li>" for line in list_lines)
            blocks.append(f"      <{list_type}>\n{items}\n      </{list_type}>")
        list_lines = []
        list_type = None

    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            flush_paragraph()
            flush_list()
            continue
        if line.startswith("# "):
            continue
        if line.startswith("## "):
            flush_paragraph()
            flush_list()
            blocks.append(f"      <h2>{escape(line[3:].strip())}</h2>")
            continue
        ordered = re.match(r"^\d+[.、]\s*(.+)$", line)
        unordered = re.match(r"^[-*]\s+(.+)$", line)
        if ordered or unordered:
            flush_paragraph()
            next_type = "ol" if ordered else "ul"
            if list_type and list_type != next_type:
                flush_list()
            list_type = next_type
            list_lines.append((ordered or unordered).group(1))
            continue
        flush_list()
        paragraph.append(line)

    flush_paragraph()
    flush_list()
    return "\n".join(blocks)


def render_source_items(source_items: list[NewsItem], timezone_name: str) -> str:
    if not source_items:
        return ""
    items = []
    for item in source_items:
        meta = f"{item.source} · {format_datetime(item.published_at, timezone_name)}"
        items.append(
            "\n".join(
                [
                    "        <li>",
                    f"          <a href=\"{escape(item.link)}\" target=\"_blank\" rel=\"noopener noreferrer\">{escape(item.title)}</a>",
                    f"          <span class=\"source-meta\">{escape(meta)}</span>",
                    "        </li>",
                ]
            )
        )
    return "\n".join(
        [
            "      <section class=\"sources\">",
            "        <h2>原文链接</h2>",
            "        <ol class=\"source-list\">",
            *items,
            "        </ol>",
            "      </section>",
        ]
    )


def inline_markup(text: str) -> str:
    value = escape(text)
    value = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", value)
    return URL_RE.sub(link_replacement, value)


def link_replacement(match: re.Match[str]) -> str:
    url = match.group(1)
    return f'<a href="{url}" target="_blank" rel="noopener noreferrer">{url}</a>'
