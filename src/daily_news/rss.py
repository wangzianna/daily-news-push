from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
import re
from typing import Any

import feedparser
import requests

from .models import NewsItem, Source


TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")


def fetch_source(source: Source, timeout: int, user_agent: str, limit: int) -> list[NewsItem]:
    response = requests.get(source.url, headers={"User-Agent": user_agent}, timeout=timeout)
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
            )
        )
    return items


def fetch_all_sources(
    sources: list[Source],
    timeout: int,
    user_agent: str,
    limit_per_source: int,
) -> tuple[list[NewsItem], dict[str, str]]:
    items: list[NewsItem] = []
    errors: dict[str, str] = {}
    for source in sources:
        try:
            items.extend(fetch_source(source, timeout, user_agent, limit_per_source))
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
