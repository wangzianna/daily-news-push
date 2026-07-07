from __future__ import annotations

import concurrent.futures
import re
import threading
from collections import defaultdict
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlsplit

import requests
import trafilatura


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


def fetch_full_text(
    url: str,
    timeout: int = 10,
    user_agent: str = "DailyNewsPush/1.0",
) -> str:
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            extracted = trafilatura.extract(
                downloaded,
                include_comments=False,
                include_tables=False,
                deduplicate=True,
                favor_precision=True,
            )
            if extracted:
                return _SPACE_RE.sub(" ", extracted).strip()
    except Exception:
        pass

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


def enrich_items_with_full_text(
    items,
    timeout: int = 8,
    user_agent: str = "DailyNewsPush/1.0",
    max_length: int = 1200,
    max_workers: int = 6,
    per_domain_limit: int = 2,
) -> None:
    if not items:
        return

    domain_semaphores: dict[str, threading.Semaphore] = defaultdict(
        lambda: threading.Semaphore(per_domain_limit)
    )

    def _fetch(item):
        domain = urlsplit(item.link).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        sem = domain_semaphores[domain]
        sem.acquire()
        try:
            text = fetch_full_text(item.link, timeout=timeout, user_agent=user_agent)
            if text:
                item.full_text = text[:max_length]
        finally:
            sem.release()

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(max_workers, len(items))) as executor:
        list(executor.map(_fetch, items))
