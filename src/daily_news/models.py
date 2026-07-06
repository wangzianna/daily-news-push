from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Source:
    id: str
    name: str
    url: str
    category: str
    language: str
    enabled: bool = True
    weight: int = 0
    last_fetch_at: str | None = None


@dataclass
class NewsItem:
    title: str
    source: str
    source_id: str
    category: str
    published_at: datetime | None
    link: str
    summary: str
    weight: int = 0

