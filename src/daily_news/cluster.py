from __future__ import annotations

from rapidfuzz import fuzz

from .models import NewsItem


def cluster_by_title(
    items: list[NewsItem],
    threshold: int = 80,
) -> list[list[NewsItem]]:
    clusters: list[list[NewsItem]] = []

    for item in items:
        target_title = _normalize_for_match(item.title)
        matched_cluster = None
        for cluster in clusters:
            cluster_title = _normalize_for_match(cluster[0].title)
            if item.language != cluster[0].language:
                continue
            ratio = fuzz.token_set_ratio(target_title, cluster_title)
            if ratio >= threshold:
                matched_cluster = cluster
                break
        if matched_cluster is not None:
            matched_cluster.append(item)
        else:
            clusters.append([item])

    return clusters


def pick_representative(cluster: list[NewsItem]) -> NewsItem:
    return max(cluster, key=lambda i: (i.quality_score, i.weight))


def dedupe_by_cluster(items: list[NewsItem], threshold: int = 80) -> list[NewsItem]:
    clusters = cluster_by_title(items, threshold=threshold)
    representatives = [pick_representative(cluster) for cluster in clusters]
    seen_ids: set[str] = set()
    result: list[NewsItem] = []
    for item in representatives:
        key = f"{item.title}|{item.source_id}"
        if key in seen_ids:
            continue
        seen_ids.add(key)
        result.append(item)
    return result


def _normalize_for_match(title: str) -> str:
    return " ".join(title.lower().split())
