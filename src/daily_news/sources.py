from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

from .models import Source


class SourceStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if not self.path.exists():
            self.path.write_text("sources: []\n", encoding="utf-8")

    def list(self, enabled_only: bool = False, section: str = "sources") -> list[Source]:
        data = self._read()
        sources = [self._to_source(item) for item in data.get(section, [])]
        if enabled_only:
            return [source for source in sources if source.enabled]
        return sources

    def list_many(self, sections: list[str], enabled_only: bool = False) -> list[Source]:
        sources: list[Source] = []
        seen: set[str] = set()
        for section in sections:
            for source in self.list(enabled_only=enabled_only, section=section):
                if source.id in seen:
                    continue
                seen.add(source.id)
                sources.append(source)
        return sources

    def get(self, source_id: str, section: str = "sources") -> Source:
        for source in self.list(section=section):
            if source.id == source_id:
                return source
        raise ValueError(f"订阅源不存在: {source_id}")

    def add(self, source: Source, section: str = "sources") -> None:
        sources = self.list(section=section)
        if any(item.id == source.id for item in sources):
            raise ValueError(f"订阅源 id 已存在: {source.id}")
        sources.append(source)
        self._write(sources, section=section)

    def delete(self, source_id: str, section: str = "sources") -> None:
        sources = self.list(section=section)
        next_sources = [source for source in sources if source.id != source_id]
        if len(next_sources) == len(sources):
            raise ValueError(f"订阅源不存在: {source_id}")
        self._write(next_sources, section=section)

    def update(self, source_id: str, section: str = "sources", **updates: Any) -> Source:
        sources = self.list(section=section)
        updated: Source | None = None
        for index, source in enumerate(sources):
            if source.id == source_id:
                values = asdict(source)
                values.update({key: value for key, value in updates.items() if value is not None})
                updated = self._to_source(values)
                sources[index] = updated
                break
        if updated is None:
            raise ValueError(f"订阅源不存在: {source_id}")
        self._write(sources, section=section)
        return updated

    def set_enabled(self, source_id: str, enabled: bool, section: str = "sources") -> Source:
        return self.update(source_id, section=section, enabled=enabled)

    def set_last_fetch_at(self, source_id: str, value: str, sections: list[str] | None = None) -> None:
        for section in sections or ["sources"]:
            try:
                self.update(source_id, section=section, last_fetch_at=value)
                return
            except ValueError:
                continue

    def _read(self) -> dict[str, Any]:
        with self.path.open("r", encoding="utf-8") as file:
            return yaml.safe_load(file) or {"sources": []}

    def _write(self, sources: list[Source], section: str = "sources") -> None:
        data = self._read()
        data[section] = [asdict(source) for source in sources]
        with self.path.open("w", encoding="utf-8") as file:
            yaml.safe_dump(data, file, allow_unicode=True, sort_keys=False)

    @staticmethod
    def _to_source(item: dict[str, Any]) -> Source:
        return Source(
            id=str(item["id"]),
            name=str(item["name"]),
            url=str(item["url"]),
            category=str(item["category"]),
            language=str(item.get("language", "zh")),
            enabled=bool(item.get("enabled", True)),
            weight=int(item.get("weight", 0)),
            last_fetch_at=item.get("last_fetch_at"),
        )
