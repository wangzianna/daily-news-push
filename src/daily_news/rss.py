from __future__ import annotations

import concurrent.futures
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
import re
from typing import Any
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

import feedparser
import requests

from .models import NewsItem, Source


TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")

_MAX_WORKERS = 8


def _build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=2,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


_SESSION = _build_session()


def fetch_source(
    source: Source,
    timeout: int,
    user_agent: str,
    limit: int,
    session: requests.Session | None = None,
) -> list[NewsItem]:
    http = session or _SESSION
    response = http.get(source.url, headers={"User-Agent": user_agent}, timeout=timeout)
    response.raise_for_status()
    parsed = feedparser.parse(response.content)
    if parsed.bozo and not parsed.entries:
        raise RuntimeError(str(parsed.bozo_exception))

    items: list[NewsItem] = []
    for entry in parsed.entries[:limit]:
        title = clean_text(entry.get("title", "")).strip()
        link = entry.get("link", "").strip()
        if not title or not link:
            continue
        items.append(
            NewsItem(
                title=title,
                source=source.name,
                source_id=source.id,
                category=source.category,
                published_at=parse_entry_datetime(entry),
                link=link,
                summary=extract_summary(entry),
                weight=source.weight,
                language=source.language,
                credibility=source.credibility,
            )
        )
    return items


def fetch_all_sources(
    sources: list[Source],
    timeout: int,
    user_agent: str,
    limit_per_source: int,
    max_workers: int = _MAX_WORKERS,
) -> tuple[list[NewsItem], dict[str, str]]:
    items: list[NewsItem] = []
    errors: dict[str, str] = {}

    if not sources:
        return items, errors

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(max_workers, len(sources))) as executor:
        future_to_source = {
            executor.submit(fetch_source, source, timeout, user_agent, limit_per_source): source
            for source in sources
        }
        for future in concurrent.futures.as_completed(future_to_source):
            source = future_to_source[future]
            try:
                items.extend(future.result())
            except Exception as exc:
                errors[source.id] = str(exc)
    return items, errors


def parse_entry_datetime(entry: Any) -> datetime | None:
    for key in ("published", "updated", "created"):
        value = entry.get(key)
        if not value:
            continue
        try:
            dt = parsedate_to_datetime(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (TypeError, ValueError, IndexError, OverflowError):
            continue

    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        value = entry.get(key)
        if value:
            return datetime(*value[:6], tzinfo=timezone.utc)
    return None


def extract_summary(entry: Any) -> str:
    value = entry.get("summary") or entry.get("description") or ""
    if not value and entry.get("content"):
        value = entry.content[0].get("value", "")
    summary = clean_text(value)
    return summary[:500]


def clean_text(value: str) -> str:
    text = TAG_RE.sub(" ", unescape(str(value)))
    return SPACE_RE.sub(" ", text).strip()
