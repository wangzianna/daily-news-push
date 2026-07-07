from __future__ import annotations

import re
from collections import defaultdict
from urllib.parse import urlsplit

from .models import NewsItem


PRIMARY_SOURCE_DOMAINS = {
    "openai.com",
    "deepmind.google",
    "anthropic.com",
    "microsoft.com",
    "googleblog.com",
    "apple.com",
    "meta.com",
    "about.fb.com",
    "nvidia.com",
    "github.blog",
    "36kr.com",
    "caixin.com",
}

RESEARCH_DOMAINS = {
    "arxiv.org",
    "nature.com",
    "science.org",
    "nejm.org",
    "thelancet.com",
    "cell.com",
    "acm.org",
    "ieee.org",
    "paperswithcode.com",
}

INSTITUTION_DOMAINS = {
    "who.int",
    "cdc.gov",
    "nih.gov",
    "fda.gov",
    "ema.europa.eu",
    "oecd.org",
    "worldbank.org",
    "imf.org",
    "gov.cn",
    "miit.gov.cn",
    "mofcom.gov.cn",
}

DEPTH_KEYWORDS = (
    "研究",
    "报告",
    "白皮书",
    "调查",
    "深度",
    "复盘",
    "访谈",
    "analysis",
    "research",
    "report",
    "paper",
    "survey",
    "interview",
)

MARKETING_KEYWORDS = (
    "限时",
    "福利",
    "重磅优惠",
    "免费领取",
    "报名",
    "课程",
    "训练营",
    "招商",
    "广告",
    "赞助",
    "sponsored",
    "webinar",
)

FINANCING_KEYWORDS = (
    "融资",
    "完成",
    "获投",
    "投资",
    "估值",
    "a轮",
    "b轮",
    "c轮",
    "series a",
    "series b",
    "funding",
    "raises",
)

CLICKBAIT_PATTERNS = (
    r"震惊",
    r"炸裂",
    r"彻底变天",
    r"一文看懂",
    r"必看",
    r"火了",
    r"刷屏",
    r"不得不看",
    r"you won't believe",
    r"what happened next",
)

REPOST_KEYWORDS = ("转载", "转自", "编译", "来源：", "via ", "repost")

HEALTH_CATEGORIES = {"健康", "医疗", "医学", "生命科学", "health", "medical", "medicine"}
AI_CATEGORIES = {"AI", "人工智能", "科技", "技术", "ai", "technology", "tech"}


def apply_quality_rules(
    items: list[NewsItem],
    max_per_direction: int = 4,
    max_total: int = 16,
) -> list[NewsItem]:
    scored = [score_item(item) for item in items]
    grouped: dict[str, list[NewsItem]] = defaultdict(list)
    for item in scored:
        grouped[item.category].append(item)

    limited: list[NewsItem] = []
    for category in sorted(grouped):
        category_items = sorted(grouped[category], key=quality_sort_key)
        limited.extend(category_items[:max_per_direction])

    return sorted(limited, key=quality_sort_key)[:max_total]


def score_item(item: NewsItem) -> NewsItem:
    text = f"{item.title} {item.summary}".lower()
    domain = normalize_domain(item.link)
    labels: list[str] = []
    penalties: list[str] = []
    score = item.weight

    if domain in PRIMARY_SOURCE_DOMAINS:
        score += 35
        labels.append("一手来源")
    if domain in INSTITUTION_DOMAINS:
        score += 30
        labels.append("机构来源")
    if domain in RESEARCH_DOMAINS:
        score += 35
        labels.append("研究来源")
    if contains_any(text, DEPTH_KEYWORDS):
        score += 20
        labels.append("深度内容")

    if contains_any(text, MARKETING_KEYWORDS):
        score -= 35
        penalties.append("营销软文")
    if contains_any(text, FINANCING_KEYWORDS):
        score -= 5
        penalties.append("融资/商业通稿")
    if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in CLICKBAIT_PATTERNS):
        score -= 25
        penalties.append("标题党")
    if contains_any(text, REPOST_KEYWORDS):
        score -= 20
        penalties.append("转载/编译")

    item.quality_score = score
    item.quality_labels = labels or ["常规资讯"]
    item.penalty_labels = penalties
    item.evidence_type = classify_health_evidence(item, domain, text)
    item.ai_type = classify_ai_type(item, domain, text)
    return item


def quality_sort_key(item: NewsItem) -> tuple[int, int, float]:
    return (
        -item.quality_score,
        -item.weight,
        -(item.published_at.timestamp() if item.published_at else 0),
    )


def classify_health_evidence(item: NewsItem, domain: str, text: str) -> str | None:
    category = item.category.lower()
    if category not in HEALTH_CATEGORIES and not contains_any(text, HEALTH_CATEGORIES):
        return None
    if domain in INSTITUTION_DOMAINS:
        return "医学机构"
    if domain in RESEARCH_DOMAINS or contains_any(text, ("论文", "临床试验", "study", "trial", "journal")):
        return "研究论文"
    if contains_any(text, ("政策", "指南", "监管", "报告", "policy", "guideline")):
        return "政策报告"
    if contains_any(text, ("我", "亲历", "经验", "分享", "个人", "my experience")):
        return "个人经验"
    return "媒体报道"


def classify_ai_type(item: NewsItem, domain: str, text: str) -> str | None:
    category = item.category.lower()
    if category not in AI_CATEGORIES and not contains_any(text, AI_CATEGORIES):
        return None
    if domain in PRIMARY_SOURCE_DOMAINS or contains_any(text, ("发布", "上线", "release", "announces", "introduces")):
        return "官方发布"
    if contains_any(text, ("模型", "benchmark", "推理", "多模态", "上下文", "能力", "model")):
        return "模型能力更新"
    if contains_any(text, ("产品", "应用", "agent", "copilot", "workflow", "工具")):
        return "产品应用"
    if contains_any(text, FINANCING_KEYWORDS + ("商业化", "收入", "营收", "订阅")):
        return "投融资/商业化"
    if contains_any(text, ("风险", "安全", "监管", "版权", "隐私", "合规", "regulation", "risk", "safety")):
        return "风险与监管"
    return "产品应用"


def normalize_domain(url: str) -> str:
    domain = urlsplit(url).netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def contains_any(text: str, keywords: tuple[str, ...] | set[str]) -> bool:
    return any(keyword.lower() in text for keyword in keywords)
