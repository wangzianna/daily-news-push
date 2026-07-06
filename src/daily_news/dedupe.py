from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .models import NewsItem


TRACKING_PREFIXES = ("utm_",)
TRACKING_KEYS = {"from", "spm", "fbclid", "gclid", "ref"}


def dedupe_items(items: list[NewsItem]) -> list[NewsItem]:
    seen: set[str] = set()
    result: list[NewsItem] = []
    for item in items:
        key = normalize_url(item.link) or normalize_title(item.title)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def sort_items(items: list[NewsItem]) -> list[NewsItem]:
    return sorted(
        items,
        key=lambda item: (
            item.category,
            -item.quality_score,
            -item.weight,
            -(item.published_at.timestamp() if item.published_at else 0),
        ),
    )


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key not in TRACKING_KEYS and not key.startswith(TRACKING_PREFIXES)
    ]
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path.rstrip("/"),
            urlencode(query),
            "",
        )
    )


def normalize_title(title: str) -> str:
    return " ".join(title.lower().split())
