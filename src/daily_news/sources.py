from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

from .models import Source


class SourceStore:
    def __init__(self, path: str | Path, state_path: str | Path | None = None) -> None:
        self.path = Path(path)
        if not self.path.exists():
            self.path.write_text("sources: []\n", encoding="utf-8")

        if state_path is None:
            self.state_path = self.path.parent / ".state" / "sources.json"
        else:
            self.state_path = Path(state_path)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)

    def list(self, enabled_only: bool = False, section: str = "sources") -> list[Source]:
        config_data = self._read_config()
        state_data = self._read_state()
        sources = [self._to_source(item, state_data) for item in config_data.get(section, [])]
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
        self._write_config(sources, section=section)

    def delete(self, source_id: str, section: str = "sources") -> None:
        sources = self.list(section=section)
        next_sources = [source for source in sources if source.id != source_id]
        if len(next_sources) == len(sources):
            raise ValueError(f"订阅源不存在: {source_id}")
        self._write_config(next_sources, section=section)
        state = self._read_state()
        state.pop(source_id, None)
        self._write_state(state)

    def update(self, source_id: str, section: str = "sources", **updates: Any) -> Source:
        sources = self.list(section=section)
        updated: Source | None = None
        for index, source in enumerate(sources):
            if source.id == source_id:
                values = asdict(source)
                values.update({key: value for key, value in updates.items() if value is not None})
                updated = self._to_source_static(values)
                sources[index] = updated
                break
        if updated is None:
            raise ValueError(f"订阅源不存在: {source_id}")
        self._write_config(sources, section=section)
        return updated

    def set_enabled(self, source_id: str, enabled: bool, section: str = "sources") -> Source:
        return self.update(source_id, section=section, enabled=enabled)

    def set_last_fetch_at(self, source_id: str, value: str, sections: list[str] | None = None) -> None:
        state = self._read_state()
        if source_id not in state:
            state[source_id] = {}
        state[source_id]["last_fetch_at"] = value
        state[source_id]["consecutive_failures"] = 0
        self._write_state(state)

    def increment_consecutive_failures(self, source_id: str) -> int:
        state = self._read_state()
        if source_id not in state:
            state[source_id] = {}
        count = state[source_id].get("consecutive_failures", 0) + 1
        state[source_id]["consecutive_failures"] = count
        self._write_state(state)
        return count

    def get_consecutive_failures(self, source_id: str) -> int:
        state = self._read_state()
        return state.get(source_id, {}).get("consecutive_failures", 0)

    def get_last_fetch_at(self, source_id: str) -> str | None:
        state = self._read_state()
        return state.get(source_id, {}).get("last_fetch_at")

    def _read_config(self) -> dict[str, Any]:
        with self.path.open("r", encoding="utf-8") as file:
            return yaml.safe_load(file) or {"sources": []}

    def _write_config(self, sources: list[Source], section: str = "sources") -> None:
        data = self._read_config()
        data[section] = [asdict(source) for source in sources]
        with self.path.open("w", encoding="utf-8") as file:
            yaml.safe_dump(data, file, allow_unicode=True, sort_keys=False)

    def _read_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {}
        try:
            with self.state_path.open("r", encoding="utf-8") as file:
                return json.load(file) or {}
        except (json.JSONDecodeError, OSError):
            return {}

    def _write_state(self, state: dict[str, Any]) -> None:
        with self.state_path.open("w", encoding="utf-8") as file:
            json.dump(state, file, ensure_ascii=False, indent=2)

    @staticmethod
    def _to_source(item: dict[str, Any], state: dict[str, Any]) -> Source:
        source_id = str(item["id"])
        source_state = state.get(source_id, {})
        return Source(
            id=source_id,
            name=str(item["name"]),
            url=str(item["url"]),
            category=str(item["category"]),
            language=str(item.get("language", "zh")),
            enabled=bool(item.get("enabled", True)),
            weight=int(item.get("weight", 0)),
            last_fetch_at=source_state.get("last_fetch_at") or item.get("last_fetch_at"),
            credibility=str(item.get("credibility", "media")),
        )

    @staticmethod
    def _to_source_static(item: dict[str, Any]) -> Source:
        return Source(
            id=str(item["id"]),
            name=str(item["name"]),
            url=str(item["url"]),
            category=str(item["category"]),
            language=str(item.get("language", "zh")),
            enabled=bool(item.get("enabled", True)),
            weight=int(item.get("weight", 0)),
            last_fetch_at=None,
            credibility=str(item.get("credibility", "media")),
        )
