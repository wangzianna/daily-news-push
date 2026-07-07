from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser

import requests


class _ArticleTextExtractor(HTMLParser):
    SKIP_TAGS = {"script", "style", "nav", "header", "footer", "aside", "noscript"}
    BLOCK_TAGS = {"p", "div", "article", "section", "li", "blockquote"}

    def __init__(self) -> None:
        super().__init__()
        self._pieces: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
        elif tag in self.BLOCK_TAGS and self._pieces:
            self._pieces.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._pieces.append(data)

    def get_text(self) -> str:
        return " ".join(self._pieces)


_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


def fetch_full_text(url: str, timeout: int = 10, user_agent: str = "DailyNewsPush/1.0") -> str:
    try:
        response = requests.get(
            url,
            headers={"User-Agent": user_agent},
            timeout=timeout,
            allow_redirects=True,
        )
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "html" not in content_type and "xml" not in content_type:
            return ""
        return extract_text_from_html(response.text)
    except Exception:
        return ""


def extract_text_from_html(html: str) -> str:
    extractor = _ArticleTextExtractor()
    try:
        extractor.feed(html)
        raw = extractor.get_text()
    except Exception:
        raw = _TAG_RE.sub(" ", html)
    text = unescape(raw)
    text = _SPACE_RE.sub(" ", text).strip()
    return text


def enrich_items_with_full_text(
    items,
    timeout: int = 10,
    user_agent: str = "DailyNewsPush/1.0",
    max_length: int = 1200,
) -> None:
    for item in items:
        text = fetch_full_text(item.link, timeout=timeout, user_agent=user_agent)
        if text:
            item.full_text = text[:max_length]
